"""
GrandCypher Structural Components and Variable-Length Path Handling.

This module provides the core data structures and algorithms for handling
variable-length paths (edge hops) in Cypher queries, including:

1. **Data Structures**: HopSpec, EdgeMapping, Match, etc.
2. **Hop Expansion**: Materializing variable-length paths into concrete graphs
3. **Zero-Hop Unification**: Collapsing nodes that must be the same
4. **Graph Matching Support**: Preparing motifs for graph isomorphism

## Architecture Overview

### Query Processing Pipeline for Variable-Length Paths

When GrandCypher processes a query like `MATCH (A)-[*1..3]->(B)`, the flow is:

1. **Parse Query** → Create motif graph with hop metadata
   - Motif edge A->B has __min_hop__=1, __max_hop__=3

2. **Generate Hop Specifications** (`generate_edge_hop_specs`)
   - For each edge, create HopSpec for each possible hop count
   - Edge A->B → [HopSpec(1-hop), HopSpec(2-hop), HopSpec(3-hop)]

3. **Generate Hop Assignments** (`generate_hop_assignments`)
   - Create all combinations (Cartesian product) of hop choices
   - Each assignment: complete hop count selection for all edges

4. **For each hop assignment:**
   a. **Materialize Motif** (`materialize_motif`)
      - Expand edges into concrete paths with intermediate nodes
      - A -[*2]-> B becomes A -> _h1 -> B (two edges)

   b. **Unify Zero-Hop Nodes** (`unify_zero_hop_nodes`)
      - Find nodes connected by zero-hop edges (A -[*0]-> B)
      - Collapse them using Union-Find algorithm
      - Return unified motif + alias mapping

   c. **Graph Isomorphism Matching** (grandiso)
      - Match the materialized+unified motif against host graph
      - Find subgraph isomorphisms

   d. **Expand Node Mappings**
      - Use alias to add unified nodes back to results
      - Both A and B appear in results (pointing to same host node)

### Zero-Hop Edge Handling (Key Feature)

Zero-hop edges (e.g., `MATCH (A)-[*0]->(B)`) require A and B to be the **same
node** in the host graph. The handling process:

1. **Materialization**: Both A and B nodes added (no edges)
2. **Unification**: Union-Find groups A and B together
3. **Graph Construction**: Create motif with single representative node
4. **Matching**: Grandiso enforces A and B map to same host node
5. **Result Expansion**: Both A and B appear in query results

Example Flow:
```python
# Original motif: A -[*0]-> B -[*1]-> C
hop_specs = [
    HopSpec(edge_id=("A","B"), nodes=("A","A"), hop_count=0),  # Zero-hop
    HopSpec(edge_id=("B","C"), nodes=("B","C"), hop_count=1)   # Normal edge
]

# After materialize_motif:
# Nodes: {A, B, C}
# Edges: {(B, C)}  # No edge for zero-hop

# After unify_zero_hop_nodes:
# Nodes: {A, C}  # B merged into A
# Edges: {(A, C)}  # B->C became A->C
# Alias: {A: A, B: A, C: C}

# After matching and expansion:
# node_mappings: {A: "host_x", B: "host_x", C: "host_y"}
# Both A and B map to the same host node!
```

### Performance Considerations

- **Exponential combinations**: Query with N edges, each having K hop options
  → K^N materialized motifs to match
- **Zero-hop optimization**: Unification reduces graph size before matching
- **UnionFind efficiency**: O(α(n)) ≈ O(1) for practical sizes

## Key Classes and Functions

### Core Data Structures
- `HopSpec`: Represents one concrete hop expansion for an edge
- `HopAssignment`: Maps all edges to their hop specifications
- `Match`: Stores matching results (node mappings, edge paths)
- `UnionFind`: Efficient set union/find for node unification

### Pipeline Functions
- `generate_edge_hop_specs()`: Edge → list of hop options
- `generate_hop_assignments()`: Cartesian product of all options
- `materialize_motif()`: Expand edges according to hop assignment
- `unify_zero_hop_nodes()`: Collapse zero-hop connected nodes

### Design Principles
- **Separation of concerns**: Each function has single, clear responsibility
- **Immutability**: Original motif preserved; transformations create new graphs
- **Efficiency**: Union-Find runs once per hop assignment (not duplicated)
- **Correctness**: Graph isomorphism ensures unified nodes map to same host node
"""

from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Tuple, Union, Optional, Hashable
import itertools
import networkx as nx
import uuid
from functools import cached_property


NodeID = Union[str, Hashable]
EdgeID = Tuple[NodeID, NodeID]
NodeMapping = Dict[NodeID, NodeID]


@dataclass(frozen=True)
class EdgeHopKey:
    edge_id: EdgeID
    keys: tuple[int, ...]


HopKeyAssignment = Dict[EdgeID, EdgeHopKey]


@dataclass(frozen=True)
class EdgeWithKey:
    u: NodeID
    v: NodeID
    k: int  # multi key
    h: int  # hop info


@dataclass(frozen=True)
class HopSpec:
    """Represents one expansion option for one motif edge."""
    edge_id: EdgeID
    nodes: Tuple[Any, ...]   # (u,u) or (u,v) or (u,x1,x2,v)
    hop_count: int


HopAssignment = Dict[EdgeID, HopSpec]


def generate_edge_hop_specs(motif: nx.DiGraph) -> list[list[HopSpec]]:
    """
    Generate all possible hop specifications for each edge in a motif.

    For edges with variable-length path notation (e.g., -[*2..4]->), this
    generates all concrete hop counts within the specified range. Each edge
    becomes a list of HopSpec options representing different path lengths.

    Args:
        motif: A motif graph where edges may have hop metadata:
            - __min_hop__: Minimum number of hops (default: 1)
            - __max_hop__: Maximum number of hops (default: same as min)
            - Example: -[*2..4]-> sets __min_hop__=2, __max_hop__=4

    Returns:
        List[List[HopSpec]]: One list of HopSpec options per motif edge.
            Each HopSpec represents one possible expansion (hop count).

    Example:
        >>> motif = nx.DiGraph()
        >>> motif.add_edge("A", "B", __min_hop__=1, __max_hop__=2)
        >>> motif.add_edge("B", "C")  # Default: 1 hop
        >>>
        >>> specs = generate_edge_hop_specs(motif)
        >>> # specs[0] for edge A->B: [HopSpec(1-hop), HopSpec(2-hop)]
        >>> # specs[1] for edge B->C: [HopSpec(1-hop)]
        >>> len(specs)
        2
        >>> len(specs[0])  # A->B has 2 options (1-hop and 2-hop)
        2
        >>> len(specs[1])  # B->C has 1 option (1-hop)
        1

    Note:
        - Zero-hop (min_hop=0) creates a HopSpec with nodes=(u,u)
        - Multi-hop creates intermediate node IDs using _new_hop_id()
        - Used with generate_hop_assignments() to create all combinations
    """
    all_edges = []
    is_multi = motif.is_multigraph()

    edges = motif.edges(keys=True) if is_multi else motif.edges(keys=False)

    for edge in edges:
        # NOTE: multi graph isn't used in motif
        if is_multi:
            u, v, k = edge
            edge_id = (u, v)
            meta = motif.edges[u, v, k]
        else:
            u, v = edge
            edge_id = (u, v)
            meta = motif.edges[u, v]
        min_hop = int(meta.get("__min_hop__", 1))
        max_hop = int(meta.get("__max_hop__", min_hop))

        hop_specs = _enumerate_hops(
            edge_id, u, v, min_hop, max_hop
        )
        all_edges.append(hop_specs)

    return all_edges


def generate_hop_assignments(all_edge_hops: list[list[HopSpec]]) -> Generator[HopAssignment, None, None]:
    """
    Generate all possible combinations of hop assignments for a motif.

    Given hop options for each edge (from generate_edge_hop_specs), this
    produces the Cartesian product of all choices, representing every possible
    way to materialize the variable-length paths in the motif.

    Args:
        all_edge_hops: List of HopSpec options per edge. For example:
            [[HopSpec(1-hop), HopSpec(2-hop)],  # Edge 1: 2 options
             [HopSpec(1-hop)]]                   # Edge 2: 1 option
            Results in 2×1 = 2 combinations

    Yields:
        HopAssignment: Dictionary mapping each edge_id to one HopSpec choice.
            Represents one complete assignment of hop counts for all edges.

    Example:
        >>> # Motif: A -[*1..2]-> B -[*1]-> C
        >>> # Edge A->B has 2 options (1-hop, 2-hop)
        >>> # Edge B->C has 1 option (1-hop)
        >>>
        >>> all_edge_hops = [
        ...     [HopSpec(("A","B"), ("A","B"), 1),
        ...      HopSpec(("A","B"), ("A","x","B"), 2)],
        ...     [HopSpec(("B","C"), ("B","C"), 1)]
        ... ]
        >>>
        >>> assignments = list(generate_hop_assignments(all_edge_hops))
        >>> len(assignments)
        2
        >>> # Assignment 1: A->B uses 1-hop, B->C uses 1-hop
        >>> # Assignment 2: A->B uses 2-hop, B->C uses 1-hop

    Complexity:
        Produces ∏(len(options) for options in all_edge_hops) combinations.
        For a query with N edges, each having K hop options, yields K^N assignments.

    Note:
        - Each assignment is used to create one materialized motif
        - The number of combinations can grow exponentially
        - Each combination is matched independently against the host graph
    """
    for combo in itertools.product(*all_edge_hops):
        yield {hs.edge_id: hs for hs in combo}


def materialize_motif(hop_assignment: Dict[EdgeID, HopSpec], motif: nx.DiGraph) -> nx.DiGraph:
    """
    Materialize a motif graph by expanding edges according to hop specifications.

    This function transforms a motif with variable-length path edges (e.g., [*1..3])
    into a concrete graph where each edge is expanded to a specific path length.

    Args:
        hop_assignment: Mapping from original edge IDs to their hop specifications.
            Each HopSpec contains:
            - edge_id: (u, v) tuple identifying the original edge
            - nodes: Tuple of nodes in the expanded path (e.g., (A, x1, x2, B) for 3 hops)
            - hop_count: Number of hops (0 for zero-hop, length of path - 1 otherwise)

        motif: Original motif graph containing node attributes and edge metadata.
            May be a MultiDiGraph if the pattern has multiple edges between nodes.

    Returns:
        nx.DiGraph: Materialized graph where:
            - Edges are expanded into paths of concrete length
            - Zero-hop edges (hop_count=0) result in nodes being added but no edges
            - Node attributes are preserved from the original motif
            - Edge attributes are preserved (excluding hop metadata: __min_hop__, __max_hop__, __is_hop__)
            - Intermediate nodes (e.g., x1, x2) are added without attributes

    Examples:
        >>> # Original motif: A -[*2]-> B
        >>> motif = nx.DiGraph()
        >>> motif.add_node("A", type="Person")
        >>> motif.add_node("B", type="Person")
        >>> motif.add_edge("A", "B", __min_hop__=2, __max_hop__=2)
        >>>
        >>> # Hop assignment specifies the concrete path
        >>> hop_assignment = {
        ...     ("A", "B"): HopSpec(
        ...         edge_id=("A", "B"),
        ...         nodes=("A", "_h1", "B"),  # 2 hops via intermediate node
        ...         hop_count=2
        ...     )
        ... }
        >>>
        >>> result = materialize_motif(hop_assignment, motif)
        >>> list(result.edges())
        [('A', '_h1'), ('_h1', 'B')]
        >>> result.nodes["A"]
        {'type': 'Person'}

        Zero-hop example:
        >>> # A -[*0]-> B means A and B must be the same node
        >>> hop_assignment = {
        ...     ("A", "B"): HopSpec(
        ...         edge_id=("A", "B"),
        ...         nodes=("A", "A"),  # Zero-hop: start and end are same
        ...         hop_count=0
        ...     )
        ... }
        >>> result = materialize_motif(hop_assignment, motif)
        >>> list(result.edges())
        []  # No edges added for zero-hop
        >>> set(result.nodes())
        {'A', 'B'}  # Both nodes exist for later unification

    Note:
        - Isolated nodes (no incoming/outgoing edges) are preserved
        - For zero-hop edges, both endpoint nodes are added to enable
          subsequent unification by unify_zero_hop_nodes()
        - Edge attributes like __labels__ are preserved for pattern matching
    """
    g = nx.DiGraph()

    # Add all original nodes with attributes
    for n, data in motif.nodes(data=True):
        if motif.out_degree(n) == 0 and motif.in_degree(n) == 0:
            g.add_node(n, **data)

    new_nodes = set()
    # Add expanded edges
    for hs in hop_assignment.values():
        A, B = hs.edge_id
        nodes = hs.nodes
        new_nodes.update(nodes)
        if hs.hop_count == 0:
            new_nodes.update((A, B))
            continue
        if motif.is_multigraph():
            motif_edge_data = motif.get_edge_data(A, B) or {}
            if motif_edge_data:
                motif_edge_data = next(iter(motif_edge_data.values()))
        else:
            motif_edge_data = motif.get_edge_data(A, B) or {}
        motif_edge_data = {k: v for k, v in motif_edge_data.items() if k not in (
            "__min_hop__", "__max_hop__", "__is_hop__"
        )}
        if "__labels__" not in motif_edge_data:
            motif_edge_data["__labels__"] = set()
        for a, b in zip(nodes[:-1], nodes[1:]):
            g.add_edge(a, b, **motif_edge_data)

    # Add nodes attributes
    for n in new_nodes:
        if n not in motif.nodes:
            continue
        g.add_node(n, **motif.nodes[n])

    return g


def _new_hop_id() -> str:
    return f"__hop_{uuid.uuid4().hex[:6]}"


def _enumerate_hops(
    edge_id: EdgeID,
    u: NodeID,
    v: NodeID,
    min_hop: int,
    max_hop: int,
) -> List[HopSpec]:
    """
    Generate all HopSpecs for a single motif edge.
    """

    hop_specs: List[HopSpec] = []

    # --- Case A: zero-hop allowed (u→u)
    if min_hop == 0:
        hop_specs.append(HopSpec(edge_id, (u, u), hop_count=0))

    intermediates = []
    # --- Case B: hops from 1 to max_hop
    # hop_count = number of edges between u→v
    # hop_count == 1 => [u, v]
    # hop_count == k => [u, x1, ..., x(k-1), v]
    for hop_count in range(1, max_hop):
        if hop_count >= min_hop:
            nodes = tuple([u] + intermediates + [v])
            hop_specs.append(HopSpec(edge_id, nodes, hop_count=hop_count))
        intermediates.append(_new_hop_id())

    return hop_specs


@dataclass(frozen=True)
class EdgePath:
    """
    Represents a fully expanded edge-path in the host graph corresponding to a
    single motif edge after hop-expansion.

    Parameters
    ----------
    nodes : list[str]
        The ordered list of host node names that form the expanded path.
        Example: ['a', 'x1', 'x2', 'b']

    keys : list[int]
        The multiedge keys for each hop along the path. `keys[i]` corresponds to
        the hop (nodes[i] -> nodes[i+1]). Keys may be empty if the host graph
        is a `DiGraph` or if no valid key exists.

    hop_count : int
        The number of hops in the expanded motif edge (len(nodes) - 1).

    Iteration
    ---------
    Iterating over an EdgePath yields a sequence of `EdgeWithKey` objects,
    each representing one hop along the path.

    Properties
    ----------
    edges : list[EdgeWithKey]
        Materialized list of hop edges, each providing:
        - u, v : node pair
        - k    : multiedge key or `None`
        - h    : hop_count (for convenience)

    Notes
    -----
    - The class is immutable.
    - It does not validate path consistency; correctness is expected from
      upstream expansion logic.
    """
    nodes: list[str]
    keys: list[int]
    hop_count: int

    def __iter__(self):
        yield from self.edges

    @cached_property
    def edges(self) -> list[EdgeWithKey]:
        return [
            EdgeWithKey(self.nodes[i], self.nodes[i+1], self.keys[i] if self.keys else None, self.hop_count)
            for i in range(len(self.nodes)-1)
        ]

@dataclass(frozen=True)
class EdgeMapping:
    """
    Container for the hop expansion and multiedge-key assignments associated
    with a single motif match.

    This class links each motif edge (identified by its EdgeID) to:
      - a HopSpec describing the host-node expansion of the motif edge
      - an EdgeHopKey describing the multi-edge key assignment for each hop

    Parameters
    ----------
    edge_hop_map : HopAssignment
        Mapping {EdgeID -> HopSpec}. Each HopSpec defines the expanded host-node
        path for a motif edge (e.g., ['A', 'x1', 'x2', 'B']).

    edge_key_map : HopKeyAssignment
        Mapping {EdgeID -> EdgeHopKey}. Each EdgeHopKey contains a tuple of
        multiedge keys aligned with the hops in the corresponding HopSpec.

    Methods
    -------
    edge_ids() -> list[EdgeID]
        List of motif-edge ids included in this mapping.

    edge_paths : list[EdgePath]
        A lazily computed list of EdgePath objects, constructed by combining
        the corresponding HopSpec and EdgeHopKey entries for each EdgeID.

    edge_path(u, v) -> EdgePath
        Retrieve the EdgePath associated with the motif edge (u, v).

    Notes
    -----
    - This object stores **motif→host expansion**, not host→motif.
    - EdgePath creation is lightweight and deterministic; no graph queries
      occur at this stage.
    """
    edge_hop_map: HopAssignment
    edge_key_map: HopKeyAssignment

    def edge_ids(self) -> list[EdgeID]:
        return list(self.edge_hop_map.keys())

    @cached_property
    def edge_paths(self) -> list[EdgePath]:
        return [
            EdgePath(
                nodes=self.edge_hop_map[(u, v)].nodes,
                keys=self.edge_key_map[(u, v)].keys,
                hop_count=self.edge_hop_map[(u, v)].hop_count,
            ) for u, v in self.edge_hop_map.keys()
        ]

    def edge_path(self, u, v) -> EdgePath:
        return EdgePath(
            nodes=self.edge_hop_map[(u, v)].nodes,
            keys=self.edge_key_map[(u, v)].keys,
            hop_count=self.edge_hop_map[(u, v)].hop_count,
        )


class MotifToHostView:
    """
    A read-only view that exposes motif→host translation for both nodes and
    expanded edges, using the information stored in a Match.

    This view gives you a clean interface for accessing host-level entities
    directly from motif identifiers.

    Access Patterns
    ---------------
    mth.node('A')
        -> host node corresponding to motif node 'A'

    mth.edge('A', 'B')
        -> EdgePath describing the full host expanded path of motif edge A→B

    Attributes
    ----------
    _match : Match
        Reference to the parent Match object containing node and edge mappings.

    Methods
    -------
    node(node) -> str
        Translate motif node → host node.

    has_node(node) -> bool
        Check whether a motif node has a mapped host node.

    edge(u, v) -> EdgePath
        Translate motif edge (u, v) → the expanded host EdgePath, including
        host nodes and multi-edge keys.

    Notes
    -----
    - Returned EdgePath instances always contain **host node names**.
    - This view does not perform any validation against the actual host graph—
      it purely reinterprets the Match's stored metadata.
    - Node and edge translations are fully deterministic once a Match exists.
    """
    def __init__(self, match: "Match"):
        self._match = match

    def _get_paths(self, u, v):
            path = self._match.edge_mapping.edge_path(u, v)
            return EdgePath(
                nodes=[self._match.node_mappings[n] for n in path.nodes],
                keys=path.keys,
                hop_count=path.hop_count
            )

    def node(self, node: NodeID) -> NodeID:
        return self._match.node_mappings[node]

    def has_node(self, node) -> bool:
        return node in self._match.node_mappings

    def edge(self,u, v) -> EdgePath:
        return self._get_paths(u, v)


@dataclass
class Match:
    """
    Represents the result of matching a motif against a host graph.

    This object stores:
      - node_mappings: motif node → host node
      - edge_mapping: motif edge expansions (HopSpecs + EdgeHopKeys)
      - where_results: optional predicate evaluations (if applicable)

    Parameters
    ----------
    node_mappings : NodeMapping
        A dictionary mapping motif node names to host node names.

    where_results : list[bool] or None
        Optional list representing WHERE-clause results or other filter
        evaluations associated with the match. Semantics depend on the caller.

    edge_mapping : EdgeMapping or None
        Encodes hop-expanded motif edges and their multi-edge key assignments.

    Properties
    ----------
    mth : MotifToHostView
        Convenient motif→host view bound to this Match, supporting:
            mth.node(...)
            mth.edge(...)

    Notes
    -----
    - The Match does not perform any graph-level validation by itself.
    - It is typically produced by a motif-matching engine that ensures the
      compatibility between motif structure and host graph structure.
    """
    node_mappings: NodeMapping
    where_results: Optional[list[bool]]  # what for?
    edge_mapping: Optional[EdgeMapping]

    @cached_property
    def mth(self) -> MotifToHostView:
        return MotifToHostView(self)


class UnionFind:
    """
    Union-Find (Disjoint Set Union) data structure with path compression.

    This data structure efficiently tracks and merges disjoint sets, supporting
    two primary operations:
    - find(x): Determine which set an element belongs to (returns representative)
    - union(a, b): Merge the sets containing elements a and b

    Implementation uses path compression during find() for O(α(n)) amortized
    time complexity, where α is the inverse Ackermann function (effectively constant).

    Used in GrandCypher for:
    - Unifying nodes connected by zero-hop edges (A -[*0]-> B means A and B
      must be the same node)
    - Building alias mappings to track which nodes were merged

    Example:
        >>> uf = UnionFind()
        >>> uf.union("A", "B")  # A and B are in the same set
        >>> uf.union("B", "C")  # Transitively, A, B, C are all in the same set
        >>> uf.find("A")
        'A'
        >>> uf.find("B")
        'A'
        >>> uf.find("C")
        'A'
        >>> # All three return the same representative
    """
    def __init__(self):
        """Initialize an empty Union-Find structure."""
        self.parent = {}

    def find(self, x):
        """
        Find the representative (root) of the set containing x.

        Uses path compression: during traversal to the root, all nodes
        along the path are updated to point directly to the root.

        Args:
            x: Element to find the representative for

        Returns:
            The representative element of the set containing x

        Time Complexity:
            O(α(n)) amortized, where α is the inverse Ackermann function
        """
        if x not in self.parent:
            self.parent[x] = x
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])  # Path compression
        return self.parent[x]

    def union(self, a, b):
        """
        Merge the sets containing elements a and b.

        After this operation, find(a) and find(b) will return the same
        representative. The representative of a becomes the representative
        of the merged set.

        Args:
            a: Element from first set
            b: Element from second set

        Time Complexity:
            O(α(n)) amortized
        """
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra  # Make a's root the parent of b's root


def unify_zero_hop_nodes(motif: nx.DiGraph,
                        hop_specs: list[HopSpec],
                         ) -> tuple[nx.DiGraph, dict[NodeID, NodeID]]:
    """
    Collapse nodes connected by zero-hop edges in a motif graph.

    Zero-hop edges in Cypher (e.g., MATCH (A)-[*0]->(B)) indicate that the start
    and end nodes must be the same node in the host graph. This function uses
    Union-Find to identify all nodes that must be unified and creates a new graph
    where these nodes are merged into single representative nodes.

    The unification process:
    1. Use Union-Find to group nodes connected by zero-hop edges
    2. Build an alias mapping from all nodes to their representatives
    3. Create a new graph with:
       - One node per equivalence class (using representative as node ID)
       - Merged node attributes from all unified nodes
       - Edges rewritten to use representative nodes
       - Zero-hop edges removed (they become self-loops, which are omitted)

    Args:
        motif: The motif graph to unify. Nodes and edges may have attributes.
        hop_specs: Collection of HopSpec objects. Zero-hop specs (hop_count=0)
            indicate which edges trigger unification. For example:
            HopSpec(edge_id=("A","B"), nodes=("A","A"), hop_count=0)
            means A and B should be unified.

    Returns:
        tuple[nx.DiGraph, dict[NodeID, NodeID]]: A tuple containing:
            - unified_motif: New graph with nodes collapsed
            - alias: Mapping from original node IDs to representative node IDs
                    Example: {"A": "A", "B": "A", "C": "C"} means B was unified into A

    Examples:
        >>> # Single zero-hop: A -[*0]-> B
        >>> motif = nx.DiGraph()
        >>> motif.add_node("A", type="Person")
        >>> motif.add_node("B", type="Person")
        >>> hop_specs = [HopSpec(edge_id=("A","B"), nodes=("A","A"), hop_count=0)]
        >>>
        >>> unified, alias = unify_zero_hop_nodes(motif, hop_specs)
        >>> list(unified.nodes())
        ['A']
        >>> alias
        {'A': 'A', 'B': 'A'}

        >>> # Chain: A -[*0]-> B -[*0]-> C (all unify to A)
        >>> motif = nx.DiGraph()
        >>> for n in ["A", "B", "C"]:
        ...     motif.add_node(n)
        >>> hop_specs = [
        ...     HopSpec(edge_id=("A","B"), nodes=("A","A"), hop_count=0),
        ...     HopSpec(edge_id=("B","C"), nodes=("B","B"), hop_count=0)
        ... ]
        >>> unified, alias = unify_zero_hop_nodes(motif, hop_specs)
        >>> alias
        {'A': 'A', 'B': 'A', 'C': 'A'}

        >>> # Mixed: A -[*0]-> B, B -[*1]-> C
        >>> motif = nx.DiGraph()
        >>> motif.add_node("A")
        >>> motif.add_node("B")
        >>> motif.add_node("C")
        >>> motif.add_edge("B", "C")
        >>> hop_specs = [
        ...     HopSpec(edge_id=("A","B"), nodes=("A","A"), hop_count=0),
        ...     HopSpec(edge_id=("B","C"), nodes=("B","C"), hop_count=1)
        ... ]
        >>> unified, alias = unify_zero_hop_nodes(motif, hop_specs)
        >>> list(unified.nodes())
        ['A', 'C']
        >>> list(unified.edges())
        [('A', 'C')]  # Edge B->C became A->C

    Note:
        - If no zero-hop edges exist, returns (original_motif, {})
        - Node attributes are merged (later values overwrite earlier ones)
        - The first node in each equivalence class becomes the representative
        - This function is called by _edge_hop_motifs() before graph isomorphism matching
    """
    uf = UnionFind()

    # for (u1, v1), path in paths.items():
    for hs in hop_specs:
        # if len(nodes) < 2 or nodes[0] != path[-1]:
        if hs.hop_count != 0:
            continue
        u1, v1 = hs.edge_id
        uf.union(u1, v1)

    if not uf.parent:
        return motif, {}

    # 2. Build alias mapping
    alias = {n: uf.find(n) for n in motif.nodes()}

    # 3. Create unified motif graph
    unified = nx.DiGraph()

    # Merge node attributes
    merged_attrs = {}
    for n, attrs in motif.nodes(data=True):
        rep = alias[n]
        if rep not in merged_attrs:
            merged_attrs[rep] = dict(attrs)
        else:
            merged_attrs[rep].update(attrs)

    for rep, attrs in merged_attrs.items():
        unified.add_node(rep, **attrs)

    # 4. Rewrite edges (skip zero-hop edges)
    for u, v, attrs in motif.edges(data=True):
        u2, v2 = alias[u], alias[v]
        unified.add_edge(u2, v2, **attrs)

    return unified, alias
