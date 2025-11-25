from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Generator, Iterable, List, Tuple, Union
import itertools
import networkx as nx
import uuid


MotifNode = Any
MotifEdgeKey = Union[int, str]
MapKey = Union[Tuple[Any, Any], Tuple[Any, Any, Any]]   # (u,v) or (u,v,k)


# @dataclass(frozen=True)
# class HopSpec:
#     """Represents one expansion option for one motif edge."""
#     map_key: MapKey
#     nodes: Tuple[MotifNode, ...]  # hop sequence: (u, u) or (u,v) or (u,x1,...,v)
#     labels: Any                   # __labels__ attribute


@dataclass(frozen=True)
class HopSpec:
    """Represents one expansion option for one motif edge."""
    map_key: MapKey
    nodes: Tuple[Any, ...]   # (u,u) or (u,v) or (u,x1,x2,v)
    labels: Any
    hop_count: int


HopAssignment = Dict[MapKey, HopSpec]



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
            # map_key = (u, v, k)
            map_key = (u, v)
            meta = motif.edges[u, v, k]
        else:
            u, v = edge
            map_key = (u, v)
            meta = motif.edges[u, v]
        min_hop = int(meta.get("__min_hop__", 1))
        max_hop = int(meta.get("__max_hop__", min_hop))
        labels = meta["__labels__"]

        hop_specs = _enumerate_hops(
            map_key, u, v, labels, min_hop, max_hop
        )
        all_edges.append(hop_specs)

    return all_edges


def generate_hop_assignments(all_edge_hops: list[list[HopSpec]]) -> Generator[HopAssignment]:
    """
    all_edge_hops: List[List[HopSpec]]
        List of hop-spec choices per edge.

    Yields:
        Dict[MapKey, HopSpec]
    """
    for combo in itertools.product(*all_edge_hops):
        yield {hs.map_key: hs for hs in combo}


def materialize_motif(hop_assignment: Dict[MapKey, HopSpec], motif: nx.DiGraph) -> nx.DiGraph:
    """
    hop_assignment: Dict[MapKey, HopSpec]
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
        for a, b in zip(nodes[:-1], nodes[1:]):
            g.add_edge(a, b, __labels__=hs.labels)

    # Add nodes, including single nodes with no edges
    for n in new_nodes:
        if n not in motif.nodes:
            continue
        g.add_node(n, **motif.nodes[n])
    return g


def _new_hop_id() -> str:
    return f"__hop_{uuid.uuid4().hex[:6]}"


def _enumerate_hops(
    map_key: MapKey,
    u: MotifNode,
    v: MotifNode,
    labels: Any,
    min_hop: int,
    max_hop: int,
) -> Tuple[List[HopSpec], int]:
    """
    Generate all HopSpecs for a single motif edge.
    """

    hop_specs: List[HopSpec] = []

    # --- Case A: zero-hop allowed (u→u)
    if min_hop == 0:
        hop_specs.append(HopSpec(map_key, (u, u), labels, hop_count=0))

    intermediates = []
    # --- Case B: hops from 1 to max_hop
    # hop_count = number of edges between u→v
    # hop_count == 1 => [u, v]
    # hop_count == k => [u, x1, ..., x(k-1), v]
    for hop_count in range(1, max_hop):
        if hop_count >= min_hop:
            nodes = tuple([u] + intermediates + [v])
            hop_specs.append(HopSpec(map_key, nodes, labels, hop_count=hop_count))
        intermediates.append(_new_hop_id())

    return hop_specs
