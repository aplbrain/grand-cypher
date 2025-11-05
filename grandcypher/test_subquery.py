import networkx as nx


from . import GrandCypher

ACCEPTED_GRAPH_TYPES = [nx.MultiDiGraph, nx.DiGraph]


def test_sub_query_2_level():

    host = nx.DiGraph()
    host.add_node("x", age=15)
    host.add_node("y", age=25)
    host.add_node("z", age=35)
    host.add_node("zz", age=45)
    host.add_edge("x", "z")
    host.add_edge("x", "zz")
    host.add_edge("y", "z")

    qry = """
    MATCH (A)
    where EXISTS {
        MATCH (A) --> (B)
        where B.age > 30
    }
    RETURN ID(A)
    """


    res = GrandCypher(host).run(qry)
    assert res == {'ID(A)': ['x', 'y']}


def test_sub_query_2_level_complex_where_condition():

    host = nx.DiGraph()
    host.add_node("x", age=15)
    host.add_node("y", age=25)
    host.add_node("z", age=35)
    host.add_node("zz", age=45)
    host.add_edge("x", "z")
    host.add_edge("x", "zz")
    host.add_edge("y", "z")

    qry = """
    MATCH (A)
    where A.age < 20 and EXISTS {
        MATCH (A) --> (B)
        where B.age > 30
    }
    RETURN ID(A)
    """


    res = GrandCypher(host).run(qry)
    assert res == {'ID(A)': ['x']}


def test_sub_query_3_level():

    host = nx.DiGraph()
    host.add_node("x", age=15)
    host.add_node("y", age=25)
    host.add_node("z", age=35)
    host.add_node("zz", age=45)
    host.add_edge("x", "z")
    host.add_edge("x", "zz")
    host.add_edge("y", "z")

    qry = """
    MATCH (A)
    where EXISTS {
        MATCH (A) --> (B)
        where EXISTS {
            MATCH (B)
            where B.age > 30
        }
    }
    RETURN ID(A)
    """


    res = GrandCypher(host).run(qry)
    assert res == {'ID(A)': ['x', 'y']}

    qry = """
    MATCH (A)
    where EXISTS {
        MATCH (A) --> (B)
        where EXISTS {
            MATCH (B)
            where B.age > 40
        }
    }
    return ID(A)
    """


    res = GrandCypher(host).run(qry)
    assert res == {'ID(A)': ['x']}


def test_negated_edge_edge_label():
    host = nx.DiGraph()
    host.add_node("x")
    host.add_node("y")
    host.add_node("z")
    host.add_edge("x", "y", __labels__={"XY"}, name="XY")
    host.add_edge("x", "z", __labels__={"XZ"}, name="XZ")

    qry = """
    MATCH (A) --> (B)
    where NOT EXISTS {
        MATCH (A) -[:XY]-> (B)
    }
    RETURN ID(A), ID(B)
    """

    res = GrandCypher(host).run(qry)
    assert res == {'ID(A)': ['x'], 'ID(B)': ['z']}


def test_negated_edge_where():
    host = nx.DiGraph()
    host.add_node("x")
    host.add_node("y")
    host.add_node("z")
    host.add_edge("x", "y", __labels__={"XY"}, name="XY")
    host.add_edge("x", "z", __labels__={"XZ"}, name="XZ")

    qry = """
    MATCH (A) --> (B)
    where  NOT EXISTS {
        MATCH (A) -[r]-> (B)
        WHERE r.name = XY
    }
    RETURN ID(A), ID(B)
    """

    res = GrandCypher(host).run(qry)
    assert res == {'ID(A)': ['x'], 'ID(B)': ['z']}
