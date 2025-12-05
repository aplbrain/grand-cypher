import networkx as nx
from grandcypher.struct import EdgeHopKey, EdgeWithKey, HopSpec
import pytest

from . import GrandCypher, find_multiedge_keys, generate_multiedge_edge_hop_key, get_edge_from_host

ACCEPTED_GRAPH_TYPES = [nx.MultiDiGraph, nx.DiGraph]


class TestSimpleAPI:
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_simple_api(self, graph_type):
        host = graph_type()
        host.add_edge("x", "y")
        host.add_edge("y", "z")
        host.add_node("x", dinnertime="no thanks I already ate")

        qry = """
        MATCH (A)-[B]->(C)
        RETURN A.dinnertime
        """

        assert len(GrandCypher(host).run(qry)["A.dinnertime"]) == 2

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_simple_api_triangles(self, graph_type):
        host = graph_type()
        host.add_edge("x", "y")
        host.add_edge("y", "z")
        host.add_edge("z", "x")

        qry = """
        MATCH (A)-[AB]->(B)
        MATCH (B)-[BC]->(C)
        MATCH (C)-[CA]->(A)
        RETURN A
        """

        assert len(GrandCypher(host).run(qry)["A"]) == 3

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_simple_api_single_node_where(self, graph_type):
        host = graph_type()
        host.add_edge("x", "y")
        host.add_edge("y", "z")
        host.add_edge("z", "x")
        host.add_node("x", foo="bar")

        qry = """
        MATCH (A)-[X]->(B)
        WHERE A.foo == "bar"
        RETURN A
        """

        assert len(GrandCypher(host).run(qry)["A"]) == 1

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_simple_api_single_node_multi_where(self, graph_type):
        host = graph_type()
        host.add_edge("x", "y")
        host.add_edge("y", "z")
        host.add_edge("z", "x")
        host.add_node("x", foo="bar")

        qry = """
        MATCH (A)-[X]->(B)
        WHERE A.foo == "bar"
        AND A.foo <> "baz"
        RETURN A
        """

        assert len(GrandCypher(host).run(qry)["A"]) == 1

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_simple_api_single_node_multi_where_2(self, graph_type):
        host = graph_type()
        host.add_edge("x", "y")
        host.add_edge("y", "z")
        host.add_edge("z", "x")
        host.add_node("x", foo=12)
        host.add_node("y", foo=13)
        host.add_node("z", foo=16)

        qry = """
        MATCH (A)-[X]->(B)
        WHERE A.foo > 10
        AND A.foo < 15
        RETURN A
        """

        assert len(GrandCypher(host).run(qry)["A"]) == 2

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_null_where(self, graph_type):
        host = graph_type()
        host.add_node("x", foo="foo")
        host.add_node("y")
        host.add_node("z")

        qry = """
        MATCH (A)
        WHERE A.foo iS nUlL
        RETURN A.foo
        """
        assert len(GrandCypher(host).run(qry)["A.foo"]) == 2

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_simple_api_multi_node_multi_where(self, graph_type):
        host = graph_type()
        host.add_edge("x", "y")
        host.add_edge("y", "z")
        host.add_edge("z", "x")
        host.add_node("x", foo=12)
        host.add_node("y", foo=13)
        host.add_node("z", foo=16)

        qry = """
        MATCH (A)-[X]->(B)
        WHERE A.foo == 12
        AND B.foo == 13
        RETURN A
        """

        assert len(GrandCypher(host).run(qry)["A"]) == 1

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_simple_api_anonymous_edge(self, graph_type):
        host = graph_type()
        host.add_edge("x", "y")
        host.add_edge("y", "z")
        host.add_edge("z", "x")

        qry = """
        MATCH (A)-[]->(B)
        RETURN A
        """

        assert len(GrandCypher(host).run(qry)["A"]) == 3

        qry = """
        MATCH (A)<-[]-(B)
        RETURN A
        """

        assert len(GrandCypher(host).run(qry)["A"]) == 3

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_simple_api_anonymous_node(self, graph_type):
        host = graph_type()
        host.add_edge("x", "y")
        host.add_edge("y", "z")
        host.add_edge("x", "z")

        qry = """
        MATCH () -[]-> (B)
        RETURN ID(B)
        """
        res = GrandCypher(host).run(qry)
        assert len(res) == 1
        assert list(res.values())[0] == ["y", "z", "z"]

        qry = """
        MATCH () <-[]- (B)
        RETURN ID(B)
        """
        res = GrandCypher(host).run(qry)
        assert len(res) == 1
        assert list(res.values())[0] == ["x", "x", "y"]

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_single_edge_where(self, graph_type):
        host = graph_type()
        host.add_edge("y", "z")

        qry = """
        MATCH (A)-[AB]->(B)
        RETURN AB
        """

        assert len(GrandCypher(host).run(qry)["AB"]) == 1

        qry = """
        MATCH (A)<-[AB]-(B)
        RETURN AB
        """

        assert len(GrandCypher(host).run(qry)["AB"]) == 1

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_simple_api_single_edge_where(self, graph_type):
        host = graph_type()
        host.add_edge("x", "y")
        host.add_edge("y", "z", foo="bar")
        host.add_edge("z", "x")

        qry = """
        MATCH (A)-[AB]->(B)
        WHERE AB.foo == "bar"
        RETURN A
        """

        assert len(GrandCypher(host).run(qry)["A"]) == 1

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_simple_api_two_edge_where_clauses_same_edge(self, graph_type):
        host = graph_type()
        host.add_edge("x", "y")
        host.add_edge("y", "z", foo="bar", weight=12)
        host.add_edge("z", "x")

        qry = """
        MATCH (A)-[AB]->(B)
        WHERE AB.foo == "bar"
        AND AB.weight > 11
        RETURN AB
        """

        assert len(GrandCypher(host).run(qry)["AB"]) == 1

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_simple_api_two_edge_where_clauses_diff_edge(self, graph_type):
        host = graph_type()
        host.add_edge("x", "y")
        host.add_edge("y", "z", foo="bar")
        host.add_edge("z", "x", weight=12)

        qry = """
        MATCH (A)-[AB]->(B)
        MATCH (B)-[BC]->(C)
        WHERE AB.foo == "bar"
        AND BC.weight > 11
        RETURN AB
        """
        assert len(GrandCypher(host).run(qry)["AB"]) == 1


class TestKarate:
    @pytest.mark.benchmark
    def test_simple_multi_edge(self):
        qry = """
        MATCH (A)-[]->(B)
        MATCH (B)-[]->(C)
        WHERE A.club == "Mr. Hi"
        RETURN A.club, B.club
        """
        assert len(GrandCypher(nx.karate_club_graph()).run(qry)["A.club"]) == 544


class TestDictAttributes:
    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_node_dict(self, graph_type):
        qry = """
        MATCH (A {type: "foo"})-[]->(B)
        RETURN A
        """
        host = graph_type()
        host.add_node("Y", type="foo")
        host.add_node("X", type="bar")
        host.add_edge("X", "Y")
        host.add_edge("Y", "Z", type="foo")
        host.add_edge("X", "Z", type="bar")

        assert len(GrandCypher(host).run(qry)["A"]) == 1

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_null_value(self, graph_type):
        host = graph_type()
        host.add_node("x", foo="foo")
        host.add_node("y")
        host.add_node("z")

        qry = """
        MATCH (A{foo:NuLl})
        RETURN A.foo
        """
        assert len(GrandCypher(host).run(qry)["A.foo"]) == 2


class TestLimitSkip:
    @pytest.mark.benchmark
    def test_limit_only(self):
        qry = """
        MATCH (A)-[]->(B)
        MATCH (B)-[]->(C)
        WHERE A.club == "Mr. Hi"
        RETURN A.club, B.club
        LIMIT 10
        """
        assert len(GrandCypher(nx.karate_club_graph()).run(qry)["A.club"]) == 10

    @pytest.mark.benchmark
    def test_skip_only(self):
        qry = """
        MATCH (A)-[]->(B)
        MATCH (B)-[]->(C)
        WHERE A.club == "Mr. Hi"
        RETURN A.club, B.club
        SKIP 10
        """
        assert len(GrandCypher(nx.karate_club_graph()).run(qry)["A.club"]) == 544 - 10

    @pytest.mark.benchmark
    def test_skip_and_limit(self):
        base_qry_for_comparison = """
        MATCH (A)-[]->(B)
        MATCH (B)-[]->(C)
        WHERE A.club == "Mr. Hi"
        RETURN A.club, B.club
        """

        qry = """
        MATCH (A)-[]->(B)
        MATCH (B)-[]->(C)
        WHERE A.club == "Mr. Hi"
        RETURN A.club, B.club
        SKIP 10 LIMIT 10
        """
        results = GrandCypher(nx.karate_club_graph()).run(qry)["A.club"]
        assert len(results) == 10
        assert (
            results
            == GrandCypher(nx.karate_club_graph()).run(base_qry_for_comparison)[
                "A.club"
            ][10:20]
        )

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_single_node_query(self, graph_type):
        """
        Test that you can search for individual nodes with properties
        """

        qry = """
        MATCH (c)
        WHERE c.name = "London"
        RETURN c
        """

        host = graph_type()
        host.add_node("London", type="City", name="London")

        assert len(GrandCypher(host).run(qry)["c"]) == 1

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_multi_node_query(self, graph_type):
        """
        Test that you can search for individual nodes with properties
        """

        qry = """
        MATCH (c)-[]->(b)
        WHERE c.name = "London"
        AND b.type = "City"
        RETURN b, c
        """

        host = graph_type()
        host.add_node("London", type="City", name="London")
        host.add_node("NYC", type="City", name="NYC")
        host.add_edge("London", "NYC")

        assert len(GrandCypher(host).run(qry)["c"]) == 1

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_left_or_right_direction_with_where(self, graph_type):
        host = graph_type()
        host.add_node("x", name="x")
        host.add_node("y", name="y")
        host.add_node("z", name="z")

        host.add_edge("x", "y", foo="bar")
        host.add_edge("z", "y")

        qry = """Match (A{name:"x"}) -[AB]-> (B) return B.name"""
        res = GrandCypher(host).run(qry)
        assert len(res) == 1
        assert list(res.values())[0] == ["y"]

        qry = """Match (A{name:"y"}) <-[AB]- (B) return B.name"""
        res = GrandCypher(host).run(qry)
        assert len(res) == 1
        assert list(res.values())[0] == ["x", "z"]

        qry = """Match (A{name:"y"}) <-[AB]- (B) where AB.foo == "bar" return B.name"""
        res = GrandCypher(host).run(qry)
        assert len(res) == 1
        assert list(res.values())[0] == ["x"]

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_disconected_multi_match(self, graph_type):
        host = graph_type()
        host.add_node("x", name="x")
        host.add_node("y", name="y")
        host.add_node("z", name="z")
        host.add_edge("x", "y")
        host.add_edge("y", "z")

        qry = """match (A) -[]-> (B) match (C) -[]-> (D) return A.name, B.name, C.name, D.name"""
        res = GrandCypher(host).run(qry)
        assert len(res) == 4
        assert res["A.name"] == ["x", "x", "y", "y"]
        assert res["B.name"] == ["y", "y", "z", "z"]
        assert res["C.name"] == ["x", "y", "x", "y"]
        assert res["D.name"] == ["y", "z", "y", "z"]

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_chained_edges(self, graph_type):
        host = graph_type()
        host.add_node("x", name="x")
        host.add_node("y", name="y")
        host.add_node("z", name="z")
        host.add_edge("x", "y")
        host.add_edge("y", "z")

        qry = (
            """Match (A{name:"x"}) -[]-> (B) -[]-> (C) return A.name, B.name, C.name"""
        )
        res = GrandCypher(host).run(qry)
        assert len(res) == 3
        assert res["A.name"] == ["x"]
        assert res["B.name"] == ["y"]
        assert res["C.name"] == ["z"]

        qry = (
            """Match (A{name:"y"}) -[]-> (B) -[]-> (C) return A.name, B.name, C.name"""
        )
        res = GrandCypher(host).run(qry)
        assert len(res) == 3
        assert res["A.name"] == []
        assert res["B.name"] == []
        assert res["C.name"] == []

        qry = (
            """Match (A) -[]-> (B{name:"y"}) -[]-> (C) return A.name, B.name, C.name"""
        )
        res = GrandCypher(host).run(qry)
        assert len(res) == 3
        assert res["A.name"] == ["x"]
        assert res["B.name"] == ["y"]
        assert res["C.name"] == ["z"]

        qry = """Match (A) -[]-> (B) -[]-> (C) where B.name == "y" return A.name, B.name, C.name"""
        res = GrandCypher(host).run(qry)
        assert len(res) == 3
        assert res["A.name"] == ["x"]
        assert res["B.name"] == ["y"]
        assert res["C.name"] == ["z"]

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_chained_backward_edges(self, graph_type):
        host = graph_type()
        host.add_node("x", name="x")
        host.add_node("y", name="y")
        host.add_node("z", name="z")
        host.add_edge("x", "y")
        host.add_edge("z", "y")

        qry = (
            """Match (A{name:"x"}) -[]-> (B) -[]-> (C) return A.name, B.name, C.name"""
        )
        res = GrandCypher(host).run(qry)
        assert len(res) == 3
        assert res["A.name"] == []
        assert res["B.name"] == []
        assert res["C.name"] == []

        qry = (
            """Match (A) -[]-> (B{name:"y"}) -[]-> (C) return A.name, B.name, C.name"""
        )
        res = GrandCypher(host).run(qry)
        assert len(res) == 3
        assert res["A.name"] == []
        assert res["B.name"] == []
        assert res["C.name"] == []

        qry = """Match (A{name:"x"}) -[]-> (B) -[]-> (C) where B.name == "y" return A.name, B.name, C.name"""
        res = GrandCypher(host).run(qry)
        assert len(res) == 3
        assert res["A.name"] == []
        assert res["B.name"] == []
        assert res["C.name"] == []

        qry = (
            """Match (A{name:"x"}) -[]-> (B) <-[]- (C) return A.name, B.name, C.name"""
        )
        res = GrandCypher(host).run(qry)
        assert len(res) == 3
        assert res["A.name"] == ["x"]
        assert res["B.name"] == ["y"]
        assert res["C.name"] == ["z"]

        qry = (
            """Match (A) -[]-> (B{name:"y"}) <-[]- (C) return A.name, B.name, C.name"""
        )
        res = GrandCypher(host).run(qry)
        assert len(res) == 3
        assert res["A.name"] == ["x", "z"]
        assert res["B.name"] == ["y", "y"]
        assert res["C.name"] == ["z", "x"]

        qry = """Match (A) -[]-> (B) <-[]- (C) where C.name == "z" return A.name, B.name, C.name"""
        res = GrandCypher(host).run(qry)
        assert len(res) == 3
        assert res["A.name"] == ["x"]
        assert res["B.name"] == ["y"]
        assert res["C.name"] == ["z"]

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_undirected(self, graph_type):
        host = graph_type()
        host.add_node("x", name="x")
        host.add_node("y", name="y")
        host.add_node("z", name="z")
        host.add_edge("x", "y", foo="bar")
        host.add_edge("y", "x")
        host.add_edge("y", "z")

        qry = """Match (A) -[]- (B) return A.name, B.name"""
        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["A.name"] == ["x", "y"]
        assert res["B.name"] == ["y", "x"]

        qry = """Match (A) <--> (B) return A.name, B.name"""
        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["A.name"] == ["x", "y"]
        assert res["B.name"] == ["y", "x"]

        qry = """Match (A) -[r]- (B) where r.foo == "bar" return A.name, B.name"""
        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["A.name"] == ["x"]
        assert res["B.name"] == ["y"]

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_anonymous_node(self, graph_type):
        host = graph_type()
        host.add_node("x", name="x")
        host.add_node("y", name="y")
        host.add_node("z", name="z")

        host.add_edge("x", "y")
        host.add_edge("z", "y")

        qry = """Match () -[]-> (B) <-[]- ()  return B.name"""
        res = GrandCypher(host).run(qry)
        assert len(res) == 1
        assert res["B.name"] == ["y", "y"]

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_complex_where(self, graph_type):
        host = graph_type()
        host.add_node("x", foo=12)
        host.add_node("y", foo=13)
        host.add_node("z", foo=16)
        host.add_edge("x", "y", bar="1")
        host.add_edge("y", "z", bar="2")
        host.add_edge("z", "x", bar="3")
        qry = """
        MATCH (A)-[X]->(B)
        WHERE A.foo == 12 Or (B.foo>13 aNd X.bar>="2")
        RETURN A, B
        """
        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["A"] == [{"foo": 12}, {"foo": 13}]
        assert res["B"] == [{"foo": 13}, {"foo": 16}]


class TestDistinct:
    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_basic_distinct1(self, graph_type):
        host = graph_type()
        host.add_node("a", name="Alice")
        host.add_node("b", name="Bob")
        host.add_node("c", name="Alice")  # duplicate name

        qry = """
        MATCH (n)
        RETURN DISTINCT n.name
        """
        res = GrandCypher(host).run(qry)
        assert len(res["n.name"]) == 2  # should return "Alice" and "Bob" only once
        assert "Alice" in res["n.name"] and "Bob" in res["n.name"]

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_basic_distinct2(self, graph_type):
        host = graph_type()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=25)
        host.add_node("c", name="Carol", age=21)
        host.add_node("d", name="Alice", age=25)
        host.add_node("e", name="Greg", age=32)

        qry = """
        MATCH (n)
        RETURN DISTINCT n.name
        """
        res = GrandCypher(host).run(qry)
        assert len(res["n.name"]) == 4  # should return "Alice" and "Bob" only once
        assert (
            "Alice" in res["n.name"]
            and "Bob" in res["n.name"]
            and "Carol" in res["n.name"]
            and "Greg" in res["n.name"]
        )

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_distinct_with_relationships(self, graph_type):
        host = graph_type()
        host.add_node("a", name="Alice")
        host.add_node("b", name="Bob")
        host.add_node("c", name="Alice")  # duplicate name
        host.add_edge("a", "b")
        host.add_edge("c", "b")

        qry = """
        MATCH (n)-[]->(b)
        RETURN DISTINCT n.name
        """
        res = GrandCypher(host).run(qry)
        assert len(res["n.name"]) == 1  # should return "Alice" only once
        assert res["n.name"] == ["Alice"]

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_distinct_with_limit_and_skip(self, graph_type):
        host = graph_type()
        for i in range(5):
            host.add_node(f"a{i}", name="Alice")
            host.add_node(f"b{i}", name="Bob")

        qry = """
        MATCH (n)
        RETURN DISTINCT n.name SKIP 1 LIMIT 1
        """
        res = GrandCypher(host).run(qry)
        assert len(res["n.name"]) == 1  # only one name should be returned
        assert res["n.name"] == ["Bob"]  # assuming alphabetical order

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_distinct_on_complex_graph(self, graph_type):
        host = graph_type()
        host.add_node("a", name="Alice")
        host.add_node("b", name="Bob")
        host.add_node("c", name="Carol")
        host.add_node("d", name="Alice")  # duplicate name
        host.add_edge("a", "b")
        host.add_edge("b", "c")
        host.add_edge("c", "d")

        qry = """
        MATCH (n)-[]->(m)
        RETURN DISTINCT n.name, m.name
        """
        res = GrandCypher(host).run(qry)
        assert (
            len(res["n.name"]) == 3
        )  # should account for paths without considering duplicate names
        assert (
            "Alice" in res["n.name"]
            and "Bob" in res["n.name"]
            and "Carol" in res["n.name"]
        )
        assert (
            len(res["m.name"]) == 3
        )  # should account for paths without considering duplicate names

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_distinct_with_attributes(self, graph_type):
        host = graph_type()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Alice", age=30)  # same name, different attribute
        host.add_node("c", name="Bob", age=25)

        qry = """
        MATCH (n)
        WHERE n.age > 20
        RETURN DISTINCT n.name
        """
        res = GrandCypher(host).run(qry)
        assert len(res["n.name"]) == 2  # "Alice" and "Bob" should be distinct
        assert "Alice" in res["n.name"] and "Bob" in res["n.name"]


class TestOrderBy:
    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_order_by_single_field_ascending(self, graph_type):
        host = graph_type()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=20)

        qry = """
        MATCH (n)
        RETURN n.name
        ORDER BY n.age ASC
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Carol", "Alice", "Bob"]

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_order_by_single_field_descending(self, graph_type):
        host = graph_type()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=20)

        qry = """
        MATCH (n)
        RETURN n.name
        ORDER BY n.age DESC
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Bob", "Alice", "Carol"]

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_order_by_single_field_no_direction_provided(self, graph_type):
        host = graph_type()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=20)

        qry = """
        MATCH (n)
        RETURN n.name
        ORDER BY n.age
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Carol", "Alice", "Bob"]

    @pytest.mark.benchmark
    def test_order_by_edge_attribute1(self):
        host = nx.DiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=20)
        host.add_edge("b", "a", __labels__={"paid"}, value=14)
        host.add_edge("a", "b", __labels__={"paid"}, value=9)
        host.add_edge("a", "c", __labels__={"paid"}, value=4)

        qry = """
        MATCH (n)-[r]->(m)
        RETURN n.name, r.value, m.name
        ORDER BY r.value ASC
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Alice", "Alice", "Bob"]
        assert res["m.name"] == ["Carol", "Bob", "Alice"]
        assert res["r.value"] == [4,  9, 14]

        qry = """
        MATCH (n)-[r]->()
        RETURN n.name, r.value
        ORDER BY r.value DESC
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Bob", "Alice", "Alice"]
        assert res["r.value"] == [14, 9, 4]

    @pytest.mark.benchmark
    def test_order_by_edge_attribute2(self):
        host = nx.DiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=20)
        host.add_edge(
            "b", "a", __labels__={"paid"}, amount=14
        )  # different attribute name
        host.add_edge("a", "b", __labels__={"paid"}, value=9)
        host.add_edge("c", "b", __labels__={"paid"}, value=980)
        host.add_edge("b", "c", __labels__={"paid"}, value=11)

        qry = """
        MATCH (n)-[r]->(m)
        RETURN n.name, r.value, m.name
        ORDER BY r.value ASC
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Alice", "Bob", "Carol", "Bob"]
        assert res["r.value"] == [9, 11, 980, None]
        assert res["m.name"] == ["Bob", "Carol", "Bob", "Alice"]

    @pytest.mark.benchmark
    def test_order_by_aggregation_function(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=20)
        host.add_edge("b", "a", __labels__={"paid"}, value=14)
        host.add_edge("a", "b", __labels__={"paid"}, value=9)
        host.add_edge("a", "b", __labels__={"paid"}, amount=96)
        host.add_edge("a", "b", __labels__={"paid"}, value=40)

        # SUM
        qry = """
        MATCH (n)-[r]->()
        RETURN n.name, SUM(r.value)
        ORDER BY SUM(r.value) ASC
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Bob", "Alice"]
        assert res["SUM(r.value)"] == [14, 49]

        # AVG
        # TODO: This query in comment should throw an error instead of returning r.value.
        # qry = """
        # MATCH (n)-[r]->()
        # RETURN n.name, AVG(r.value), r.value
        # ORDER BY AVG(r.value) DESC
        # """
        qry = """
        MATCH (n)-[r]->()
        RETURN n.name, AVG(r.value), r.value
        ORDER BY AVG(r.value) DESC
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Alice", "Bob"]
        assert res["AVG(r.value)"] == [16.333333333333332, 14.0]

        # MIN, MAX, and COUNT
        qry = """
        MATCH (n)-[r]->()
        RETURN n.name, MIN(r.value), MAX(r.value), COUNT(r.value)
        ORDER BY MAX(r.value) DESC
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Alice", "Bob"]
        assert res["MIN(r.value)"] == [9, 14]
        assert res["MAX(r.value)"] == [40, 14]
        assert res["COUNT(r.value)"] == [2, 1]  # COUNT excludes None values

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_order_by_aggregation_fails_if_not_requested_in_return(self, graph_type):
        host = graph_type()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=20)
        host.add_edge("b", "a", __labels__={"paid"}, value=14)
        host.add_edge("a", "b", __labels__={"paid"}, value=9)
        host.add_edge("a", "b", __labels__={"paid"}, amount=96)
        host.add_edge("a", "b", __labels__={"paid"}, value=40)

        qry = """
        MATCH (n)-[r]->()
        RETURN n.name, r.value
        ORDER BY SUM(r.value) ASC
        """
        with pytest.raises(Exception):
            GrandCypher(host).run(qry)

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_order_by_multiple_fields(self, graph_type):
        host = graph_type()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=25)
        host.add_node("d", name="Dave", age=25)

        qry = """
        MATCH (n)
        RETURN n.name
        ORDER BY n.age ASC, n.name DESC
        """
        res = GrandCypher(host).run(qry)
        # names sorted in descending order where ages are the same
        assert res["n.name"] == ["Dave", "Carol", "Alice", "Bob"]

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_order_by_with_limit(self, graph_type):
        host = graph_type()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=20)

        qry = """
        MATCH (n)
        RETURN n.name
        ORDER BY n.age ASC LIMIT 2
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Carol", "Alice"]

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_order_by_with_skip(self, graph_type):
        host = graph_type()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=20)

        qry = """
        MATCH (n)
        RETURN n.name
        ORDER BY n.age ASC SKIP 1
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Alice", "Bob"]

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_order_by_with_distinct(self, graph_type):
        host = graph_type()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=25)
        host.add_node("d", name="Alice", age=25)
        host.add_node("e", name="Greg", age=32)

        qry = """
        MATCH (n)
        RETURN DISTINCT n.name, n.age
        ORDER BY n.age DESC
        """
        res = GrandCypher(host).run(qry)
        # Distinct names, ordered by age where available
        assert res["n.name"] == ["Greg", "Bob", "Alice", "Carol"]
        assert res["n.age"] == [32, 30, 25, 25]

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_error_on_order_by_with_distinct_and_non_returned_field(self, graph_type):
        host = graph_type()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=25)
        host.add_node("d", name="Alice", age=25)
        host.add_node("e", name="Greg", age=32)

        qry = """
        MATCH (n)
        RETURN DISTINCT n.name
        ORDER BY n.age DESC
        """
        # Expect an error since 'n.age' is not included in the RETURN clause but used in ORDER BY
        with pytest.raises(Exception):
            GrandCypher(host).run(qry)

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_order_by_with_non_returned_field(self, graph_type):
        host = graph_type()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=20)

        qry = """
        MATCH (n)
        RETURN n.name ORDER BY n.age ASC
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Carol", "Alice", "Bob"]


class TestMultigraphRelations:
    @pytest.mark.benchmark
    def test_query_with_multiple_relations(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Charlie", age=25)
        host.add_node("d", name="Diana", age=25)

        # Adding edges with labels for different types of relationship_type
        host.add_edge("a", "b", __labels__={"friends"})
        host.add_edge("a", "b", __labels__={"colleagues"})
        host.add_edge("a", "c", __labels__={"colleagues"})
        host.add_edge("b", "d", __labels__={"family"})
        host.add_edge("c", "d", __labels__={"family"})
        host.add_edge("c", "d", __labels__={"friends"})
        host.add_edge("d", "a", __labels__={"friends"})
        host.add_edge("d", "a", __labels__={"colleagues"})

        qry = """
        MATCH (n)-[r:friends]->(m)
        RETURN n.name, m.name
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Alice", "Charlie", "Diana"]
        assert res["m.name"] == ["Bob", "Diana", "Alice"]

    def test_multiple_edges_specific_attribute(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=30)
        host.add_node("b", name="Bob", age=30)
        host.add_edge("a", "b", __labels__={"colleague"}, years=3)
        host.add_edge("a", "b", __labels__={"friend"}, years=5)
        host.add_edge("a", "b", __labels__={"enemy"}, hatred=10)

        qry = """
        MATCH (a)-[r:friend]->(b)
        RETURN a.name, b.name, r.years
        """
        res = GrandCypher(host).run(qry)
        assert res["a.name"] == ["Alice"]
        assert res["b.name"] == ["Bob"]
        assert res["r.years"] == [5]

    def test_edge_directionality(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_edge("a", "b", __labels__={"friend"}, years=1)
        host.add_edge("b", "a", __labels__={"colleague"}, years=2)
        host.add_edge("b", "a", __labels__={"mentor"}, years=4)

        qry = """
        MATCH (a)-[r]->(b)
        RETURN a.name, b.name, r.__labels__, r.years
        """
        res = GrandCypher(host).run(qry)
        assert res == {
            "a.name": ["Alice", "Bob", "Bob"],
            "b.name": ["Bob", "Alice", "Alice"],
            "r.__labels__": [{"friend"}, {"colleague"}, {"mentor"}],
            "r.years": [1, 2, 4],
        }

    def test_query_with_missing_edge_attribute(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=30)
        host.add_node("b", name="Bob", age=40)
        host.add_node("c", name="Charlie", age=50)
        host.add_edge("a", "b", __labels__={"friend"}, years=3)
        host.add_edge("a", "c", __labels__={"colleague"}, years=10)
        host.add_edge("b", "c", __labels__={"colleague"}, duration=10)
        host.add_edge("b", "c", __labels__={"mentor"}, years=2)

        qry = """
        MATCH (a)-[r:colleague]->(b)
        RETURN a.name, b.name, r.duration
        """
        res = GrandCypher(host).run(qry)
        assert res == {
            "a.name": ["Alice", "Bob"],
            "b.name": ["Charlie", "Charlie"],
            "r.duration": [None, 10]
        }

        qry = """
        MATCH (a)-[r:colleague]->(b)
        RETURN a.name, b.name, r.years
        """
        res = GrandCypher(host).run(qry)
        assert res == {
            "a.name": ["Alice", "Bob"],
            "b.name": ["Charlie", "Charlie"],
            "r.years": [10, None]
        }

        qry = """
        MATCH (a)-[r]->(b)
        RETURN a.name, b.name, r.__labels__, r.duration
        """
        res = GrandCypher(host).run(qry)
        assert res == {
            "a.name": ["Alice", "Alice", "Bob", "Bob"],
            "b.name": ["Bob", "Charlie", "Charlie", "Charlie"],
            "r.__labels__": [{"friend"}, {"colleague"}, {"colleague"}, {"mentor"}],
            "r.duration": [None, None, 10, None],
        }

    def test_multigraph_single_edge_where1(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Christine", age=30)
        host.add_edge("a", "b", __labels__={"friend"}, years=1, friendly="very")
        host.add_edge("b", "a", __labels__={"colleague"}, years=2)
        host.add_edge("b", "a", __labels__={"mentor"}, years=4)
        host.add_edge("b", "c", __labels__={"chef"}, years=12)

        qry = """
        MATCH (a)-[r]->(b)
        WHERE r.friendly == "very" OR r.years == 2
        RETURN a.name, b.name, r.__labels__, r.years, r.friendly
        """
        res = GrandCypher(host).run(qry)
        assert res["a.name"] == ["Alice", "Bob"]
        assert res["b.name"] == ["Bob", "Alice"]
        assert res["r.__labels__"] == [
            {"friend"},
            {"colleague"},
        ]
        assert res["r.years"] == [1, 2]
        assert res["r.friendly"] == ["very", None]

    def test_multigraph_single_edge_where2(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_edge("a", "b", __labels__={"paid"}, value=20)
        host.add_edge("a", "b", __labels__={"paid"}, amount=12, date="12th June")
        host.add_edge("b", "a", __labels__={"paid"}, amount=6)
        host.add_edge("b", "a", __labels__={"paid"}, value=14)
        host.add_edge("a", "b", __labels__={"friends"}, years=9)
        host.add_edge("a", "b", __labels__={"paid"}, amount=40)

        qry = """
        MATCH (n)-[r:paid]->(m)
        WHERE r.amount > 12
        RETURN n.name, m.name, r.amount
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Alice"]
        assert res["m.name"] == ["Bob"]
        assert res["r.amount"] == [40]

    def test_multigraph_where_node_attribute(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Christine", age=30)
        host.add_edge("a", "b", __labels__={"friend"}, years=1, friendly="very")
        host.add_edge("b", "a", __labels__={"colleague"}, years=2)
        host.add_edge("b", "a", __labels__={"mentor"}, years=4)
        host.add_edge("b", "c", __labels__={"chef"}, years=12)

        qry = """
        MATCH (a)-[r]->(b)
        WHERE a.name == "Alice"
        RETURN a.name, b.name, r.__labels__, r.years, r.friendly
        """
        res = GrandCypher(host).run(qry)
        assert res["a.name"] == ["Alice"]
        assert res["b.name"] == ["Bob"]
        assert res["r.__labels__"] == [{"friend"}]
        assert res["r.years"] == [1]
        assert res["r.friendly"] == ["very"]

    def test_multigraph_multiple_same_edge_labels(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_edge("a", "b", __labels__={"paid"}, amount=12, date="12th June")
        host.add_edge("b", "a", __labels__={"paid"}, amount=6)
        host.add_edge("b", "a", __labels__={"paid"}, value=14)
        host.add_edge("a", "b", __labels__={"friends"}, years=9)
        host.add_edge("a", "b", __labels__={"paid"}, amount=40)

        qry = """
        MATCH (n)-[r:paid]->(m)
        RETURN n.name, m.name, r.amount
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Alice", "Alice", "Bob", "Bob"]
        assert res["m.name"] == ["Bob", "Bob", "Alice", "Alice"]
        # the second "paid" edge between Bob -> Alice has no "amount" attribute, so it should be None
        assert res["r.amount"] == [12, 40, 6, None]

    def test_order_by_edge_attribute1(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=20)
        host.add_edge("b", "a", __labels__={"paid"}, value=14)
        host.add_edge("a", "b", __labels__={"paid"}, value=9)
        host.add_edge("a", "b", __labels__={"paid"}, value=40)

        qry = """
        MATCH (n)-[r]->()
        RETURN n.name, r.value
        ORDER BY r.value ASC
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Alice", "Bob", "Alice",]
        assert res["r.value"] == [9, 14,  40]

        qry = """
        MATCH (n)-[r]->()
        RETURN n.name, r.value
        ORDER BY r.value DESC
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Alice", "Bob", "Alice"]
        assert res["r.value"] == [40, 14, 9]

    def test_order_by_edge_attribute2(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=20)
        host.add_edge(
            "b", "a", __labels__={"paid"}, amount=14
        )  # different attribute name
        host.add_edge("a", "b", __labels__={"paid"}, value=9)
        host.add_edge("c", "b", __labels__={"paid"}, value=980)
        host.add_edge("c", "b", __labels__={"paid"}, value=4)
        host.add_edge("b", "c", __labels__={"paid"}, value=11)
        host.add_edge("a", "b", __labels__={"paid"}, value=40)
        host.add_edge("b", "a", __labels__={"paid"}, value=14)  # duplicate edge
        host.add_edge("a", "b", __labels__={"paid"}, value=9)  # duplicate edge
        host.add_edge("a", "b", __labels__={"paid"}, value=40)  # duplicate edge

        qry = """
        MATCH (n)-[r]->(m)
        RETURN n.name, r.value, m.name
        ORDER BY r.value ASC
        """
        res = GrandCypher(host).run(qry)
        assert res == {
            "n.name": ["Carol", "Alice", "Alice", "Bob", "Bob", "Alice", "Alice", "Carol", "Bob"],
            "m.name": ["Bob", "Bob", "Bob", "Carol", "Alice", "Bob", "Bob", "Bob", "Alice"],
            "r.value": [4, 9, 9, 11, 14, 40, 40, 980, None],
        }

    def test_order_by_edge_attribute3(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=20)
        host.add_edge("b", "a", __labels__={"paid"}, value=14)
        host.add_edge("a", "b", __labels__={"paid"}, value=9)
        host.add_edge("a", "b", __labels__={"paid"}, value=40)

        qry = """
        MATCH (n)-[r]->()
        RETURN n.name, r.value
        ORDER BY r.value ASC
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Alice", "Bob", "Alice"]
        assert res["r.value"] == [9, 14, 40]

        qry = """
        MATCH (n)-[r]->()
        RETURN n.name, r.value
        ORDER BY r.value DESC
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Alice", "Bob", "Alice"]
        assert res["r.value"] == [40, 14, 9]

    def test_order_by_edge_attribute4(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=20)
        host.add_edge(
            "b", "a", __labels__={"paid"}, amount=14
        )  # different attribute name
        host.add_edge("a", "b", __labels__={"paid"}, value=9)
        host.add_edge("c", "b", __labels__={"paid"}, value=980)
        host.add_edge("c", "b", __labels__={"paid"}, value=4)
        host.add_edge("b", "c", __labels__={"paid"}, value=11)
        host.add_edge("a", "b", __labels__={"paid"}, value=40)
        host.add_edge("b", "a", __labels__={"paid"}, value=14)  # duplicate edge
        host.add_edge("a", "b", __labels__={"paid"}, value=9)  # duplicate edge
        host.add_edge("a", "b", __labels__={"paid"}, value=40)  # duplicate edge

        qry = """
        MATCH (n)-[r]->(m)
        RETURN n.name, r.value, m.name
        ORDER BY r.value ASC
        """
        res = GrandCypher(host).run(qry)
        assert res == {
            "n.name": ["Carol", "Alice", "Alice", "Bob", "Bob", "Alice", "Alice", "Carol", "Bob"],
            "m.name": ["Bob", "Bob", "Bob", "Carol", "Alice", "Bob", "Bob", "Bob", "Alice"],
            "r.value": [4, 9, 9, 11, 14, 40, 40, 980, None]
        }

    @pytest.mark.benchmark
    def test_multigraph_aggregation_function_sum(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_edge("a", "b", __labels__={"paid"}, amount=12, date="12th June")
        host.add_edge("b", "a", __labels__={"paid"}, amount=6)
        host.add_edge("b", "a", __labels__={"paid"}, value=14)
        host.add_edge("a", "b", __labels__={"friends"}, years=9)
        host.add_edge("a", "b", __labels__={"paid"}, amount=40)

        qry = """
        MATCH (n)-[r:paid]->(m)
        RETURN n.name, m.name, SUM(r.amount)
        """
        res = GrandCypher(host).run(qry)
        assert res["SUM(r.amount)"] == [52, 6]

    def test_multigraph_aggregation_function_avg(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_edge("a", "b", __labels__={"paid"}, amount=12, date="12th June")
        host.add_edge("b", "a", __labels__={"paid"}, amount=6, message="Thanks")
        host.add_edge("a", "b", __labels__={"paid"}, amount=40)

        qry = """
        MATCH (n)-[r:paid]->(m)
        RETURN n.name, m.name, AVG(r.amount)
        """
        res = GrandCypher(host).run(qry)
        assert res["AVG(r.amount)"] == [26, 6]

    def test_multigraph_aggregation_function_min(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_edge("a", "b", __labels__={"paid"}, amount=40)
        host.add_edge("b", "a", __labels__={"paid"}, amount=6)
        host.add_edge("a", "b", __labels__={"paid"}, value=4)
        host.add_edge("a", "b", __labels__={"paid"}, amount=12)

        qry = """
        MATCH (n)-[r:paid]->(m)
        RETURN n.name, m.name, MIN(r.amount)
        """
        res = GrandCypher(host).run(qry)
        assert res["MIN(r.amount)"] == [12, 6]

    def test_multigraph_aggregation_function_max(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Christine")
        host.add_edge("a", "b", __labels__={"paid"}, amount=40)
        host.add_edge("a", "b", __labels__={"paid"}, amount=12)
        host.add_edge("a", "c", __labels__={"owes"}, amount=39)
        host.add_edge("b", "a", __labels__={"paid"}, amount=6)

        qry = """
        MATCH (n)-[r:paid]->(m)
        RETURN n.name, m.name, MAX(r.amount)
        """
        res = GrandCypher(host).run(qry)
        assert res["MAX(r.amount)"] == [40, 6]

        qry = """
        MATCH (n)-[r:owes]->(m)
        RETURN n.name, m.name, MAX(r.amount)
        """
        res = GrandCypher(host).run(qry)
        assert res["MAX(r.amount)"] == [39]

    @pytest.mark.benchmark
    def test_multigraph_aggregation_function_count(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Christine")
        host.add_edge("a", "b", __labels__={"paid"}, amount=40)
        host.add_edge("a", "b", __labels__={"paid"}, amount=12)
        host.add_edge("a", "c", __labels__={"owes"}, amount=39)
        host.add_edge("b", "a", __labels__={"paid"}, amount=6)

        qry = """
        MATCH (n)-[r:paid]->(m)
        RETURN n.name, m.name, COUNT(r.amount)
        """
        res = GrandCypher(host).run(qry)
        assert res["COUNT(r.amount)"] == [2, 1]

    def test_multigraph_multiple_aggregation_functions(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Christine")
        host.add_edge("a", "b", __labels__={"paid"}, amount=40)
        host.add_edge("a", "b", __labels__={"paid"}, amount=12)
        host.add_edge("a", "c", __labels__={"owes"}, amount=39)
        host.add_edge("b", "a", __labels__={"paid"}, amount=6)

        qry = """
        MATCH (n)-[r:paid]->(m)
        RETURN n.name, m.name, COUNT(r.amount), SUM(r.amount)
        """
        res = GrandCypher(host).run(qry)
        assert res["COUNT(r.amount)"] == [2, 1]
        assert res["SUM(r.amount)"] == [52, 6]

    def test_multigraph_aggregation_function_collect(self):
        """Test COLLECT aggregation function"""
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Christine", age=35)
        host.add_edge("a", "b", __labels__={"paid"}, amount=40)
        host.add_edge("a", "b", __labels__={"paid"}, amount=12)
        host.add_edge("a", "c", __labels__={"owes"}, amount=39)
        host.add_edge("b", "a", __labels__={"paid"}, amount=6)

        # Test COLLECT with edge attributes
        qry = """
        MATCH (n)-[r:paid]->(m)
        RETURN n.name, COLLECT(r.amount)
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Alice", "Bob"]
        assert res["COLLECT(r.amount)"] == [[40, 12], [6]]

        # Test COLLECT with node attributes
        qry = """
        MATCH (n)
        RETURN COLLECT(n.name)
        """
        res = GrandCypher(host).run(qry)
        assert res["COLLECT(n.name)"] == [["Alice", "Bob", "Christine"]]

    def test_multigraph_collect_with_grouping(self):
        """Test COLLECT with grouping by multiple keys"""
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice")
        host.add_node("b", name="Bob")
        host.add_node("c", name="Charlie")
        host.add_edge("a", "b", value=1)
        host.add_edge("a", "b", value=2)
        host.add_edge("b", "c", value=3)

        qry = """
        MATCH (n)-[r]->(m)
        RETURN n.name, m.name, COLLECT(r.value)
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Alice", "Bob"]
        assert res["m.name"] == ["Bob", "Charlie"]
        assert res["COLLECT(r.value)"] == [[1, 2], [3]]


class TestStringScalarFunctions:
    """Tests for string scalar functions: toLower, toUpper, trim"""

    def test_tolower_basic(self):
        """Test toLower with node attribute"""
        host = nx.DiGraph()
        host.add_node("a", name="ALICE")
        host.add_node("b", name="BOB")

        qry = """
        MATCH (n)
        RETURN n.name, toLower(n.name)
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["ALICE", "BOB"]
        assert res["toLower(n.name)"] == ["alice", "bob"]

    def test_tolower_mixed_case(self):
        """Test toLower with mixed case strings"""
        host = nx.DiGraph()
        host.add_node("a", name="AlIcE")

        qry = """
        MATCH (n)
        RETURN toLower(n.name)
        """
        res = GrandCypher(host).run(qry)
        assert res["toLower(n.name)"] == ["alice"]

    def test_toupper_basic(self):
        """Test toUpper with node attribute"""
        host = nx.DiGraph()
        host.add_node("a", name="alice")
        host.add_node("b", name="bob")

        qry = """
        MATCH (n)
        RETURN n.name, toUpper(n.name)
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["alice", "bob"]
        assert res["toUpper(n.name)"] == ["ALICE", "BOB"]

    def test_toupper_mixed_case(self):
        """Test toUpper with mixed case strings"""
        host = nx.DiGraph()
        host.add_node("a", name="AlIcE")

        qry = """
        MATCH (n)
        RETURN toUpper(n.name)
        """
        res = GrandCypher(host).run(qry)
        assert res["toUpper(n.name)"] == ["ALICE"]

    def test_trim_whitespace(self):
        """Test trim with leading/trailing whitespace"""
        host = nx.DiGraph()
        host.add_node("a", name="  alice  ")
        host.add_node("b", name="bob   ")
        host.add_node("c", name="   charlie")

        qry = """
        MATCH (n)
        RETURN n.name, trim(n.name)
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["  alice  ", "bob   ", "   charlie"]
        assert res["trim(n.name)"] == ["alice", "bob", "charlie"]

    def test_trim_no_whitespace(self):
        """Test trim with no whitespace"""
        host = nx.DiGraph()
        host.add_node("a", name="alice")

        qry = """
        MATCH (n)
        RETURN trim(n.name)
        """
        res = GrandCypher(host).run(qry)
        assert res["trim(n.name)"] == ["alice"]

    # NOTE: Scalar functions work on LEFT side of WHERE conditions but not RIGHT side yet
    # Currently supported: WHERE ID(A) == 1, WHERE toLower(n.name) = 'value'
    # Not yet supported: WHERE ID(A) == ID(B), WHERE toLower(n.name) = toLower(m.name)
    # def test_string_functions_with_where(self):
    #     """Test string functions in WHERE clause"""
    #     host = nx.DiGraph()
    #     host.add_node("a", name="ALICE")
    #     host.add_node("b", name="BOB")
    #
    #     qry = """
    #     MATCH (n)
    #     WHERE toLower(n.name) = 'alice'
    #     RETURN n.name
    #     """
    #     res = GrandCypher(host).run(qry)
    #     assert set(res["n.name"]) == {"ALICE", "alice"}

    def test_string_functions_combined(self):
        """Test combining multiple string functions (nested)"""
        host = nx.DiGraph()
        host.add_node("a", name="  ALICE  ")
        host.add_node("b", name="  bob  ")

        qry = """
        MATCH (n)
        RETURN toLower(trim(n.name))
        """
        res = GrandCypher(host).run(qry)
        assert set(res["toLower(trim(n.name))"]) == {"alice", "bob"}

    def test_nested_functions_multiple_levels(self):
        """Test deeply nested functions"""
        host = nx.DiGraph()
        host.add_node("a", name="  HELLO  ")

        qry = """
        MATCH (n)
        RETURN toUpper(trim(toLower(n.name)))
        """
        res = GrandCypher(host).run(qry)
        assert res["toUpper(trim(toLower(n.name)))"] == ["HELLO"]


class TestTypeAndCoalesceScalarFunctions:
    """Tests for type() and coalesce() scalar functions"""

    def test_type_basic(self):
        """Test type() with relationship labels"""
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice")
        host.add_node("b", name="Bob")
        host.add_edge("a", "b", __labels__={"paid"}, amount=50)
        host.add_edge("a", "b", __labels__={"owes"}, amount=20)

        qry = """
        MATCH (n)-[r]->(m)
        RETURN n.name, type(r), r.amount
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Alice", "Alice"]
        assert set(res["type(r)"]) == {"paid", "owes"}

    def test_type_with_specific_label(self):
        """Test type() with specific relationship label filter"""
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice")
        host.add_node("b", name="Bob")
        host.add_edge("a", "b", __labels__={"paid"}, amount=50)
        host.add_edge("a", "b", __labels__={"owes"}, amount=20)

        qry = """
        MATCH (n)-[r:paid]->(m)
        RETURN type(r)
        """
        res = GrandCypher(host).run(qry)
        assert res["type(r)"] == ["paid"]

    def test_coalesce_basic(self):
        """Test coalesce() with multiple attributes"""
        host = nx.DiGraph()
        host.add_node("a", name="Alice", nickname=None)
        host.add_node("b", nickname="Bobby")
        host.add_node("c", name="Charlie")

        qry = """
        MATCH (n)
        RETURN coalesce(n.nickname, n.name)
        """
        res = GrandCypher(host).run(qry)
        # a: nickname is None, so use name "Alice"
        # b: nickname is "Bobby"
        # c: nickname missing, so use name "Charlie"
        assert set(res["coalesce(n.nickname, n.name)"]) == {"Alice", "Bobby", "Charlie"}

    def test_coalesce_first_non_null(self):
        """Test that coalesce returns first non-null value"""
        host = nx.DiGraph()
        host.add_node("a", first=None, second="Second", third="Third")

        qry = """
        MATCH (n)
        RETURN coalesce(n.first, n.second, n.third)
        """
        res = GrandCypher(host).run(qry)
        assert res["coalesce(n.first, n.second, n.third)"] == ["Second"]

    def test_coalesce_all_null(self):
        """Test coalesce when all values are null"""
        host = nx.DiGraph()
        host.add_node("a")

        qry = """
        MATCH (n)
        RETURN coalesce(n.missing1, n.missing2)
        """
        res = GrandCypher(host).run(qry)
        assert res["coalesce(n.missing1, n.missing2)"] == [None]

    def test_coalesce_with_fallback(self):
        """Test coalesce with a fallback attribute"""
        host = nx.DiGraph()
        host.add_node("a", id="id_a")
        host.add_node("b", name="Bob", id="id_b")

        qry = """
        MATCH (n)
        RETURN coalesce(n.name, n.id)
        """
        res = GrandCypher(host).run(qry)
        assert set(res["coalesce(n.name, n.id)"]) == {"Bob", "id_a"}


class TestAlias:
    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_alias_with_single_variable_length_relationship(self, graph_type):
        host = graph_type()
        host.add_node("x", foo=12)
        host.add_node("y", foo=13)
        host.add_node("z", foo=16)
        host.add_edge("x", "y", bar="1")
        host.add_edge("y", "z", bar="2")
        host.add_edge("z", "x", bar="3")

        qry = """
        MATCH (A)-[r*0]->(B)
        RETURN ID(A) AS ayy, ID(B) AS bee, r
        """

        res = GrandCypher(host).run(qry)
        print("RES", res)
        assert res["ayy"] == ["x", "y", "z"]
        assert res["bee"] == ["x", "y", "z"]
        assert res["r"] == [[], [], []]

        qry = """
        MATCH (A)-[r*1]->(B)
        RETURN ID(A), ID(B), r AS arr
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 3
        assert res["ID(A)"] == ["x", "y", "z"]
        assert res["ID(B)"] == ["y", "z", "x"]
        assert graph_type in ACCEPTED_GRAPH_TYPES
        assert res["arr"] == [
            {"bar": "1"},
            {"bar": "2"},
            {"bar": "3"},
        ]

    @pytest.mark.benchmark
    def test_alias_with_order_by(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=20)
        host.add_edge("b", "a", __labels__={"paid"}, value=14)
        host.add_edge("a", "b", __labels__={"paid"}, value=9)
        host.add_edge("a", "b", __labels__={"paid"}, amount=96)
        host.add_edge("a", "b", __labels__={"paid"}, value=40)

        # TODO: this query should raise error due to mixing group by r.value and r.value
        # qry = """
        # MATCH (n)-[r]->(m)
        # RETURN n.name, AVG(r.value) AS average, m.name, r.value
        # ORDER BY average ASC
        # """
        qry = """
        MATCH (n)-[r]->(m)
        RETURN n.name, AVG(r.value) AS average, m.name
        ORDER BY average ASC
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Bob", "Alice"]
        assert res["m.name"] == ["Alice", "Bob"]
        assert res["average"] == [14.0, 16.333333333333332]

        # TODO: this query should raise error due to mixing group by r.value and r.value
        # qry = """
        # MATCH (n)-[r]->(m)
        # RETURN n.name, AVG(r.value) AS average, m.name, r.value
        # ORDER BY average ASC
        # """
        # qry = """
        # MATCH (n)-[r]->(m)
        # RETURN n.name, m.name, AVG(r.value) AS total, r.value as myvalue
        # ORDER BY myvalue ASC
        # """

class TestVariableLengthRelationship:
    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_single_variable_length_relationship(self, graph_type):
        host = graph_type()
        host.add_node("x", foo=12)
        host.add_node("y", foo=13)
        host.add_node("z", foo=16)
        host.add_edge("x", "y", bar="1")
        host.add_edge("y", "z", bar="2")
        host.add_edge("z", "x", bar="3")

        qry = """
        MATCH (A)-[r*0]->(B)
        RETURN ID(A), ID(B), r
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 3
        assert res["ID(A)"] == ["x", "y", "z"]
        assert res["ID(B)"] == ["x", "y", "z"]
        assert res["r"] == [[], [], []]

        qry = """
        MATCH (A)-[r*1]->(B)
        RETURN ID(A), ID(B), r
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 3
        assert res["ID(A)"] == ["x", "y", "z"]
        assert res["ID(B)"] == ["y", "z", "x"]
        assert graph_type in ACCEPTED_GRAPH_TYPES
        assert res["r"] == [
            {"bar": "1"},
            {"bar": "2"},
            {"bar": "3"},
        ]

        qry = """
        MATCH (A)-[r*2]->(B)
        RETURN ID(A), ID(B), r
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 3
        assert res["ID(A)"] == ["x", "y", "z"]
        assert res["ID(B)"] == ["z", "x", "y"]
        assert graph_type in ACCEPTED_GRAPH_TYPES
        assert res["r"] == [
            [{"bar": "1"}, {"bar": "2"}],
            [{"bar": "2"}, {"bar": "3"}],
            [{"bar": "3"}, {"bar": "1"}],
        ]

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_complex_variable_length_relationship(self, graph_type):
        host = graph_type()
        host.add_node("x", foo=12)
        host.add_node("y", foo=13)
        host.add_node("z", foo=16)
        host.add_edge("x", "y", bar="1")
        host.add_edge("y", "z", bar="2")
        host.add_edge("z", "x", bar="3")

        qry = """
        MATCH (A)-[r*0..2]->(B)
        RETURN ID(A), ID(B), r
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 3
        assert res["ID(A)"] == ["x", "y", "z", "x", "y", "z", "x", "y", "z"]
        assert res["ID(B)"] == ["x", "y", "z", "y", "z", "x", "z", "x", "y"]
        assert graph_type in ACCEPTED_GRAPH_TYPES
        assert res["r"] == [
            [],
            [],
            [],
            {"bar": "1"},
            {"bar": "2"},
            {"bar": "3"},
            [{"bar": "1"}, {"bar": "2"}],
            [{"bar": "2"}, {"bar": "3"}],
            [{"bar": "3"}, {"bar": "1"}],
        ]


class TestType:
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_host_no_edge_type(self, graph_type):
        host = graph_type()
        host.add_node("x")
        host.add_node("y")
        host.add_node("z")
        host.add_edge("x", "y", bar="1")
        host.add_edge("y", "z", bar="2")
        host.add_edge("z", "x", bar="3")

        qry = """
        MATCH (A)-[:A]->(B)
        RETURN A, B
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["A"] == []
        assert res["B"] == []

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_edge_type(self, graph_type):
        host = graph_type()
        host.add_node("x")
        host.add_node("y")
        host.add_node("z")
        host.add_edge("x", "y", __labels__={"Edge", "XY"}, bar="1")
        host.add_edge("y", "z", __labels__={"Edge", "YZ"}, bar="2")
        host.add_edge("z", "x", __labels__={"Edge", "ZX"}, bar="3")

        qry = """
        MATCH (A)-[:XY]->(B)
        RETURN ID(A), ID(B)
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["ID(A)"] == ["x"]
        assert res["ID(B)"] == ["y"]

        qry = """
        MATCH (A)-[:Edge]->(B)
        RETURN ID(A), ID(B)
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["ID(A)"] == ["x", "y", "z"]
        assert res["ID(B)"] == ["y", "z", "x"]

        qry = """
        MATCH (A)-[r:Edge]->(B)
        where r.bar == "2"
        RETURN ID(A), ID(B)
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["ID(A)"] == ["y"]
        assert res["ID(B)"] == ["z"]

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_edge_type_hop(self, graph_type):
        host = graph_type()
        host.add_node("x")
        host.add_node("y")
        host.add_node("z")
        host.add_edge("x", "y", __labels__={"Edge", "XY"})
        host.add_edge("y", "z", __labels__={"Edge", "YZ"})
        host.add_edge("z", "x", __labels__={"Edge", "ZX"})

        qry = """
        MATCH (A)-[:XY*2]->(B)
        RETURN ID(A), ID(B)
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["ID(A)"] == []
        assert res["ID(B)"] == []

        qry = """
        MATCH (A)-[:XY*0..2]->(B)
        RETURN ID(A), ID(B)
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["ID(A)"] == ["x", "y", "z", "x"]
        assert res["ID(B)"] == ["x", "y", "z", "y"]

        qry = """
        MATCH (A)-[r:Edge*0..2]->(B)
        RETURN ID(A), ID(B), r
        """

        res = GrandCypher(host).run(qry)

        assert len(res) == 3
        assert res["ID(A)"] == ["x", "y", "z", "x", "y", "z", "x", "y", "z"]
        assert res["ID(B)"] == ["x", "y", "z", "y", "z", "x", "z", "x", "y"]
        assert graph_type in ACCEPTED_GRAPH_TYPES
        assert res["r"] == [
            [],
            [],
            [],
            {"__labels__": {"Edge", "XY"}},
            {"__labels__": {"Edge", "YZ"}},
            {"__labels__": {"Edge", "ZX"}},
            [{"__labels__": {"Edge", "XY"}}, {"__labels__": {"Edge", "YZ"}}],
            [{"__labels__": {"Edge", "YZ"}}, {"__labels__": {"Edge", "ZX"}}],
            [{"__labels__": {"Edge", "ZX"}}, {"__labels__": {"Edge", "XY"}}],
        ]

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_host_no_node_type(self, graph_type):
        host = graph_type()
        host.add_node("x")
        host.add_node("y")
        host.add_node("z")
        host.add_edge("x", "y")
        host.add_edge("y", "z")
        host.add_edge("z", "x")

        qry = """
        MATCH (A:Node)-->(B)
        RETURN A, B
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["A"] == []
        assert res["B"] == []

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_node_type(self, graph_type):
        host = graph_type()
        host.add_node("x", __labels__=set(["Node", "X"]), foo="1")
        host.add_node("y", __labels__=set(["Node", "Y"]), foo="2")
        host.add_node("z", __labels__=set(["Node", "Z"]), foo="3")
        host.add_edge("x", "y")
        host.add_edge("y", "z")
        host.add_edge("z", "x")

        qry = """
        MATCH (A)-->(B:Node)
        RETURN ID(A), ID(B)
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["ID(A)"] == ["x", "y", "z"]
        assert res["ID(B)"] == ["y", "z", "x"]

        qry = """
        MATCH (A:Node)-->(B:X)
        RETURN ID(A), ID(B)
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["ID(A)"] == ["z"]
        assert res["ID(B)"] == ["x"]

        qry = """
        MATCH (A:Node)-->(B)
        where A.foo == "2"
        RETURN ID(A), ID(B)
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["ID(A)"] == ["y"]
        assert res["ID(B)"] == ["z"]

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_node_type_edge_hop(self, graph_type):
        host = graph_type()
        host.add_node("x", __labels__=set(["Node", "X"]), foo="1")
        host.add_node("y", __labels__=set(["Node", "Y"]), foo="2")
        host.add_node("z", __labels__=set(["Node", "Z"]), foo="3")
        host.add_edge("x", "y", name="xy", __labels__={"XY"})
        host.add_edge("y", "z", name="yz", __labels__={"XY"})

        qry = """
        MATCH (A:Node)-[*0..1]->(B:X)
        RETURN ID(A), ID(B)
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["ID(A)"] == ["x"]
        assert res["ID(B)"] == ["x"]

        qry = """
        MATCH (A:Node)-[*0..2]->(B{foo:"2"})
        RETURN ID(A), ID(B)
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["ID(A)"] == ["y", "x"]
        assert res["ID(B)"] == ["y", "y"]

        qry = """
        MATCH (A:X)-[*0..2]->(B)
        where B.foo == "1" or B.foo == "3"
        RETURN ID(A), ID(B)
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["ID(A)"] == ["x", "x"]
        assert res["ID(B)"] == ["x", "z"]


    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_node_type_edge_zero_hop_complex(self, graph_type):
        host = graph_type()
        host.add_node("b1", __labels__=set(["batch"]))
        host.add_node("u0", __labels__=set(["upgrade"]), foo="0")
        host.add_node("u1", __labels__=set(["upgrade"]), foo="1")
        host.add_node("u2", __labels__=set(["upgrade"]), foo="2")
        host.add_node("u3", __labels__=set(["upgrade"]), foo="3")
        host.add_edge("b1", "u0", __labels__=set(["contain"]))
        host.add_edge("b1", "u1", __labels__=set(["contain"]))
        host.add_edge("b1", "u2", __labels__=set(["contain"]))
        host.add_edge("b1", "u3", __labels__=set(["contain"]))
        host.add_edge("u1", "u2", __labels__=set(["dependent"]))

        host.add_node("b2", __labels__=set(["batch"]))
        host.add_node("u4", __labels__=set(["upgrade"]), foo="4")
        host.add_edge("b2", "u4", __labels__=set(["contain"]))

        host.add_edge("u1", "u4", __labels__=set(["conflict"]))
        host.add_edge("u3", "u4", __labels__=set(["conflict"]))

        qry = """
        MATCH (U1:upgrade)-[:conflict]->(U2:upgrade)
        MATCH (U1:upgrade)-[:dependent*0..3]->(U3:upgrade)
        match (B1:batch) -[:contain]->(U1:upgrade)
        match (B1:batch) -[:contain]->(U3:upgrade)
        match (B2:batch) -[:contain]->(U2:upgrade)
        RETURN ID(U1), ID(U3)
        """

        gc = GrandCypher(host)
        res = gc.run(qry)
        assert len(res) == 2
        assert res["ID(U1)"] == ["u1", "u3", "u1"]
        assert res["ID(U3)"] == ["u1", "u3", "u2"]


class TestSpecialCases:
    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_two_edge_hop_with_edge_node_type(self, graph_type):
        host = graph_type()
        host.add_node("C_1_1", __labels__=set(["X"]), head=True)
        host.add_node("C_1_2", __labels__=set(["X"]))
        host.add_node("C_1_3", __labels__=set(["X"]))
        host.add_node("C_2_1", name="C_2_1", __labels__=set(["X"]), head=True)
        host.add_node("C_2_2", __labels__=set(["X"]))
        host.add_edge("C_1_1", "C_1_2", __labels__=set(["b"]))
        host.add_edge("C_1_2", "C_1_3", __labels__=set(["b"]))
        host.add_edge("C_2_1", "C_2_2", __labels__=set(["b"]))

        host.add_node("a_1_1", __labels__=set(["Y"]), head=True)
        host.add_node("a_1_2", __labels__=set(["Y"]))
        host.add_node("a_2_1", __labels__=set(["Y"]), head=True)
        host.add_edge("a_1_1", "a1_2", __labels__=set(["b"]))

        host.add_edge("C_1_1", "a_1_1", __labels__=set(["i"]))
        host.add_edge("C_1_3", "a_1_2", __labels__=set(["i"]))
        host.add_edge("C_1_2", "a_2_1", __labels__=set(["i"]))
        host.add_edge("C_2_2", "a_2_1", __labels__=set(["i"]))

        qry = """
        MATCH (A:X) -[:b*0..5]-> (B:X) -[:i*0..1]-> (c)
        where A.head is True
        return ID(A), ID(B), ID(c)
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 3

        C_1_indices = [i for i, v in enumerate(res["ID(A)"]) if v == "C_1_1"]
        C_2_indices = [i for i, v in enumerate(res["ID(A)"]) if v == "C_2_1"]
        assert len(C_1_indices) + len(C_2_indices) == len(res["ID(A)"])

        assert set(res["ID(B)"][i] for i in C_1_indices) == set(
            ["C_1_1", "C_1_2", "C_1_3"]
        )
        assert set(res["ID(c)"][i] for i in C_1_indices) == set(
            ["C_1_1", "C_1_2", "C_1_3", "a_1_1", "a_1_2", "a_2_1"]
        )

        assert set(res["ID(B)"][i] for i in C_2_indices) == set(["C_2_1", "C_2_2"])
        assert set(res["ID(c)"][i] for i in C_2_indices) == set(
            ["C_2_1", "C_2_2", "a_2_1"]
        )


class TestComments:
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_line_comments(self, graph_type):
        host = graph_type()
        host.add_node("x", foo=12)
        host.add_node("y", foo=13)
        host.add_node("z", foo=16)
        host.add_edge("x", "y", bar="1")
        host.add_edge("y", "z", bar="2")
        host.add_edge("z", "x", bar="3")

        qry = """
        // This is a comment
        MATCH (A)-[r*0]->(B)
        RETURN A, B, r
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 3

        qry = """
        MATCH (A)-[r*1]->(B)
        // This is a comment
        RETURN A, B, r
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 3

        qry = """
        MATCH (A)-[r*2]->(B)
        RETURN A, B, r
        // This is a comment
        """

        res = GrandCypher(host).run(qry)

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_end_of_line_comments(self, graph_type):
        host = graph_type()
        host.add_node("x", foo=12)
        host.add_node("y", foo=13)
        host.add_node("z", foo=16)
        host.add_edge("x", "y", bar="1")
        host.add_edge("y", "z", bar="2")
        host.add_edge("z", "x", bar="3")

        qry = """
        MATCH (A)-[r*0]->(B) // This is a comment
        RETURN A, B, r
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 3

        qry = """
        MATCH (A)-[r*1]->(B)
        RETURN A, B, r // This is a comment
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 3

        qry = """
        MATCH (A)-[r*2]->(B)
        RETURN A, B, r
        """

        res = GrandCypher(host).run(qry)

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_every_line_comments(self, graph_type):
        host = graph_type()
        host.add_node("x", foo=12)
        host.add_node("y", foo=13)
        host.add_node("z", foo=16)
        host.add_edge("x", "y", bar="1")
        host.add_edge("y", "z", bar="2")
        host.add_edge("z", "x", bar="3")

        qry = """
        // This is a comment
        MATCH (A)-[r*0]->(B) // This is a comment
        RETURN A, B, r // This is a comment
        // This is a comment
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 3

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_mid_query_comment(self, graph_type):
        host = graph_type()
        host.add_node("x", foo=12)
        host.add_node("y", foo=13)
        host.add_node("z", foo=16)
        host.add_edge("x", "y", bar="1")
        host.add_edge("y", "z", bar="2")
        host.add_edge("z", "x", bar="3")

        qry = """
        MATCH
            // OBTRUSIVE COMMENT!
            (A)-[
            // This is a comment //
            r*0 // This is a comment
        ]->(B
            // Comment!
        )
        RETURN A, B, r
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 3


class TestStringOperators:
    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_starts_with(self, graph_type):
        host = graph_type()
        host.add_node(1, name="Ford Prefect")
        host.add_node(2, name="Arthur Dent")
        host.add_edge(1, 2)

        qry = """
        MATCH (A)
        WHERE A.name STARTS WITH "Ford"
        RETURN A
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 1

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_ends_with(self, graph_type):
        host = graph_type()
        host.add_node(1, name="Ford Prefect")
        host.add_node(2, name="Arthur Dent")
        host.add_edge(1, 2)

        qry = """
        MATCH (A)
        WHERE A.name ends WITH "Ford"
        RETURN A
        """

        res = GrandCypher(host).run(qry)
        assert len(res["A"]) == 0

        qry = """
        MATCH (A)
        WHERE A.name ends wITh "t"
        RETURN A
        """

        res = GrandCypher(host).run(qry)
        assert len(res["A"]) == 2

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_contains(self, graph_type):
        host = graph_type()
        host.add_node(1, name="Ford Prefect")
        host.add_node(2, name="Arthur Dent")
        host.add_edge(1, 2)

        qry = """
        MATCH (A)
        WHERE A.name contains "Ford"
        RETURN A
        """

        res = GrandCypher(host).run(qry)
        assert len(res["A"]) == 1

        qry = """
        MATCH (A)
        WHERE NOT A.name contains " "
        RETURN A
        """

        res = GrandCypher(host).run(qry)
        assert len(res["A"]) == 0


class TestNot:
    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_not(self, graph_type):
        host = graph_type()
        host.add_node(1, name="Ford Prefect")
        host.add_node(2, name="Arthur Dent")
        host.add_edge(1, 2)

        qry = """
        MATCH (A)
        WHERE NOT A.name contains "Ford"
        RETURN A
        """

        res = GrandCypher(host).run(qry)
        assert len(res["A"]) == 1

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_doublenot(self, graph_type):
        host = graph_type()
        host.add_node(1, name="Ford Prefect")
        host.add_node(2, name="Arthur Dent")
        host.add_edge(1, 2)

        qry = """
        MATCH (A)
        WHERE NOT NOT A.name contains "Ford"
        RETURN A
        """

        res = GrandCypher(host).run(qry)
        assert len(res["A"]) == 1

    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_nested_nots_in_statements(self, graph_type):
        host = graph_type()
        host.add_node("Piano", votes=42, percussion="yup", strings="yup")
        host.add_node("Guitar", votes=16, percussion="nah", strings="yup")
        host.add_node("Drum", votes=12, percussion="yup", strings="nah")

        qry = """
        MATCH (Instrument)
        WHERE (
            NOT Instrument.percussion == "yup"
            AND NOT Instrument.strings == "yup"
        )
        RETURN Instrument
        """

        res = GrandCypher(host).run(qry)
        assert len(res["Instrument"]) == 0

        qry = """
        MATCH (Instrument)
        WHERE (
            Instrument.percussion == "yup"
            AND NOT Instrument.votes == 42
        )
        RETURN Instrument
        """

        res = GrandCypher(host).run(qry)
        assert len(res["Instrument"]) == 1


class TestPath:
    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_path(self, graph_type):
        host = graph_type()
        host.add_node("x", name="x")
        host.add_node("y", name="y")
        host.add_node("z", name="z")

        host.add_edge("x", "y", foo="bar")
        host.add_edge(
            "y",
            "z",
        )

        qry = """
        MATCH P = ()-[r*2]->()
        RETURN P
        LIMIT 1
        """

        res = GrandCypher(host).run(qry)
        print("!!!!!!!!!!!!!", res)
        assert len(res["P"][0]) == 5


class TestMatchWithOrOperatorInRelationships:
    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_match_with_single_or_operator(self, graph_type):
        host = graph_type()
        host.add_node("a", name="Alice")
        host.add_node("b", name="Bob")
        host.add_node("c", name="Carol")
        host.add_edge("a", "b", __labels__={"LOVES"})
        host.add_edge("b", "c", __labels__={"WORKS_WITH"})

        qry = """
        MATCH (n1)-[r:LOVES|WORKS_WITH]->(n2)
        RETURN n1.name, n2.name
        """
        res = GrandCypher(host).run(qry)
        assert res["n1.name"] == ["Alice", "Bob"]
        assert res["n2.name"] == ["Bob", "Carol"]

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_match_with_multiple_or_operators(self, graph_type):
        host = graph_type()
        host.add_node("a", name="Alice")
        host.add_node("b", name="Bob")
        host.add_node("c", name="Carol")
        host.add_node("d", name="Derek")
        host.add_edge("a", "b", __labels__={"LOVES"})
        host.add_edge("a", "c", __labels__={"KNOWS"})
        host.add_edge("b", "c", __labels__={"LIVES_NEAR"})
        host.add_edge("b", "d", __labels__={"WORKS_WITH"})

        qry = """
        MATCH (n1)-[r:LOVES|KNOWS|LIVES_NEAR]->(n2)
        RETURN n1.name, n2.name
        """
        res = GrandCypher(host).run(qry)
        assert res["n1.name"] == ["Alice", "Alice", "Bob"]
        assert res["n2.name"] == ["Bob", "Carol", "Carol"]

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_match_with_or_operator_and_other_conditions(self, graph_type):
        host = graph_type()
        host.add_node("a", name="Alice", age=30)
        host.add_node("b", name="Bob", age=25)
        host.add_node("c", name="Carol", age=40)
        host.add_edge("a", "b", __labels__={"LOVES"})
        host.add_edge("a", "c", __labels__={"KNOWS"})
        host.add_edge("b", "c", __labels__={"WORKS_WITH"})

        qry = """
        MATCH (n1)-[r:LOVES|KNOWS]->(n2)
        WHERE n1.age > 28 AND n2.age > 35
        RETURN n1.name, n2.name
        """
        res = GrandCypher(host).run(qry)
        assert res["n1.name"] == ["Alice"]
        assert res["n2.name"] == ["Carol"]

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_no_results_when_no_matching_edges(self, graph_type):
        host = graph_type()
        host.add_node("a", name="Alice")
        host.add_node("b", name="Bob")
        host.add_edge("a", "b", __labels__={"WORKS_WITH"})

        qry = """
        MATCH (n1)-[r:IN_CITY|HAS_ROUTE]->(n2)
        RETURN n1.name, n2.name
        """
        res = GrandCypher(host).run(qry)
        assert len(res["n1.name"]) == 0  # No results because no edges match

    def test_multigraph_match_with_single_or_operator(self):
        host = nx.MultiDiGraph()
        host.add_node("a", name="Alice")
        host.add_node("b", name="Bob")
        host.add_node("c", name="Carol")
        host.add_node("d", name="Derek")
        host.add_edge("a", "b", __labels__={"LOVES"})
        host.add_edge("b", "c", __labels__={"WORKS_WITH"})
        host.add_edge("b", "c", __labels__={"DISLIKES"})
        host.add_edge("b", "d", __labels__={"DISLIKES"})

        qry = """
        MATCH (n1)-[r:IS_SUING|DISLIKES]->(n2)
        RETURN n1.name, n2.name
        """
        res = GrandCypher(host).run(qry)
        assert res["n1.name"] == ["Bob", "Bob"]
        assert res["n2.name"] == ["Carol", "Derek"]


class TestMatchWithOrOperatorInNodeLabels:
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_match_with_single_or_operator_in_start_node(self, graph_type):
        host = graph_type()
        host.add_node("a", __labels__={"Person", "Employee"}, name="Alice")
        host.add_node("b", __labels__={"Person", "Manager"}, name="Bob")
        host.add_node("c", __labels__={"Task"}, name="Project Plan")
        host.add_edge("a", "c", __labels__={"ASSIGNED_TO"})
        host.add_edge("b", "c", __labels__={"ASSIGNED_TO"})

        qry = """
        MATCH (n:Person|Manager)-[r]->(t:Task)
        RETURN n.name, t.name
        """
        res = GrandCypher(host).run(qry)
        assert sorted(res["n.name"]) == ["Alice", "Bob"]
        assert sorted(res["t.name"]) == ["Project Plan", "Project Plan"]

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_match_with_or_operator_in_end_node(self, graph_type):
        host = graph_type()
        host.add_node("a", __labels__={"User"}, name="Charlie")
        host.add_node("b", __labels__={"Post"}, name="First Post")
        host.add_node("c", __labels__={"Comment"}, name="First Comment")
        host.add_node("d", __labels__={"Tag"}, name="Tech")
        host.add_edge("a", "b", __labels__={"CREATES"})
        host.add_edge("a", "c", __labels__={"CREATES"})

        qry = """
        MATCH (n:User)-[r]->(e:Post|Comment)
        RETURN n.name, e.name
        """
        res = GrandCypher(host).run(qry)
        assert sorted(res["n.name"]) == ["Charlie", "Charlie"]
        assert sorted(res["e.name"]) == ["First Comment", "First Post"]

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_match_with_multiple_or_operators_on_both_nodes(self, graph_type):
        host = graph_type()
        host.add_node("a", __labels__={"Employee", "Manager"}, name="Dave")
        host.add_node("b", __labels__={"Project"}, name="Apollo")
        host.add_node("c", __labels__={"Employee", "Senior"}, name="Eve")
        host.add_node("d", __labels__={"Task"}, name="Database Setup")
        host.add_edge("a", "b", __labels__={"MANAGES"})
        host.add_edge("c", "d", __labels__={"ASSIGNED_TO"})
        host.add_edge("a", "d", __labels__={"OVERSEES"})

        qry = """
        MATCH (n:Employee|Manager)-[r]->(m:Project|Task)
        RETURN n.name, m.name
        """
        res = GrandCypher(host).run(qry)
        assert sorted(res["n.name"]) == ["Dave", "Dave", "Eve"]
        assert sorted(res["m.name"]) == ["Apollo", "Database Setup", "Database Setup"]

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_match_with_or_on_nodes_and_relationships(self, graph_type):
        host = graph_type()
        host.add_node("a", __labels__={"User"}, name="Adam")
        host.add_node("b", __labels__={"Company"}, name="Company Inc.")
        host.add_node("c", __labels__={"Person"}, name="Alice")
        host.add_edge("a", "b", __labels__={"WORKS_FOR"})
        host.add_edge("a", "c", __labels__={"KNOWS"})
        host.add_edge("c", "b", __labels__={"WORKS_FOR"})

        qry = """
        MATCH (n:User|Person)-[r:KNOWS|WORKS_FOR]->(m:Company|Person)
        RETURN n.name, m.name
        """
        res = GrandCypher(host).run(qry)
        assert sorted(res["n.name"]) == ["Adam", "Adam", "Alice"]
        assert sorted(res["m.name"]) == ["Alice", "Company Inc.", "Company Inc."]

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_no_results_when_no_matching_nodes(self, graph_type):
        host = graph_type()
        host.add_node("a", __labels__={"User"}, name="Henry")
        host.add_node("b", __labels__={"Location"}, name="Paris")
        host.add_edge("a", "b", __labels__={"LIVES_IN"})

        qry = """
        MATCH (n:Person|Animal)
        RETURN n.name
        """
        res = GrandCypher(host).run(qry)
        assert len(res.get("n.name", [])) == 0


    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_or_operator_with_single_label_and_no_match(self, graph_type):
        host = graph_type()
        host.add_node("a", __labels__={"User"}, name="Henry")
        host.add_node("b", __labels__={"Location"}, name="Paris")
        host.add_edge("a", "b", __labels__={"LIVES_IN"})

        qry = """
        MATCH (n:Person|Tourist)-[]->()
        RETURN n.name
        """
        res = GrandCypher(host).run(qry)
        assert len(res.get("n.name", [])) == 0


    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_or_operator_on_nodes_with_property_filters(self, graph_type):
        host = graph_type()
        host.add_node("a", __labels__={"Book"}, name="Dune", pages=412)
        host.add_node("b", __labels__={"Movie"}, name="Dune", runtime=155)
        host.add_node("c", __labels__={"Book"}, name="Foundation", pages=255)
        host.add_node("d", __labels__={"Author"}, name="Frank Herbert")
        host.add_node("e", __labels__={"Author"}, name="Isaac Asimov")
        host.add_edge("d", "a", __labels__={"WROTE"})
        host.add_edge("e", "c", __labels__={"WROTE"})

        qry = """
        MATCH (p:Book|Movie)<-[r:WROTE]-(a:Author)
        WHERE p.name == "Dune"
        RETURN p.name, a.name
        """
        res = GrandCypher(host).run(qry)
        assert res["p.name"] == ["Dune"]
        assert res["a.name"] == ["Frank Herbert"]

class TestFunction:
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_id(self, graph_type):
        host = graph_type()
        host.add_node(1, name="Ford Prefect")
        host.add_node(2, name="Arthur Dent")
        host.add_node(3, name="John Smith")
        host.add_edge(1, 2)
        host.add_edge(2, 3)

        qry = """
        MATCH (A)
        WHERE ID(A) == 1 OR ID(A) == 2
        RETURN ID(A)
        """

        res = GrandCypher(host).run(qry)
        assert res["ID(A)"] == [1, 2]


class TestList:
    @pytest.mark.benchmark
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_in(self, graph_type):
        host = graph_type()
        host.add_node(1, name="Ford Prefect")
        host.add_node(2, name="Arthur Dent")
        host.add_node(3, name="John Smith")
        host.add_edge(1, 2)
        host.add_edge(2, 3)

        qry = """
        MATCH (A)
        WHERE ID(A) IN [1, 3]
        RETURN ID(A)
        """

        res = GrandCypher(host).run(qry)
        assert res["ID(A)"] == [1, 3]


class TestReuse:
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_use_gc(self, graph_type):
        host = graph_type()
        host.add_node(1, name="Ford Prefect")
        host.add_node(2, name="Arthur Dent")
        host.add_node(3, name="John Smith")
        host.add_edge(1, 2)
        host.add_edge(2, 3)

        qry = """
        MATCH (A)
        WHERE ID(A) IN [1, 3]
        RETURN ID(A)
        """

        gc = GrandCypher(host)
        res = gc.run(qry)
        assert res["ID(A)"] == [1, 3]
        res = gc.run(qry)
        assert res["ID(A)"] == [1, 3]


class TestReturnFullNodeAttributes:
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_return_full_node_attributes(self, graph_type):
        """Test that RETURN node returns the full node dictionary with all attributes."""
        host = graph_type()
        # Add node with multiple attributes
        host.add_node("x", name="node_x", age=30, is_active=True)
        host.add_node("y", name="node_y", age=25, location="New York")
        host.add_edge("x", "y")

        # Query to return node A
        qry = """
        MATCH (A)-[]->(B)
        RETURN A
        """

        result = GrandCypher(host).run(qry)
        assert "A" in result
        assert len(result["A"]) == 1

        # Instead of just the node ID, we expect the full node dictionary
        node_result = result["A"][0]
        # Test should expect a dictionary-like object with attributes
        assert isinstance(node_result, dict)
        assert node_result["name"] == "node_x"
        assert node_result["age"] == 30
        assert node_result["is_active"] is True

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_return_multiple_nodes_with_attributes(self, graph_type):
        """Test that RETURN node returns full attributes for multiple nodes."""
        host = graph_type()
        # Add nodes with different attributes
        host.add_node("x", name="node_x", type="source")
        host.add_node("y", name="node_y", type="middle")
        host.add_node("z", name="node_z", type="target")
        host.add_edge("x", "y")
        host.add_edge("y", "z")

        # Query to return all B nodes
        qry = """
        MATCH (A)-[]->(B)
        RETURN B
        """

        result = GrandCypher(host).run(qry)
        assert "B" in result
        assert len(result["B"]) == 2

        # Check that each result is a full node dictionary
        node_types = [node["type"] for node in result["B"]]
        assert "middle" in node_types
        assert "target" in node_types

        node_names = [node["name"] for node in result["B"]]
        assert "node_y" in node_names
        assert "node_z" in node_names

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_return_node_without_attributes(self, graph_type):
        """Test that RETURN node works with nodes that have no attributes."""
        host = graph_type()
        # Add nodes without attributes
        host.add_node("x")
        host.add_node("y")
        host.add_edge("x", "y")

        # Query to return node A
        qry = """
        MATCH (A)-[]->(B)
        RETURN A
        """

        result = GrandCypher(host).run(qry)
        assert "A" in result
        assert len(result["A"]) == 1

        # For nodes without attributes, we expect an empty dictionary
        # or a dictionary with only default NetworkX attributes
        node_result = result["A"][0]
        assert isinstance(node_result, dict)

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_aliased_node_returns_full_attributes(self, graph_type):
        """Test that aliased nodes in RETURN also return full node attributes."""
        host = graph_type()
        host.add_node("x", name="node_x", score=95)
        host.add_node("y", name="node_y", score=85)
        host.add_edge("x", "y")

        # Query with alias
        qry = """
        MATCH (A)-[]->(B)
        RETURN A AS SourceNode
        """

        result = GrandCypher(host).run(qry)
        assert "SourceNode" in result
        assert len(result["SourceNode"]) == 1

        # The aliased result should still be a full node dictionary
        node_result = result["SourceNode"][0]
        assert isinstance(node_result, dict)
        assert node_result["name"] == "node_x"
        assert node_result["score"] == 95

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_return_mixed_nodes_and_attributes(self, graph_type):
        """Test that a query can return both full nodes and specific attributes."""
        host = graph_type()
        host.add_node("x", name="node_x", age=30)
        host.add_node("y", name="node_y", age=25)
        host.add_edge("x", "y")

        # Query returning both node and specific attribute
        qry = """
        MATCH (A)-[]->(B)
        RETURN A, B.name
        """

        result = GrandCypher(host).run(qry)
        assert "A" in result
        assert "B.name" in result
        assert len(result["A"]) == 1
        assert len(result["B.name"]) == 1

        # A should be a full node dictionary
        node_result = result["A"][0]
        assert isinstance(node_result, dict), (
            "Expected A to be a full node dictionary but got {}".format(
                type(node_result)
            )
        )
        assert node_result["name"] == "node_x"

        # B.name should be just the attribute value
        assert result["B.name"][0] == "node_y"


def test_generate_multiedge_edge_hop_key():
    edge_hop_map = {("A", "C"): ("A", "B", "C"), ("D", "E"): ("D", "D"), ("F", "G"): ("F", "G")}
    edge_hop_map = {k: HopSpec(edge_id=k, nodes=v, hop_count=1) for k, v in edge_hop_map.items()}
    multi_edge_keys = {("A", "B"): [1, 2], ("B", "C"): [3, 4], ("D", "D"): [-1], ("F", "G"): [None]}

    assert list(generate_multiedge_edge_hop_key(edge_hop_map, multi_edge_keys)) == [
        [EdgeHopKey(edge_id=("A", "C"), keys=(1, 3)), EdgeHopKey(edge_id=("D", "E"), keys=tuple()), EdgeHopKey(edge_id=("F", "G"), keys=(None,))],
        [EdgeHopKey(edge_id=("A", "C"), keys=(1, 4)), EdgeHopKey(edge_id=("D", "E"), keys=tuple()), EdgeHopKey(edge_id=("F", "G"), keys=(None,))],
        [EdgeHopKey(edge_id=("A", "C"), keys=(2, 3)), EdgeHopKey(edge_id=("D", "E"), keys=tuple()), EdgeHopKey(edge_id=("F", "G"), keys=(None,))],
        [EdgeHopKey(edge_id=("A", "C"), keys=(2, 4)), EdgeHopKey(edge_id=("D", "E"), keys=tuple()), EdgeHopKey(edge_id=("F", "G"), keys=(None,))],
    ]


def test_find_multiedge_keys_multidigraph():
    match = {"A": "a", "B": "b", "C": "c", "D": "d", "E": "e"}
    edge_hop_map = {("A", "C"): ("A", "B", "C"), ("D", "E"): ("D", "D")}
    edge_hop_map = {k: HopSpec(edge_id=k, nodes=v, hop_count=1) for k, v in edge_hop_map.items()}
    host = nx.MultiDiGraph()
    host.add_edge("a", "b", key=1)
    host.add_edge("a", "b", key=2)
    host.add_edge("b", "c", key=3)
    host.add_edge("b", "c", key=4)
    host.add_edge("d", "e", key=5)

    assert find_multiedge_keys(host, match, edge_hop_map) == {
        ("A", "B"): [1, 2], ("B", "C"): [3, 4], ("D", "D"): [-1]
    }


def test_find_multiedge_keys_digraph():
    match = {"A": "a", "B": "b", "C": "c", "D": "d", "E": "e", "F": "f", "G": "g"}
    edge_hop_map = {("A", "C"): ("A", "B", "C"), ("D", "E"): ("D", "D"), ("F", "G"): ("F", "G")}
    edge_hop_map = {k: HopSpec(edge_id=k, nodes=v, hop_count=1) for k, v in edge_hop_map.items()}
    host = nx.DiGraph()
    host.add_edge("a", "b", key=1)
    host.add_edge("a", "b", key=2)
    host.add_edge("b", "c", key=3)
    host.add_edge("b", "c", key=4)
    host.add_edge("d", "e", key=5)
    host.add_edge("f", "g", key=6)

    assert find_multiedge_keys(host, match, edge_hop_map) == {
        ("A", "B"): [None], ("B", "C"): [None],
        ("D", "D"): [-1], ("F", "G"): [None]
    }


class TestGetEdgeFromHost:
    def test_no_edges_found_returns_empty_list(self):
        g = nx.DiGraph()
        result = get_edge_from_host(
            g,
            [EdgeWithKey("A", "B", None, 1)]
        )
        assert result == []


    def test_single_edge_digraph_returns_full_dict(self):
        g = nx.DiGraph()
        g.add_edge("A", "B", weight=5)

        result = get_edge_from_host(
            g,
            [EdgeWithKey("A", "B", None, 1)]
        )

        assert result == {"weight": 5}


    def test_single_edge_digraph_with_attribute(self):
        g = nx.DiGraph()
        g.add_edge("A", "B", cost=9)

        result = get_edge_from_host(
            g,
            [EdgeWithKey("A", "B", None, 1)],
            entity_attribute="cost"
        )

        assert result == 9


    def test_single_edge_digraph_attribute_missing_returns_none(self):
        g = nx.DiGraph()
        g.add_edge("A", "B", weight=10)

        result = get_edge_from_host(
            g,
            [EdgeWithKey("A", "B", None, 1)],
            entity_attribute="unknown"
        )

        assert result is None


    def test_multiple_edges_multidigraph_list_returned(self):
        g = nx.MultiDiGraph()
        g.add_edge("A", "B", key=0, w=1)
        g.add_edge("A", "B", key=1, w=2)

        edges = [
            EdgeWithKey("A", "B", 0, 1),
            EdgeWithKey("A", "B", 1, 1)
        ]

        result = get_edge_from_host(g, edges)

        assert isinstance(result, list)
        assert {"w": 1} in result
        assert {"w": 2} in result
        assert len(result) == 2


    def test_multiple_edges_attribute_access_raises_typeerror(self):
        g = nx.MultiDiGraph()
        g.add_edge("A", "B", key=0, w=1)
        g.add_edge("A", "B", key=1, w=2)

        edges = [
            EdgeWithKey("A", "B", 0, 1),
            EdgeWithKey("A", "B", 1, 1)
        ]

        with pytest.raises(TypeError):
            get_edge_from_host(g, edges, entity_attribute="w")


    def test_multidigraph_correct_key_lookup(self):
        g = nx.MultiDiGraph()
        g.add_edge("X", "Y", key=10, value="correct")
        g.add_edge("X", "Y", key=11, value="wrong")

        result = get_edge_from_host(
            g,
            [EdgeWithKey("X", "Y", 10, 1)]
        )

        assert result == {"value": "correct"}


def test_equijoin():
    G = nx.DiGraph()
    G.add_node("x")
    G.add_node("y")
    G.add_node("z")
    G.add_edge("x", "x")
    G.add_edge("y", "y")

    qry = """
    MATCH (n)-->(n)
    RETURN ID(n)
    """
    assert GrandCypher(G).run(qry) == {
        "ID(n)": ["x", "y"]
    }


def test_equijoin2():
    G = nx.DiGraph()
    G.add_node("x")
    G.add_node("y")
    G.add_node("z")
    G.add_edge("x", "y")
    G.add_edge("y", "x")
    G.add_edge("x", "x")
    G.add_edge("z", "x")

    qry = """
    MATCH (n)-->(n)
    RETURN ID(n)
    """
    assert GrandCypher(G).run(qry) == {
        "ID(n)": ["x"]
    }
