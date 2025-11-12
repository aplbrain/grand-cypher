import networkx as nx

from . import GrandCypher


def test_where():
    """
    Test the case where multiple nodes are hinted
    """
    host = nx.DiGraph()
    host.add_node(1, type="node1", name="Home")
    host.add_node(2, type="node1", name="Work")
    host.add_node(3, type="node1", name="School")
    host.add_node(4, type="node2", name="Library")
    host.add_node(5, type="node2", name="Park")
    host.add_edge(1, 2)
    host.add_edge(1, 3)
    host.add_edge(2, 4)
    host.add_edge(3, 4)
    host.add_edge(4, 5)
    host.add_edge(5, 1)

    qry = """
    MATCH (A)-[r]->(B)
    where A.type = "node1" and (B.type == "node1" or B.type == "node2")
    RETURN A.name, B.name
    """

    gc = GrandCypher(host)
    res = gc.run(qry)
    assert res == {"A.name": ["Home", "Home", "Work", "School"],
                   "B.name": ["Work", "School", "Library", "Library"]}



def test_where_unsupported():
    """
    Test the case where multiple nodes are hinted
    """
    host = nx.DiGraph()
    host.add_node(1, name="Home")
    host.add_node(2, name="Work")
    host.add_edge(1, 2)

    qry = """
    MATCH (A)-[r]->(B)
    where A.name = "School" Or A.name in ["Home"]
    RETURN A.name, B.name
    """

    gc = GrandCypher(host)
    res = gc.run(qry)
    assert res == {"A.name": ["Home"],
                   "B.name": ["Work"]}
