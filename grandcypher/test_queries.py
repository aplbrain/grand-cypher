import networkx as nx
import pytest

from . import _GrandCypherGrammar, _GrandCypherTransformer, GrandCypher


class TestWorking:
    def test_simple_structural_match(self):
        tree = _GrandCypherGrammar.parse(
            """
        MATCH (A)-[B]->(C)
        RETURN A
        """
        )
        host = nx.DiGraph()
        host.add_edge("x", "y")
        host.add_edge("y", "z")
        gct = _GrandCypherTransformer(host)
        gct.transform(tree)
        assert len(gct._get_true_matches()) == 2

    def test_simple_structural_match_returns_nodes(self):
        tree = _GrandCypherGrammar.parse(
            """
        MATCH (A)-[B]->(C)
        RETURN A
        """
        )
        host = nx.DiGraph()
        host.add_edge("x", "y")
        host.add_edge("y", "z")
        gct = _GrandCypherTransformer(host)
        gct.transform(tree)
        returns = gct.returns()
        assert "A" in returns
        assert len(returns["A"]) == 2

    def test_simple_structural_match_returns_node_attributes(self):
        tree = _GrandCypherGrammar.parse(
            """
        MATCH (A)-[B]->(C)
        RETURN A.dinnertime
        """
        )
        host = nx.DiGraph()
        host.add_edge("x", "y")
        host.add_edge("y", "z")
        host.add_node("x", dinnertime="no thanks I already ate")
        gct = _GrandCypherTransformer(host)
        gct.transform(tree)
        returns = gct.returns()
        assert "A" not in returns
        assert "A.dinnertime" in returns
        assert len(returns["A.dinnertime"]) == 2


class TestSimpleAPI:
    def test_simple_api(self):
        host = nx.DiGraph()
        host.add_edge("x", "y")
        host.add_edge("y", "z")
        host.add_node("x", dinnertime="no thanks I already ate")

        qry = """
        MATCH (A)-[B]->(C)
        RETURN A.dinnertime
        """

        assert len(GrandCypher(host).run(qry)["A.dinnertime"]) == 2

    def test_simple_api_triangles(self):
        host = nx.DiGraph()
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

    def test_simple_api_single_node_where(self):
        host = nx.DiGraph()
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

    def test_simple_api_single_node_multi_where(self):
        host = nx.DiGraph()
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

    def test_simple_api_single_node_multi_where_2(self):
        host = nx.DiGraph()
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

    def test_null_where(self):
        host = nx.DiGraph()
        host.add_node("x", foo="foo")
        host.add_node("y")
        host.add_node("z")

        qry = """
        MATCH (A)
        WHERE A.foo iS nUlL
        RETURN A.foo
        """
        assert len(GrandCypher(host).run(qry)["A.foo"]) == 2

    def test_simple_api_multi_node_multi_where(self):
        host = nx.DiGraph()
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

    def test_simple_api_anonymous_edge(self):
        host = nx.DiGraph()
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

    def test_simple_api_anonymous_node(self):
        host = nx.DiGraph()
        host.add_edge("x", "y")
        host.add_edge("y", "z")
        host.add_edge("x", "z")

        qry = """
        MATCH () -[]-> (B)
        RETURN B
        """
        res = GrandCypher(host).run(qry)
        assert len(res) == 1
        assert list(res.values())[0] == ["y", "z", "z"]

        qry = """
        MATCH () <-[]- (B)
        RETURN B
        """
        res = GrandCypher(host).run(qry)
        assert len(res) == 1
        assert list(res.values())[0] == ["x", "x", "y"]
        print(res)

    def test_single_edge_where(self):
        host = nx.DiGraph()
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

    def test_simple_api_single_edge_where(self):
        host = nx.DiGraph()
        host.add_edge("x", "y")
        host.add_edge("y", "z", foo="bar")
        host.add_edge("z", "x")

        qry = """
        MATCH (A)-[AB]->(B)
        WHERE AB.foo == "bar"
        RETURN A
        """

        assert len(GrandCypher(host).run(qry)["A"]) == 1

    def test_simple_api_two_edge_where_clauses_same_edge(self):
        host = nx.DiGraph()
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

    def test_simple_api_two_edge_where_clauses_diff_edge(self):
        host = nx.DiGraph()
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
        print(GrandCypher(host).run(qry))
        assert len(GrandCypher(host).run(qry)["AB"]) == 1


class TestKarate:
    def test_simple_multi_edge(self):
        qry = """
        MATCH (A)-[]->(B)
        MATCH (B)-[]->(C)
        WHERE A.club == "Mr. Hi"
        RETURN A.club, B.club
        """
        assert len(GrandCypher(nx.karate_club_graph()).run(qry)["A.club"]) == 544


class TestDictAttributes:
    def test_node_dict(self):
        qry = """
        MATCH (A {type: "foo"})-[]->(B)
        RETURN A
        """
        host = nx.DiGraph()
        host.add_node("Y", type="foo")
        host.add_node("X", type="bar")
        host.add_edge("X", "Y")
        host.add_edge("Y", "Z", type="foo")
        host.add_edge("X", "Z", type="bar")

        assert len(GrandCypher(host).run(qry)["A"]) == 1

    def test_null_value(self):
        host = nx.DiGraph()
        host.add_node("x", foo="foo")
        host.add_node("y")
        host.add_node("z")

        qry = """
        MATCH (A{foo:NuLl})
        RETURN A.foo
        """
        assert len(GrandCypher(host).run(qry)["A.foo"]) == 2


class TestLimitSkip:
    def test_limit_only(self):
        qry = """
        MATCH (A)-[]->(B)
        MATCH (B)-[]->(C)
        WHERE A.club == "Mr. Hi"
        RETURN A.club, B.club
        LIMIT 10
        """
        assert len(GrandCypher(nx.karate_club_graph()).run(qry)["A.club"]) == 10

    def test_skip_only(self):
        qry = """
        MATCH (A)-[]->(B)
        MATCH (B)-[]->(C)
        WHERE A.club == "Mr. Hi"
        RETURN A.club, B.club
        SKIP 10
        """
        assert len(GrandCypher(nx.karate_club_graph()).run(qry)["A.club"]) == 544 - 10

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

    def test_single_node_query(self):
        """
        Test that you can search for individual nodes with properties
        """

        qry = """
        MATCH (c)
        WHERE c.name = "London"
        RETURN c
        """

        host = nx.DiGraph()
        host.add_node("London", type="City", name="London")

        assert len(GrandCypher(host).run(qry)["c"]) == 1

    def test_multi_node_query(self):
        """
        Test that you can search for individual nodes with properties
        """

        qry = """
        MATCH (c)-[]->(b)
        WHERE c.name = "London"
        AND b.type = "City"
        RETURN b, c
        """

        host = nx.DiGraph()
        host.add_node("London", type="City", name="London")
        host.add_node("NYC", type="City", name="NYC")
        host.add_edge("London", "NYC")

        assert len(GrandCypher(host).run(qry)["c"]) == 1

    def test_left_or_right_direction_with_where(self):
        host = nx.DiGraph()
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

    def test_disconected_multi_match(self):
        host = nx.DiGraph()
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

    def test_chained_edges(self):
        host = nx.DiGraph()
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

    def test_chained_backward_edges(self):
        host = nx.DiGraph()
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

    def test_undirected(self):
        host = nx.DiGraph()
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

    def test_anonymous_node(self):
        host = nx.DiGraph()
        host.add_node("x", name="x")
        host.add_node("y", name="y")
        host.add_node("z", name="z")

        host.add_edge("x", "y")
        host.add_edge("z", "y")

        qry = """Match () -[]-> (B) <-[]- ()  return B.name"""
        res = GrandCypher(host).run(qry)
        assert len(res) == 1
        assert res["B.name"] == ["y", "y"]

    def test_complex_where(self):
        host = nx.DiGraph()
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
        assert res["A"] == ["x", "y"]
        assert res["B"] == ["y", "z"]


class TestDistinct:
    def test_basic_distinct1(self):
        host = nx.DiGraph()
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

    def test_basic_distinct2(self):
        host = nx.DiGraph()
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
        assert "Alice" in res["n.name"] and "Bob" in res["n.name"] and "Carol" in res["n.name"] and "Greg" in res["n.name"]


    def test_distinct_with_relationships(self):
        host = nx.DiGraph()
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


    def test_distinct_with_limit_and_skip(self):
        host = nx.DiGraph()
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


    def test_distinct_on_complex_graph(self):
        host = nx.DiGraph()
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
        assert len(res["n.name"]) == 3  # should account for paths without considering duplicate names
        assert "Alice" in res["n.name"] and "Bob" in res["n.name"] and "Carol" in res["n.name"]
        assert len(res["m.name"]) == 3  # should account for paths without considering duplicate names

    def test_distinct_with_attributes(self):
        host = nx.DiGraph()
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
    def test_order_by_single_field_ascending(self):
        host = nx.DiGraph()
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

    def test_order_by_single_field_descending(self):
        host = nx.DiGraph()
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

    def test_order_by_single_field_no_direction_provided(self):
        host = nx.DiGraph()
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

    def test_order_by_multiple_fields(self):
        host = nx.DiGraph()
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

    def test_order_by_with_limit(self):
        host = nx.DiGraph()
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

    def test_order_by_with_skip(self):
        host = nx.DiGraph()
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

    def test_order_by_with_distinct(self):
        host = nx.DiGraph()
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
        assert res["n.name"] == ['Greg', 'Bob', 'Alice', 'Carol']
        assert res["n.age"] == [32, 30, 25, 25]

    def test_error_on_order_by_with_distinct_and_non_returned_field(self):
        host = nx.DiGraph()
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
            res = GrandCypher(host).run(qry)

    def test_order_by_with_non_returned_field(self):
        host = nx.DiGraph()
        host.add_node("a", name="Alice", age=25)
        host.add_node("b", name="Bob", age=30)
        host.add_node("c", name="Carol", age=20)

        qry = """
        MATCH (n)
        RETURN n.name ORDER BY n.age ASC
        """
        res = GrandCypher(host).run(qry)
        assert res["n.name"] == ["Carol", "Alice", "Bob"]


class TestVariableLengthRelationship:
    def test_single_variable_length_relationship(self):
        host = nx.DiGraph()
        host.add_node("x", foo=12)
        host.add_node("y", foo=13)
        host.add_node("z", foo=16)
        host.add_edge("x", "y", bar="1")
        host.add_edge("y", "z", bar="2")
        host.add_edge("z", "x", bar="3")

        qry = """
        MATCH (A)-[r*0]->(B)
        RETURN A, B, r
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 3
        assert res["A"] == ["x", "y", "z"]
        assert res["B"] == ["x", "y", "z"]
        assert res["r"] == [[None], [None], [None]]

        qry = """
        MATCH (A)-[r*1]->(B)
        RETURN A, B, r
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 3
        assert res["A"] == ["x", "y", "z"]
        assert res["B"] == ["y", "z", "x"]
        assert res["r"] == [[{"bar": "1"}], [{"bar": "2"}], [{"bar": "3"}]]

        qry = """
        MATCH (A)-[r*2]->(B)
        RETURN A, B, r
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 3
        assert res["A"] == ["x", "y", "z"]
        assert res["B"] == ["z", "x", "y"]
        assert res["r"] == [
            [{"bar": "1"}, {"bar": "2"}],
            [{"bar": "2"}, {"bar": "3"}],
            [{"bar": "3"}, {"bar": "1"}],
        ]

    def test_complex_variable_length_relationship(self):
        host = nx.DiGraph()
        host.add_node("x", foo=12)
        host.add_node("y", foo=13)
        host.add_node("z", foo=16)
        host.add_edge("x", "y", bar="1")
        host.add_edge("y", "z", bar="2")
        host.add_edge("z", "x", bar="3")

        qry = """
        MATCH (A)-[r*0..2]->(B)
        RETURN A, B, r
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 3
        assert res["A"] == ["x", "y", "z", "x", "y", "z", "x", "y", "z"]
        assert res["B"] == ["x", "y", "z", "y", "z", "x", "z", "x", "y"]
        assert res["r"] == [
            [None],
            [None],
            [None],
            [{"bar": "1"}],
            [{"bar": "2"}],
            [{"bar": "3"}],
            [{"bar": "1"}, {"bar": "2"}],
            [{"bar": "2"}, {"bar": "3"}],
            [{"bar": "3"}, {"bar": "1"}],
        ]


class TestType:
    def test_host_no_edge_type(self):
        host = nx.DiGraph()
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

    def test_edge_type(self):
        host = nx.DiGraph()
        host.add_node("x")
        host.add_node("y")
        host.add_node("z")
        host.add_edge("x", "y", __labels__={"Edge", "XY"}, bar="1")
        host.add_edge("y", "z", __labels__={"Edge", "YZ"}, bar="2")
        host.add_edge("z", "x", __labels__={"Edge", "ZX"}, bar="3")

        qry = """
        MATCH (A)-[:XY]->(B)
        RETURN A, B
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["A"] == ["x"]
        assert res["B"] == ["y"]

        qry = """
        MATCH (A)-[:Edge]->(B)
        RETURN A, B
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["A"] == ["x", "y", "z"]
        assert res["B"] == ["y", "z", "x"]

        qry = """
        MATCH (A)-[r:Edge]->(B)
        where r.bar == "2"
        RETURN A, B
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["A"] == ["y"]
        assert res["B"] == ["z"]

    def test_edge_type_hop(self):
        host = nx.DiGraph()
        host.add_node("x")
        host.add_node("y")
        host.add_node("z")
        host.add_edge("x", "y", __labels__={"Edge", "XY"})
        host.add_edge("y", "z", __labels__={"Edge", "YZ"})
        host.add_edge("z", "x", __labels__={"Edge", "ZX"})

        qry = """
        MATCH (A)-[:XY*2]->(B)
        RETURN A, B
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["A"] == []
        assert res["B"] == []

        qry = """
        MATCH (A)-[:XY*0..2]->(B)
        RETURN A, B
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["A"] == ["x", "y", "z", "x"]
        assert res["B"] == ["x", "y", "z", "y"]

        qry = """
        MATCH (A)-[r:Edge*0..2]->(B)
        RETURN A, B, r
        """

        res = GrandCypher(host).run(qry)

        assert len(res) == 3
        assert res["A"] == ["x", "y", "z", "x", "y", "z", "x", "y", "z"]
        assert res["B"] == ["x", "y", "z", "y", "z", "x", "z", "x", "y"]
        assert res["r"] == [
            [None],
            [None],
            [None],
            [{"__labels__": {"Edge", "XY"}}],
            [{"__labels__": {"Edge", "YZ"}}],
            [{"__labels__": {"Edge", "ZX"}}],
            [{"__labels__": {"Edge", "XY"}}, {"__labels__": {"Edge", "YZ"}}],
            [{"__labels__": {"Edge", "YZ"}}, {"__labels__": {"Edge", "ZX"}}],
            [{"__labels__": {"Edge", "ZX"}}, {"__labels__": {"Edge", "XY"}}],
        ]

    def test_host_no_node_type(self):
        host = nx.DiGraph()
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

    def test_node_type(self):
        host = nx.DiGraph()
        host.add_node("x", __labels__=set(["Node", "X"]), foo="1")
        host.add_node("y", __labels__=set(["Node", "Y"]), foo="2")
        host.add_node("z", __labels__=set(["Node", "Z"]), foo="3")
        host.add_edge("x", "y")
        host.add_edge("y", "z")
        host.add_edge("z", "x")

        qry = """
        MATCH (A)-->(B:Node)
        RETURN A, B
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["A"] == ["x", "y", "z"]
        assert res["B"] == ["y", "z", "x"]

        qry = """
        MATCH (A:Node)-->(B:X)
        RETURN A, B
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["A"] == ["z"]
        assert res["B"] == ["x"]

        qry = """
        MATCH (A:Node)-->(B)
        where A.foo == "2"
        RETURN A, B
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["A"] == ["y"]
        assert res["B"] == ["z"]

    def test_node_type_edge_hop(self):
        host = nx.DiGraph()
        host.add_node("x", __labels__=set(["Node", "X"]), foo="1")
        host.add_node("y", __labels__=set(["Node", "Y"]), foo="2")
        host.add_node("z", __labels__=set(["Node", "Z"]), foo="3")
        host.add_edge("x", "y")
        host.add_edge("y", "z")

        qry = """
        MATCH (A:Node)-[*0..1]->(B:X)
        RETURN A, B
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["A"] == ["x"]
        assert res["B"] == ["x"]

        qry = """
        MATCH (A:Node)-[*0..2]->(B{foo:"2"})
        RETURN A, B
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["A"] == ["y", "x"]
        assert res["B"] == ["y", "y"]

        qry = """
        MATCH (A:X)-[*0..2]->(B)
        where B.foo == "1" or B.foo == "3"
        RETURN A, B
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 2
        assert res["A"] == ["x", "x"]
        assert res["B"] == ["x", "z"]


class TestSpecialCases:
    def test_two_edge_hop_with_edge_node_type(self):
        host = nx.DiGraph()
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
        return A, B, c
        """

        res = GrandCypher(host).run(qry)
        assert len(res) == 3

        C_1_indices = [i for i, v in enumerate(res["A"]) if v == "C_1_1"]
        C_2_indices = [i for i, v in enumerate(res["A"]) if v == "C_2_1"]
        assert len(C_1_indices) + len(C_2_indices) == len(res["A"])

        assert set(res["B"][i] for i in C_1_indices) == set(["C_1_1", "C_1_2", "C_1_3"])
        assert set(res["c"][i] for i in C_1_indices) == set(
            ["C_1_1", "C_1_2", "C_1_3", "a_1_1", "a_1_2", "a_2_1"]
        )

        assert set(res["B"][i] for i in C_2_indices) == set(["C_2_1", "C_2_2"])
        assert set(res["c"][i] for i in C_2_indices) == set(["C_2_1", "C_2_2", "a_2_1"])


class TestComments:
    def test_line_comments(self):
        host = nx.DiGraph()
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

    def test_end_of_line_comments(self):
        host = nx.DiGraph()
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

    def test_every_line_comments(self):
        host = nx.DiGraph()
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

    def test_mid_query_comment(self):
        host = nx.DiGraph()
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
    def test_starts_with(self):
        host = nx.DiGraph()
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

    def test_ends_with(self):
        host = nx.DiGraph()
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

    def test_contains(self):
        host = nx.DiGraph()
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
    def test_not(self):
        host = nx.DiGraph()
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

    def test_doublenot(self):
        host = nx.DiGraph()
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

    def test_nested_nots_in_statements(self):
        host = nx.DiGraph()
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
    def test_path(self):
        host = nx.DiGraph()
        host.add_node("x", name="x")
        host.add_node("y", name="y")
        host.add_node("z", name="z")

        host.add_edge("x", "y", foo="bar")
        host.add_edge("y", "z",)

        qry = """
        MATCH P = ()-[r*2]->()
        RETURN P
        LIMIT 1
        """

        res = GrandCypher(host).run(qry)
        assert len(res["P"][0]) == 5
