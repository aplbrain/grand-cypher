import networkx as nx

from . import GrandCypher


def test_scalar_to_scalar_comparison():
    host = nx.DiGraph()
    host.add_node("a", first=" ALICE ", second="alice")
    host.add_node("b", first="BOB", second="alice")

    result = GrandCypher(host).run(
        "MATCH (n) WHERE toLower(trim(n.first)) = toLower(n.second) "
        "RETURN ID(n)"
    )

    assert result == {"ID(n)": ["a"]}


def test_aggregation_over_scalar_expression_with_alias_and_order():
    host = nx.DiGraph()
    host.add_nodes_from(
        [
            ("a", {"group": "x", "name": "Al"}),
            ("b", {"group": "x", "name": "Beth"}),
            ("c", {"group": "y", "name": "Charlie"}),
        ]
    )

    result = GrandCypher(host).run(
        "MATCH (n) RETURN n.group, AVG(size(n.name)) AS average "
        "ORDER BY AVG(size(n.name)) DESC"
    )

    assert result == {"n.group": ["y", "x"], "average": [7, 3]}


def test_all_aggregations_accept_scalar_expressions():
    host = nx.DiGraph()
    host.add_nodes_from([("a", {"name": "Al"}), ("b", {"name": "Beth"})])

    result = GrandCypher(host).run(
        "MATCH (n) RETURN COUNT(size(n.name)), SUM(size(n.name)), "
        "MIN(size(n.name)), MAX(size(n.name)), COLLECT(size(n.name))"
    )

    assert result == {
        "COUNT(size(n.name))": [2],
        "SUM(size(n.name))": [6],
        "MIN(size(n.name))": [2],
        "MAX(size(n.name))": [4],
        "COLLECT(size(n.name))": [[2, 4]],
    }


def test_nested_aggregation_preserves_null_behavior():
    host = nx.DiGraph()
    host.add_nodes_from([("a", {"name": "Al"}), ("b", {})])

    result = GrandCypher(host).run(
        "MATCH (n) RETURN COLLECT(size(n.name)), SUM(size(n.name))"
    )

    assert result == {
        "COLLECT(size(n.name))": [[2]],
        "SUM(size(n.name))": [2],
    }


def test_aggregation_accepts_literal_arguments():
    host = nx.DiGraph()
    host.add_nodes_from(["a", "b"])

    result = GrandCypher(host).run(
        "MATCH (n) RETURN COUNT(1), SUM(2), COLLECT(3)"
    )

    assert result == {"COUNT(1)": [2], "SUM(2)": [4], "COLLECT(3)": [[3, 3]]}


def test_aggregation_over_relationship_list_size():
    host = nx.DiGraph()
    host.add_edge("a", "b")
    host.add_edge("b", "c")

    result = GrandCypher(host).run(
        "MATCH (a)-[r*1..2]->(b) RETURN AVG(size(relationships(r)))"
    )

    assert result == {"AVG(size(relationships(r)))": [4 / 3]}


def test_aggregation_over_multigraph_relationship_type():
    host = nx.MultiDiGraph()
    host.add_edge("a", "b", __labels__={"PAID"})
    host.add_edge("a", "b", __labels__={"OWES"})

    result = GrandCypher(host).run(
        "MATCH (a)-[r]->(b) RETURN COLLECT(type(r))"
    )

    assert result == {"COLLECT(type(r))": [["PAID", "OWES"]]}


def test_nested_expression_query_can_be_reused():
    host = nx.DiGraph()
    host.add_nodes_from([("a", {"name": "Al"}), ("b", {"name": "Beth"})])
    grand_cypher = GrandCypher(host)
    query = "MATCH (n) RETURN AVG(size(n.name))"

    expected = {"AVG(size(n.name))": [3]}
    assert grand_cypher.run(query) == expected
    assert grand_cypher.run(query) == expected
