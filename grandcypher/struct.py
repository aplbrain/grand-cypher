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
    u: str
    v: str
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
    Returns: List[List[HopSpec]]
        One list per motif edge.
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
    all_edge_hops: List[List[HopSpec]]
        List of hop-spec choices per edge.

    Yields:
        Dict[EdgeID, HopSpec]
    """
    for combo in itertools.product(*all_edge_hops):
        yield {hs.edge_id: hs for hs in combo}


def materialize_motif(hop_assignment: Dict[EdgeID, HopSpec], motif: nx.DiGraph) -> nx.DiGraph:
    """
    hop_assignment: Dict[EdgeID, HopSpec]
    motif: original motif graph (for node attrs)

    Returns:
        nx.DiGraph
    """
    g = nx.DiGraph()

    # Add all original nodes with attributes
    for n, data in motif.nodes(data=True):
        if motif.out_degree(n) == 0 and motif.in_degree(n) == 0:
            g.add_node(n, **data)

    new_nodes = set()
    # Add expanded edges
    for hs in hop_assignment.values():
        nodes = hs.nodes
        new_nodes.update(nodes)
        if hs.hop_count == 0:
            continue
        A, B = hs.edge_id
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
      it purely reinterprets the Match’s stored metadata.
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
    def mth(self):
        return MotifToHostView(self)
