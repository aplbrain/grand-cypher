import networkx as nx

# Adjust import paths as needed
from . import (
    _is_node_attr_match,
    _is_edge_attr_match,
)


class TestNodeAttrMatch:

    def setup_method(self):
        # Clear LRU cache to avoid cross-test contamination
        _is_node_attr_match.cache_clear()

    def test_basic_node_match(self):
        motif = nx.Graph()
        host = nx.Graph()

        motif.add_node("A", color="red")
        host.add_node("H", color="red")

        assert _is_node_attr_match("A", "H", motif, host) is True

    def test_basic_node_mismatch(self):
        motif = nx.Graph()
        host = nx.Graph()

        motif.add_node("A", color="red")
        host.add_node("H", color="blue")

        assert _is_node_attr_match("A", "H", motif, host) is False

    def test_missing_attribute_in_host(self):
        motif = nx.Graph()
        host = nx.Graph()

        motif.add_node("A", color="red")
        host.add_node("H")  # no 'color'

        assert _is_node_attr_match("A", "H", motif, host) is False

    def test_labels_match(self):
        motif = nx.Graph()
        host = nx.Graph()

        motif.add_node("A", __labels__={"Person"})
        host.add_node("H", __labels__={"Person", "Employee"})

        assert _is_node_attr_match("A", "H", motif, host) is True

    def test_labels_do_not_match(self):
        motif = nx.Graph()
        host = nx.Graph()

        motif.add_node("A", __labels__={"Person"})
        host.add_node("H", __labels__={"Company"})

        assert _is_node_attr_match("A", "H", motif, host) is False

    def test_empty_labels_in_motif_allows_any_host(self):
        motif = nx.Graph()
        host = nx.Graph()

        motif.add_node("A", __labels__=set())
        host.add_node("H", __labels__={"Anything"})

        assert _is_node_attr_match("A", "H", motif, host) is True


class TestEdgeAttrMatch:

    def setup_method(self):
        _is_edge_attr_match.cache_clear()

    def test_basic_edge_match(self):
        motif = nx.MultiDiGraph()
        host = nx.MultiDiGraph()

        motif.add_edge("A", "B", color="red")
        host.add_edge("H1", "H2", color="red")

        assert _is_edge_attr_match(("A", "B"), ("H1", "H2"), motif, host) is True

    def test_basic_edge_mismatch(self):
        motif = nx.MultiDiGraph()
        host = nx.MultiDiGraph()

        motif.add_edge("A", "B", weight=5)
        host.add_edge("H1", "H2", weight=10)

        assert _is_edge_attr_match(("A", "B"), ("H1", "H2"), motif, host) is False

    def test_edge_missing_in_host(self):
        motif = nx.MultiDiGraph()
        host = nx.MultiDiGraph()

        motif.add_edge("A", "B", color="red")
        # host has no edges

        assert _is_edge_attr_match(("A", "B"), ("H1", "H2"), motif, host) is False

    def test_labels_match(self):
        motif = nx.MultiDiGraph()
        host = nx.MultiDiGraph()

        motif.add_edge("A", "B", __labels__={"KNOWS"})
        host.add_edge("H1", "H2", __labels__={"KNOWS", "FRIEND"})

        assert _is_edge_attr_match(("A", "B"), ("H1", "H2"), motif, host) is True

    def test_labels_do_not_match(self):
        motif = nx.MultiDiGraph()
        host = nx.MultiDiGraph()

        motif.add_edge("A", "B", __labels__={"LIKES"})
        host.add_edge("H1", "H2", __labels__={"OWNS"})

        assert _is_edge_attr_match(("A", "B"), ("H1", "H2"), motif, host) is False

    def test_multiple_edges_any_match(self):
        motif = nx.MultiDiGraph()
        host = nx.MultiDiGraph()

        motif.add_edge("A", "B", color="red")
        host.add_edge("H1", "H2", color="blue")  # mismatch
        host.add_edge("H1", "H2", color="red")   # match

        assert _is_edge_attr_match(("A", "B"), ("H1", "H2"), motif, host) is True

    def test_multiple_edges_no_match(self):
        motif = nx.MultiDiGraph()
        host = nx.MultiDiGraph()

        motif.add_edge("A", "B", weight=100)
        host.add_edge("H1", "H2", weight=1)
        host.add_edge("H1", "H2", weight=2)
        host.add_edge("H1", "H2", weight=3)

        assert _is_edge_attr_match(("A", "B"), ("H1", "H2"), motif, host) is False

    def test_empty_labels_ignored(self):
        motif = nx.MultiDiGraph()
        host = nx.MultiDiGraph()

        motif.add_edge("A", "B", __labels__=set(), color="red")
        host.add_edge("H1", "H2", __labels__={"ANY"}, color="red")

        assert _is_edge_attr_match(("A", "B"), ("H1", "H2"), motif, host) is True
