import pytest
import networkx as nx

from .hinter import Hinter
from . import _is_edge_attr_match, _is_node_attr_match

@pytest.fixture
def hinter():
    return Hinter(_is_node_attr_match, _is_edge_attr_match)


# ==========================================================
# eliminate_supersets
# ==========================================================

def test_eliminate_supersets_basic(hinter: Hinter):
    hints = [
        {"A": 1},
        {"A": 1, "B": 2},
        {"A": 1, "B": 2, "C": 3},
        {"B": 2},
    ]
    # Expected: keep only {A:1} and {B:2}
    out = hinter.eliminate_supersets(hints)
    assert sorted(out, key=lambda d: tuple(d.items())) == [
        {"A": 1},
        {"B": 2},
    ]


def test_eliminate_supersets_duplicate(hinter: Hinter):
    hints = [
        {"A": 1},
        {"A": 1},
        {"A": 1, "B": 2},
    ]
    out = hinter.eliminate_supersets(hints)
    assert out == [{"A": 1}]   # duplicate eliminated, superset removed


def test_eliminate_supersets_no_subsumption(hinter: Hinter):
    hints = [
        {"A": 1},
        {"A": 2},
        {"B": 3},
    ]
    out = hinter.eliminate_supersets(hints)
    # Nothing subsumes anything
    assert sorted(out, key=lambda d: tuple(d.items())) == [
        {"A": 1}, {"A": 2}, {"B": 3}
    ]


def test_eliminate_supersets_conflicting(hinter: Hinter):
    hints = [
        {"A": 1},
        {"A": 2},     # conflicts → neither subsumes the other
        {"A": 1, "B": 2},
        {"A": 2, "B": 3},
    ]
    out = hinter.eliminate_supersets(hints)
    assert sorted(out, key=lambda d: tuple(d.items())) == [
        {"A": 1},
        {"A": 2},
    ]


def test_eliminate_supersets_empty(hinter: Hinter):
    assert hinter.eliminate_supersets([]) == []


def test_eliminate_supersets_single(hinter: Hinter):
    assert hinter.eliminate_supersets([{"A": 1}]) == [{"A": 1}]


# ==========================================================
# index_domain_to_hints
# ==========================================================

def test_index_domain_to_hints_basic(hinter: Hinter):
    result = {
        "A": {1},
        "B": {2, 3},
        "C": {4, 5},
    }

    out = hinter.index_domain_to_hints(result)

    # Cartesian product:
    expected = [
        {"A": 1, "B": 2, "C": 4},
        {"A": 1, "B": 2, "C": 5},
        {"A": 1, "B": 3, "C": 4},
        {"A": 1, "B": 3, "C": 5},
    ]

    assert sorted(out, key=lambda d: tuple(sorted(d.items()))) == \
           sorted(expected, key=lambda d: tuple(sorted(d.items())))


def test_index_domain_to_hints_single_key(hinter: Hinter):
    result = {"A": {1, 2, 3}}
    out = hinter.index_domain_to_hints(result)
    assert sorted(out, key=lambda d: tuple(d.items())) == [
        {"A": 1}, {"A": 2}, {"A": 3}
    ]


def test_index_domain_to_hints_empty_dict(hinter: Hinter):
    assert hinter.index_domain_to_hints({}) == []


def test_index_domain_to_hints_key_with_empty_set(hinter: Hinter):
    result = {"A": set(), "B": {1}}
    out = hinter.index_domain_to_hints(result)
    assert out == []   # no combos possible


# ==========================================================
# take_hints_with_keys
# ==========================================================

def test_take_hints_with_keys_basic(hinter: Hinter):
    hints = [
        {"A": 1, "B": 2},
        {"B": 3, "C": 4},
        {"A": 5},
    ]

    out = hinter.take_hints_with_keys(hints, {"A", "C"})
    # keep only A or C keys
    assert sorted(out, key=lambda d: tuple(sorted(d.items()))) == [
        {"A": 1},
        {"A": 5},
        {"C": 4},
    ]


def test_take_hints_with_keys_empty_keys(hinter: Hinter):
    hints = [{"A": 1}, {"B": 2}]
    out = hinter.take_hints_with_keys(hints, set())
    assert out == [{}, {}]


def test_take_hints_with_keys_no_overlap(hinter: Hinter):
    hints = [{"A": 1}, {"B": 2}]
    out = hinter.take_hints_with_keys(hints, {"X", "Y"})
    assert out == [{}, {}]


def test_take_hints_with_keys_none_input(hinter: Hinter):
    out = hinter.take_hints_with_keys(None, {"A"})
    assert out == []


def test_take_hints_with_keys_duplicate(hinter: Hinter):
    hints = [{"A": 1}, {"A": 1, "B": 2}]
    out = hinter.take_hints_with_keys(hints, {"A"})
    assert out == [{"A": 1}, {"A": 1}]


# ==========================================================
# doublecheck
# ==========================================================


@pytest.fixture
def host_graph():
    G = nx.MultiDiGraph()

    # Nodes
    G.add_node("H1", __labels__={"Person"}, age=30)
    G.add_node("H2", __labels__={"Person"}, age=20)
    G.add_node("H3", __labels__={"Company"}, level=5)

    # Edges
    # H1 -> H2 with label "KNOWS"
    G.add_edge("H1", "H2", __labels__={"KNOWS"}, weight=3)

    # H2 -> H3 with label "WORKS_AT"
    G.add_edge("H2", "H3", __labels__={"WORKS_AT"}, since=2020)

    return G


@pytest.fixture
def motif_simple():
    G = nx.MultiDiGraph()
    G.add_node("A", __labels__={"Person"}, age=30)
    return G


@pytest.fixture
def motif_with_edge():
    G = nx.MultiDiGraph()
    G.add_node("A", __labels__={"Person"})
    G.add_node("B", __labels__={"Person"})
    G.add_edge("A", "B", __labels__={"KNOWS"}, weight=3)
    return G


@pytest.fixture
def motif_wrong_edge_label():
    G = nx.MultiDiGraph()
    G.add_node("A", __labels__={"Person"})
    G.add_node("B", __labels__={"Person"})
    G.add_edge("A", "B", __labels__={"FRIEND"}, weight=3)  # mismatch
    return G


def test_doublecheck_node_match(hinter, host_graph, motif_simple):
    """Node attributes match"""
    match = {"A": "H1"}  # H1 has age=30
    hints = [{"A": "H1"}]  # hints cause check on node A

    assert hinter.doublecheck(host_graph, motif_simple, match, hints) is True


def test_doublecheck_node_label_fail(hinter, host_graph):
    """Node label mismatch -> fails"""
    motif = nx.MultiDiGraph()
    motif.add_node("A", __labels__={"Company"})  # require Company
    match = {"A": "H1"}  # H1 is Person
    hints = [{"A": "H1"}]

    assert hinter.doublecheck(host_graph, motif, match, hints) is False


def test_doublecheck_node_attr_fail(hinter, host_graph):
    """Node attribute mismatch -> fails"""
    motif = nx.MultiDiGraph()
    motif.add_node("A", __labels__={"Person"}, age=999)
    match = {"A": "H1"}  # H1.age = 30
    hints = [{"A": "H1"}]

    assert hinter.doublecheck(host_graph, motif, match, hints) is False


def test_doublecheck_edge_match(hinter, host_graph, motif_with_edge):
    """edge matches"""
    match = {"A": "H1", "B": "H2"}  # H1->H2 has KNOWS, weight=3
    hints = [{"A": "H1", "B": "H2"}]

    assert hinter.doublecheck(host_graph, motif_with_edge, match, hints) is True


def test_doublecheck_edge_label_fail(hinter, host_graph, motif_wrong_edge_label):
    """edge label mismatch -> fails"""
    match = {"A": "H1", "B": "H2"}  # H1->H2 = KNOWS in host
    hints = [{"A": "H1", "B": "H2"}]

    assert hinter.doublecheck(host_graph, motif_wrong_edge_label, match, hints) is False


def test_doublecheck_edge_attr_fail(hinter: Hinter, host_graph):
    """Edge attribute mismatch -> fails"""
    motif = nx.MultiDiGraph()
    motif.add_node("A", __labels__={"Person"})
    motif.add_node("B", __labels__={"Person"})

    # Wrong labels
    motif.add_edge("A", "B", __labels__={"KNOWS"}, weight=999)

    match = {"A": "H1", "B": "H2"}
    hints = [{"A": "H1", "B": "H2"}]

    assert hinter.doublecheck(host_graph, motif, match, hints) is False


def test_doublecheck_edge_missing(hinter, host_graph):
    """edge exists in motif but not in host -> fails"""
    motif = nx.MultiDiGraph()
    motif.add_node("A", __labels__={"Person"})
    motif.add_node("B", __labels__={"Person"})
    motif.add_edge("A", "B", __labels__={"KNOWS"})  # A->B

    # Reverse match: host has H2->H1? No.
    match = {"A": "H2", "B": "H1"}
    hints = [{"A": "H2", "B": "H1"}]

    assert hinter.doublecheck(host_graph, motif, match, hints) is False


def test_doublecheck_partial_hints(hinter, host_graph, motif_with_edge):
    """Hints select only some nodes"""
    match = {"A": "H1", "B": "H2"}

    # Only check A, ignore B
    hints = [{"A": "H1"}]

    # Should pass: A matches (Person), edge is NOT checked
    assert hinter.doublecheck(host_graph, motif_with_edge, match, hints) is True


def test_doublecheck_no_hints(hinter, host_graph, motif_with_edge):
    """No hints → trivial true"""
    match = {"A": "H1", "B": "H2"}

    assert hinter.doublecheck(host_graph, motif_with_edge, match, hints=None) is True


def test_doublecheck_multiple_hints(hinter, host_graph, motif_with_edge):
    """Hint refers to multiple nodes"""
    match = {"A": "H1", "B": "H2"}

    hints = [{"A": "H1"}, {"B": "H2"}]

    assert hinter.doublecheck(host_graph, motif_with_edge, match, hints) is True

