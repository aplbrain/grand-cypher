
from .struct import *


# ===================================================================
#                              TESTS
# ===================================================================

def test_edgepath_edges():
    ep = EdgePath(nodes=["A", "B", "C"], keys=[10, 20], hop_count=2)

    edges = ep.edges

    assert len(edges) == 2
    assert edges[0] == EdgeWithKey("A", "B", 10, 2)
    assert edges[1] == EdgeWithKey("B", "C", 20, 2)


def test_edgemapping_edgepath():
    hop_map = {
        ("A", "B"): HopSpec(map_key=("A", "B"), nodes=["x1", "x2", "x3"], hop_count=5)
    }
    key_map = {
        ("A", "B"): EdgeHopKey(map_key=("A", "B"), keys=(1, 2))
    }

    em = EdgeMapping(edge_hop_map=hop_map, edge_key_map=key_map)

    ep = em.edge_path("A", "B")

    assert ep.nodes == ["x1", "x2", "x3"]
    assert ep.keys == (1, 2)
    assert ep.hop_count == 5


def test_motif_to_host_view_node():
    match = Match(
        node_mappings={"A": "H1", "B": "H2"},
        where_results=None,
        edge_mapping=None,
    )

    view = match.mth

    assert view.node("A") == "H1"
    assert view.has_node("B") is True
    assert view.has_node("C") is False


def test_motif_to_host_view_edge():
    hop_map = {("A", "B"): HopSpec(map_key=("A", "B"), nodes=["x1", "x2"], hop_count=3)}
    key_map = {("A", "B"): EdgeHopKey(map_key=("A", "B"), keys=(9,))}

    match = Match(
        node_mappings={"x1": "H1", "x2": "H2"},
        where_results=None,
        edge_mapping=EdgeMapping(hop_map, key_map),
    )

    mth = match.mth
    ep = mth.edge("A", "B")

    assert ep.nodes == ["H1", "H2"]
    assert ep.keys == (9,)
    assert ep.hop_count == 3


def test_iteration_over_edgepath():
    ep = EdgePath(nodes=["A", "B", "C"], keys=[7, 8], hop_count=1)
    items = list(iter(ep))

    assert len(items) == 2
    assert items[0].u == "A"
    assert items[1].v == "C"
