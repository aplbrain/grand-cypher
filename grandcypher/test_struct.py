import networkx as nx

from .struct import (
    EdgeWithKey, HopSpec, EdgeMapping, EdgeHopKey, Match, EdgePath, UnionFind, unify_zero_hop_nodes, materialize_motif)


def test_edgepath_edges():
    ep = EdgePath(nodes=["A", "B", "C"], keys=[10, 20], hop_count=2)

    edges = ep.edges

    assert len(edges) == 2
    assert edges[0] == EdgeWithKey("A", "B", 10, 2)
    assert edges[1] == EdgeWithKey("B", "C", 20, 2)


def test_edgemapping_edgepath():
    hop_map = {
        ("A", "B"): HopSpec(edge_id=("A", "B"), nodes=["x1", "x2", "x3"], hop_count=5)
    }
    key_map = {
        ("A", "B"): EdgeHopKey(edge_id=("A", "B"), keys=(1, 2))
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
    hop_map = {("A", "B"): HopSpec(edge_id=("A", "B"), nodes=["x1", "x2"], hop_count=3)}
    key_map = {("A", "B"): EdgeHopKey(edge_id=("A", "B"), keys=(9,))}

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


class TestUnionFind:

    def test_single_find(self):
        uf = UnionFind()
        assert uf.find("a") == "a"
        assert uf.parent["a"] == "a"


    def test_simple_union(self):
        uf = UnionFind()
        uf.union("a", "b")
        # Both should have the same root
        root_a = uf.find("a")
        root_b = uf.find("b")
        assert root_a == root_b
        # Union is idempotent
        uf.union("a", "b")
        assert uf.find("a") == uf.find("b")


    def test_chain_union(self):
        uf = UnionFind()
        uf.union("a", "b")
        uf.union("b", "c")
        # All should have the same root
        root = uf.find("a")
        assert uf.find("b") == root
        assert uf.find("c") == root


    def test_multiple_disjoint_unions(self):
        uf = UnionFind()
        uf.union("a", "b")
        uf.union("c", "d")
        # Roots of different sets should be different
        root1 = uf.find("a")
        root2 = uf.find("c")
        assert root1 != root2
        # Union separate sets
        uf.union("b", "c")
        # Now all should have same root
        final_root = uf.find("a")
        for x in ["a","b","c","d"]:
            assert uf.find(x) == final_root


    def test_find_creates_node(self):
        uf = UnionFind()
        # Finding a node not in parent creates it
        assert uf.find("x") == "x"
        assert "x" in uf.parent


    def test_idempotent_union_chain(self):
        uf = UnionFind()
        uf.union("a", "b")
        uf.union("b", "c")
        first_root = uf.find("a")
        uf.union("a", "c")
        # Should still have same root
        assert uf.find("b") == first_root
        assert uf.find("c") == first_root


class TestUnifyZeroHopNodes:
    def _add_zero_hop_edge(self, g, u, v):
        g.add_node(u)
        g.add_node(v)


    def _add_normal_edge(self, g, u, v):
        g.add_edge(u, v, __min_hop__=1, __max_hop__=1, __labels__=["y"])
        g.add_node(u)
        g.add_node(v)


    def test_single_zero_hop_new(self):
        """
        Single zero-hop edge: U1 -> U2
        """
        g = nx.DiGraph()
        self._add_zero_hop_edge(g, "U1", "U2")
        paths = [
            HopSpec(edge_id=("U1", "U2"), nodes=("U1", "U1"), hop_count=0)
        ]

        new_g, alias = unify_zero_hop_nodes(g, paths)
        assert set(new_g.nodes) == {"U1"}
        assert list(new_g.edges) == []


    def test_chain_zero_hop_new(self):
        """
        Chain of zero-hop edges: A -> B -> C
        """
        g = nx.DiGraph()
        self._add_zero_hop_edge(g, "A", "B")
        self._add_zero_hop_edge(g, "B", "C")
        paths = [
            HopSpec(edge_id=("A", "B"), nodes=("A", "A"), hop_count=0),
            HopSpec(edge_id=("B", "C"), nodes=("B", "B"), hop_count=0)
        ]

        new_g, alias = unify_zero_hop_nodes(g, paths)
        assert set(new_g.nodes) == {"A"}
        assert list(new_g.edges) == []


    def test_branching_zero_hop_new(self):
        """
        Branching zero-hop edges: A -> B, A -> C
        """
        g = nx.DiGraph()
        self._add_zero_hop_edge(g, "A", "B")
        self._add_zero_hop_edge(g, "A", "C")
        paths = [
            HopSpec(edge_id=("A","B"), nodes=("A","A"), hop_count=0),
            HopSpec(edge_id=("A","C"), nodes=("A","A"), hop_count=0),
        ]

        new_g, alias = unify_zero_hop_nodes(g, paths)
        assert set(new_g.nodes) == {"A"}
        assert list(new_g.edges) == []


    def test_zero_hop_plus_normal_edge_new(self):
        """
        Mix zero-hop and normal edge: A -[*0]-> B, B -[*1]-> C
        """
        g = nx.DiGraph()
        self._add_zero_hop_edge(g, "A", "B")
        self._add_normal_edge(g, "B", "C")
        paths = {
            HopSpec(edge_id=("A","B"), nodes=("A","A"), hop_count=0)
        }

        new_g, alias = unify_zero_hop_nodes(g, paths)
        assert set(new_g.nodes) == {"A", "C"}
        edges = list(new_g.edges(data=True))
        assert len(edges) == 1
        u, v, data = edges[0]
        assert u == "A" and v == "C"
        assert data["__min_hop__"] == 1


    def test_multiple_zero_hop_edges_same_direction_new(self):
        """
        Multiple zero-hop edges in the same direction: A -> B twice
        """
        g = nx.DiGraph()
        self._add_zero_hop_edge(g, "A", "B")
        self._add_zero_hop_edge(g, "A", "B")
        paths = {
            HopSpec(edge_id=("A","B"), nodes=("A","A"), hop_count=0)
        }

        new_g, alias = unify_zero_hop_nodes(g, paths)
        assert set(new_g.nodes) == {"A"}
        assert list(new_g.edges) == []


    def test_multiple_independent_chains(self):
        """
        Multiple zero-hop chains: a->b->c and x->y
        """
        g = nx.DiGraph()
        self._add_zero_hop_edge(g, "a","b")
        self._add_zero_hop_edge(g, "b","c")
        self._add_zero_hop_edge(g, "x","y")
        paths = [
            HopSpec(edge_id=("a","b"), nodes=("a","a"), hop_count=0),
            HopSpec(edge_id=("b","c"), nodes=("b","b"), hop_count=0),
            HopSpec(edge_id=("x","y"), nodes=("x","x"), hop_count=0)
        ]

        new_g, alias = unify_zero_hop_nodes(g, paths)
        assert set(new_g.nodes) == {"a", "x"}


class TestMaterializeMotif:
    """Comprehensive tests for materialize_motif function."""

    def test_zero_hop_edge(self):
        """Test that zero-hop edges add nodes but no edges."""
        motif = nx.DiGraph()
        motif.add_node("A", type="Person", age=30)
        motif.add_node("B", type="Person", age=40)
        motif.add_edge("A", "B", __min_hop__=0, __max_hop__=0)

        hop_assignment = {
            ("A", "B"): HopSpec(
                edge_id=("A", "B"),
                nodes=("A", "A"),  # Zero-hop: same node
                hop_count=0
            )
        }

        result = materialize_motif(hop_assignment, motif)

        # Both nodes should exist
        assert set(result.nodes()) == {"A", "B"}
        # No edges should be added for zero-hop
        assert list(result.edges()) == []
        # Node attributes should be preserved
        assert result.nodes["A"]["type"] == "Person"
        assert result.nodes["A"]["age"] == 30
        assert result.nodes["B"]["type"] == "Person"

    def test_single_hop_edge(self):
        """Test that single-hop edges create one edge."""
        motif = nx.DiGraph()
        motif.add_node("A", name="Alice")
        motif.add_node("B", name="Bob")
        motif.add_edge("A", "B", __labels__={"KNOWS"}, since=2020)

        hop_assignment = {
            ("A", "B"): HopSpec(
                edge_id=("A", "B"),
                nodes=("A", "B"),
                hop_count=1
            )
        }

        result = materialize_motif(hop_assignment, motif)

        assert set(result.nodes()) == {"A", "B"}
        assert list(result.edges()) == [("A", "B")]
        # Check edge attributes preserved (except hop metadata)
        edge_data = result.get_edge_data("A", "B")
        assert "__labels__" in edge_data
        assert edge_data["since"] == 2020
        assert "__min_hop__" not in edge_data  # Hop metadata should be removed

    def test_multi_hop_edge(self):
        """Test that multi-hop edges expand correctly with intermediate nodes."""
        motif = nx.DiGraph()
        motif.add_node("A", type="Start")
        motif.add_node("C", type="End")
        motif.add_edge("A", "C", __min_hop__=2, __max_hop__=3, __labels__={"PATH"})

        # 2-hop path: A -> _h1 -> C
        hop_assignment = {
            ("A", "C"): HopSpec(
                edge_id=("A", "C"),
                nodes=("A", "_h1", "C"),
                hop_count=2
            )
        }

        result = materialize_motif(hop_assignment, motif)

        # Should have A, C, and intermediate node _h1
        assert set(result.nodes()) == {"A", "_h1", "C"}
        # Should have two edges
        assert set(result.edges()) == {("A", "_h1"), ("_h1", "C")}
        # Original node attributes preserved
        assert result.nodes["A"]["type"] == "Start"
        assert result.nodes["C"]["type"] == "End"
        # Intermediate node has no attributes
        assert result.nodes["_h1"] == {}
        # Edge attributes preserved on all expanded edges
        for edge in [("A", "_h1"), ("_h1", "C")]:
            edge_data = result.get_edge_data(*edge)
            assert "__labels__" in edge_data
            assert edge_data["__labels__"] == {"PATH"}

    def test_three_hop_edge(self):
        """Test 3-hop expansion: A -> x1 -> x2 -> B."""
        motif = nx.DiGraph()
        motif.add_node("A")
        motif.add_node("B")
        motif.add_edge("A", "B", __labels__={"CONNECTED"})

        hop_assignment = {
            ("A", "B"): HopSpec(
                edge_id=("A", "B"),
                nodes=("A", "x1", "x2", "B"),
                hop_count=3
            )
        }

        result = materialize_motif(hop_assignment, motif)

        assert set(result.nodes()) == {"A", "x1", "x2", "B"}
        assert set(result.edges()) == {("A", "x1"), ("x1", "x2"), ("x2", "B")}

    def test_multiple_edges(self):
        """Test materialization with multiple edges in the motif."""
        motif = nx.DiGraph()
        motif.add_node("A", id=1)
        motif.add_node("B", id=2)
        motif.add_node("C", id=3)
        motif.add_edge("A", "B", type="friend")
        motif.add_edge("B", "C", type="colleague")

        hop_assignment = {
            ("A", "B"): HopSpec(
                edge_id=("A", "B"),
                nodes=("A", "B"),
                hop_count=1
            ),
            ("B", "C"): HopSpec(
                edge_id=("B", "C"),
                nodes=("B", "h1", "C"),  # 2 hops
                hop_count=2
            )
        }

        result = materialize_motif(hop_assignment, motif)

        assert "A" in result.nodes()
        assert "B" in result.nodes()
        assert "C" in result.nodes()
        assert "h1" in result.nodes()  # Intermediate node
        assert ("A", "B") in result.edges()
        assert ("B", "h1") in result.edges()
        assert ("h1", "C") in result.edges()

    def test_isolated_node_preserved(self):
        """Test that isolated nodes (no edges) are preserved."""
        motif = nx.DiGraph()
        motif.add_node("A", name="Alice")
        motif.add_node("B", name="Bob")
        motif.add_node("Isolated", name="Lonely")  # No edges to/from this node

        hop_assignment = {
            ("A", "B"): HopSpec(
                edge_id=("A", "B"),
                nodes=("A", "B"),
                hop_count=1
            )
        }

        result = materialize_motif(hop_assignment, motif)

        # Isolated node should be preserved
        assert "Isolated" in result.nodes()
        assert result.nodes["Isolated"]["name"] == "Lonely"

    def test_edge_without_labels(self):
        """Test that edges without __labels__ get an empty set."""
        motif = nx.DiGraph()
        motif.add_node("A")
        motif.add_node("B")
        # Edge without __labels__
        motif.add_edge("A", "B", weight=10)

        hop_assignment = {
            ("A", "B"): HopSpec(
                edge_id=("A", "B"),
                nodes=("A", "B"),
                hop_count=1
            )
        }

        result = materialize_motif(hop_assignment, motif)

        edge_data = result.get_edge_data("A", "B")
        assert "__labels__" in edge_data
        assert edge_data["__labels__"] == set()
        assert edge_data["weight"] == 10

    def test_hop_metadata_removed(self):
        """Test that hop metadata is removed from edge attributes."""
        motif = nx.DiGraph()
        motif.add_node("A")
        motif.add_node("B")
        motif.add_edge("A", "B", __min_hop__=1, __max_hop__=3, __is_hop__=True, weight=5)

        hop_assignment = {
            ("A", "B"): HopSpec(
                edge_id=("A", "B"),
                nodes=("A", "B"),
                hop_count=1
            )
        }

        result = materialize_motif(hop_assignment, motif)

        edge_data = result.get_edge_data("A", "B")
        # Hop metadata should be removed
        assert "__min_hop__" not in edge_data
        assert "__max_hop__" not in edge_data
        assert "__is_hop__" not in edge_data
        # Other attributes preserved
        assert edge_data["weight"] == 5

    def test_mixed_zero_and_nonzero_hops(self):
        """Test motif with both zero-hop and non-zero-hop edges."""
        motif = nx.DiGraph()
        motif.add_node("A", id=1)
        motif.add_node("B", id=2)
        motif.add_node("C", id=3)
        motif.add_edge("A", "B", rel="zero")
        motif.add_edge("B", "C", rel="normal")

        hop_assignment = {
            ("A", "B"): HopSpec(
                edge_id=("A", "B"),
                nodes=("A", "A"),  # Zero-hop
                hop_count=0
            ),
            ("B", "C"): HopSpec(
                edge_id=("B", "C"),
                nodes=("B", "C"),  # 1-hop
                hop_count=1
            )
        }

        result = materialize_motif(hop_assignment, motif)

        # All nodes should exist
        assert set(result.nodes()) == {"A", "B", "C"}
        # Only the 1-hop edge should exist
        assert list(result.edges()) == [("B", "C")]
        # Attributes preserved
        assert result.nodes["A"]["id"] == 1
        assert result.nodes["B"]["id"] == 2

    def test_complex_pattern(self):
        """Test a complex pattern with multiple path lengths."""
        motif = nx.DiGraph()
        for node in ["A", "B", "C", "D"]:
            motif.add_node(node, type="Node")
        motif.add_edge("A", "B", rel="r1")
        motif.add_edge("B", "C", rel="r2")
        motif.add_edge("C", "D", rel="r3")

        hop_assignment = {
            ("A", "B"): HopSpec(
                edge_id=("A", "B"),
                nodes=("A", "B"),  # 1-hop
                hop_count=1
            ),
            ("B", "C"): HopSpec(
                edge_id=("B", "C"),
                nodes=("B", "C"),  # 1-hop
                hop_count=1
            ),
            ("C", "D"): HopSpec(
                edge_id=("C", "D"),
                nodes=("C", "x1", "x2", "D"),  # 3-hop
                hop_count=3
            )
        }

        result = materialize_motif(hop_assignment, motif)

        expected_nodes = {"A", "B", "C", "D", "x1", "x2"}
        assert set(result.nodes()) == expected_nodes

        expected_edges = {("A", "B"), ("B", "C"), ("C", "x1"), ("x1", "x2"), ("x2", "D")}
        assert set(result.edges()) == expected_edges

        # All original nodes have attributes
        for node in ["A", "B", "C", "D"]:
            assert result.nodes[node]["type"] == "Node"
        # Intermediate nodes don't
        assert result.nodes["x1"] == {}
        assert result.nodes["x2"] == {}
