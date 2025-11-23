import pytest
import networkx as nx
from . import GrandCypher


@pytest.fixture
def host_graph():
    host = nx.DiGraph()
    host.add_node("x", __labels__={"Node", "X"}, foo="1")
    host.add_node("y", __labels__={"Node", "Y"}, foo="2")
    host.add_node("z", __labels__={"Node", "Z"}, foo="3")

    host.add_edge("x", "y", name="xy", __labels__={"XY"})
    host.add_edge("y", "z", name="yz", __labels__={"XY"})
    return host



@pytest.fixture
def host_multigraph():
    host = nx.MultiDiGraph()
    host.add_node("x", __labels__={"Node", "X"}, foo="1")
    host.add_node("y", __labels__={"Node", "Y"}, foo="2")
    host.add_node("z", __labels__={"Node", "Z"}, foo="3")

    host.add_edge("x", "y", name="xy", __labels__={"XY"})
    host.add_edge("x", "y", name="xy", __labels__={"XY"})
    host.add_edge("y", "z", name="yz", __labels__={"YZ"})
    return host


def test_hop_2_property_where_access_error(host_graph):
    qry = """
        MATCH (A:X)-[r*2]->(B)
        WHERE r.name = "xy"
        RETURN ID(A), r, ID(B)
    """
    with pytest.raises(TypeError):
        print(GrandCypher(host_graph).run(qry))


def test_hop_2_list_return(host_graph):
    qry = """
        MATCH (A:X)-[r*2]->(B)
        RETURN r
    """
    res = GrandCypher(host_graph).run(qry)
    assert isinstance(res["r"][0], list)
    assert res["r"] == [[{'name': 'xy', '__labels__': {'XY'}}, {'name': 'yz', '__labels__': {'XY'}}]]


def test_hop_2_property_return_access_error(host_graph):
    qry = """
        MATCH (A:X)-[r*2]->(B)
        RETURN A, r.name
    """
    with pytest.raises(TypeError):
        GrandCypher(host_graph).run(qry)


def test_hop_1_property_access_valid(host_graph):
    qry = """
        MATCH (A:X)-[r*1]->(B)
        WHERE r.name = "xy"
        RETURN r.name
    """
    res = GrandCypher(host_graph).run(qry)
    assert res["r.name"] == ['xy']


def test_hop_1_property_access_valid_multi(host_multigraph):
    qry = """
        MATCH (A:X)-[r*1]->(B)
        WHERE r.name = "xy"
        RETURN r.name
    """

    res = GrandCypher(host_multigraph).run(qry)
    assert res["r.name"] == ['xy', "xy"]


def test_hop_1_return_relationship(host_graph):
    qry = """
        MATCH (A:X)-[r*1]->(B)
        RETURN r
    """
    res = GrandCypher(host_graph).run(qry)
    assert res["r"] == [{'name': 'xy', '__labels__': {'XY'}}]


def test_hop_0_r_is_empty_list(host_graph):
    qry = """
        MATCH (A:X)-[r*0]->(B)
        RETURN ID(A), r
    """
    res = GrandCypher(host_graph).run(qry)
    assert res["ID(A)"] == ["x"]
    assert res["r"] == [[]]


def test_hop_range_runtime_error_on_list(host_graph):
    qry = """
        MATCH (A:X)-[r*0..2]->(B)
        RETURN r.name
    """
    with pytest.raises(TypeError):
        GrandCypher(host_graph).run(qry)

