import networkx as nx
import pytest


from . import GrandCypher

ACCEPTED_GRAPH_TYPES = [nx.MultiDiGraph, nx.DiGraph]


class TestHints:
    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_no_hints(self, graph_type):
        host = graph_type()
        host.add_node(1, type="alien", name="Ford Prefect")
        host.add_node(2, type="human", name="Arthur Dent")
        host.add_node(3, type="alien", name="Zaphod Beeblebrox")
        host.add_node(4, type="dog", name="Fido")
        host.add_edge(1, 4, type="petting")
        host.add_edge(2, 4, type="petting")
        host.add_edge(3, 4, type="petting")

        qry = """
        MATCH (A)-[r]->(B)
        WHERE A.type == "human"
        RETURN A.name
        """

        gc = GrandCypher(host)

        res = gc.run(qry)
        assert res == {"A.name": ["Arthur Dent"]}

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_simple_hint_same_as_full_results(self, graph_type):
        host = graph_type()
        host.add_node(1, type="alien", name="Ford Prefect")
        host.add_node(2, type="human", name="Arthur Dent")
        host.add_node(3, type="alien", name="Zaphod Beeblebrox")
        host.add_node(4, type="dog", name="Fido")
        host.add_edge(1, 4, type="petting")
        host.add_edge(2, 4, type="petting")
        host.add_edge(3, 4, type="petting")

        qry = """
        MATCH (A)-[r]->(B)
        WHERE A.type <> "human"
        RETURN A.name
        """

        gc = GrandCypher(host)
        res = gc.run(qry, hints=[{"A": 1}, {"A": 3}])
        assert res == {"A.name": ["Ford Prefect", "Zaphod Beeblebrox"]}

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_simple_hint(self, graph_type):
        host = graph_type()
        host.add_node(1, type="alien", name="Ford Prefect")
        host.add_node(2, type="human", name="Arthur Dent")
        host.add_node(3, type="alien", name="Zaphod Beeblebrox")
        host.add_node(4, type="dog", name="Fido")
        host.add_edge(1, 4, type="petting")
        host.add_edge(2, 4, type="petting")
        host.add_edge(3, 4, type="petting")

        qry = """
        MATCH (A)-[r]->(B)
        WHERE A.type <> "human"
        RETURN A.name
        """

        gc = GrandCypher(host)
        res = gc.run(qry, hints=[{"A": 3}])
        assert res == {"A.name": ["Zaphod Beeblebrox"]}

        gc = GrandCypher(host)
        res = gc.run(qry, hints=[{"A": 1}])
        assert res == {"A.name": ["Ford Prefect"]}

    @pytest.mark.parametrize("graph_type", ACCEPTED_GRAPH_TYPES)
    def test_ER_hints(self, graph_type):
        """
        Test random graphs
        """
        host = nx.fast_gnp_random_graph(100, 0.1, directed=nx.is_directed(graph_type()))
        hints = [{"A": 1}]
        gc = GrandCypher(host)
        qry = """
        MATCH (A)-[r]->(B) RETURN A
        """
        res = gc.run(qry, hints=hints)
        assert all(r == 1 for r in res["A"])
