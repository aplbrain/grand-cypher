import pickle

import networkx as nx

from . import GrandCypher, _GrandCypherGrammar


def test_string_functions_in_return_and_where():
    host = nx.DiGraph()
    host.add_node("a", name="  ALICE  ")
    host.add_node("b", name=" Bob ")

    result = GrandCypher(host).run(
        'MATCH (n) WHERE toLower(trim(n.name)) = "alice" '
        "RETURN n.name, toLower(n.name), toUpper(trim(n.name))"
    )

    assert result == {
        "n.name": ["  ALICE  "],
        "toLower(n.name)": ["  alice  "],
        "toUpper(trim(n.name))": ["ALICE"],
    }


def test_coalesce_with_attributes_and_literals():
    host = nx.DiGraph()
    host.add_node("a", name="Alice")
    host.add_node("b", nickname="Bobby")
    host.add_node("c")

    result = GrandCypher(host).run(
        'MATCH (n) RETURN coalesce(n.name, n.nickname, "Unknown") AS display'
    )

    assert result["display"] == ["Alice", "Bobby", "Unknown"]


def test_coalesce_reads_edge_attributes():
    host = nx.DiGraph()
    host.add_edge("a", "b", fallback="edge value")

    result = GrandCypher(host).run(
        "MATCH (a)-[r]->(b) RETURN coalesce(r.missing, r.fallback)"
    )

    assert result["coalesce(r.missing, r.fallback)"] == ["edge value"]


def test_size_with_string_attribute_and_literal():
    host = nx.DiGraph()
    host.add_node("a", name="Alice")
    host.add_node("b", name=None)

    result = GrandCypher(host).run(
        'MATCH (n) WHERE size("hello") = 5 RETURN size(n.name), size("hello")'
    )

    assert result["size(n.name)"] == [5, None]
    assert result['size("hello")'] == [5, 5]


def test_type_with_multigraph_relationships():
    host = nx.MultiDiGraph()
    host.add_edge("a", "b", __labels__={"PAID"})
    host.add_edge("a", "b", __labels__={"OWES"})

    result = GrandCypher(host).run(
        'MATCH (a)-[r]->(b) WHERE type(r) = "PAID" RETURN type(r) AS kind'
    )

    assert result["kind"] == ["PAID"]


def test_scalar_function_arithmetic_composition():
    host = nx.DiGraph()
    host.add_node("a", name="Alice")
    host.add_node("b", name="Bob")

    result = GrandCypher(host).run(
        "MATCH (n) WHERE size(n.name) + 1 > 4 RETURN n.name"
    )

    assert result["n.name"] == ["Alice"]


def test_scalar_query_can_be_reused():
    host = nx.DiGraph()
    host.add_node("a", name="Alice")
    grand_cypher = GrandCypher(host)
    query = "MATCH (n) RETURN toLower(n.name)"

    assert grand_cypher.run(query) == {"toLower(n.name)": ["alice"]}
    assert grand_cypher.run(query) == {"toLower(n.name)": ["alice"]}


def test_scalar_expression_is_picklable():
    tree = _GrandCypherGrammar.parse("MATCH (n) RETURN toLower(n.name)")
    grand_cypher = GrandCypher(nx.DiGraph())
    grand_cypher._transformer.transform(tree)
    expression = grand_cypher._transformer._executors[0]._return_requests[0]

    assert str(pickle.loads(pickle.dumps(expression))) == "toLower(n.name)"
