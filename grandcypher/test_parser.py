import networkx as nx

from . import GrandCypherGrammar, GrandCypherTransformer, GrandCypher


class TestParsing:
    def test_simple_match_query(self):
        tree = GrandCypherGrammar.parse(
            """
        MATCH (A)-[B]->(C)
        WHERE A > A
        RETURN A
        """
        )
        assert len(tree.children[0].children) == 3

    def test_case_insensitive(self):
        tree = GrandCypherGrammar.parse(
            """
        mAtCh (A)-[B]->(C)
        WHERe A > A
        return A
        """
        )
        assert len(tree.children[0].children) == 3


class TestWorking:
    def test_simple_structural_match(self):
        tree = GrandCypherGrammar.parse(
            """
        MATCH (A)-[B]->(C)
        RETURN A
        """
        )
        host = nx.DiGraph()
        host.add_edge("x", "y")
        host.add_edge("y", "z")
        gct = GrandCypherTransformer(host)
        gct.transform(tree)
        assert len(gct._get_matches()) == 2

    def test_simple_structural_match_returns_nodes(self):
        tree = GrandCypherGrammar.parse(
            """
        MATCH (A)-[B]->(C)
        RETURN A
        """
        )
        host = nx.DiGraph()
        host.add_edge("x", "y")
        host.add_edge("y", "z")
        gct = GrandCypherTransformer(host)
        gct.transform(tree)
        returns = gct.returns()
        assert "A" in returns
        assert len(returns["A"]) == 2

    def test_simple_structural_match_returns_node_attributes(self):
        tree = GrandCypherGrammar.parse(
            """
        MATCH (A)-[B]->(C)
        RETURN A.dinnertime
        """
        )
        host = nx.DiGraph()
        host.add_edge("x", "y")
        host.add_edge("y", "z")
        host.add_node("x", dinnertime="no thanks I already ate")
        gct = GrandCypherTransformer(host)
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