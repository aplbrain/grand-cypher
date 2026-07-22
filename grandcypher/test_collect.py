import networkx as nx

from . import Collect, GrandCypher


def test_collect_expression_groups_and_excludes_nulls():
    result = Collect("value").evaluate(
        {
            "group": ["a", "a", "a", "b"],
            "value": [1, None, 2, None],
        },
        ["group"],
    )

    assert result == {("a",): [1, 2], ("b",): []}


def test_collect_node_attributes_with_grouping_alias_and_order():
    host = nx.DiGraph()
    host.add_nodes_from(
        [
            ("a", {"group": "x", "value": 1}),
            ("b", {"group": "x", "value": 2}),
            ("c", {"group": "y", "value": 3}),
        ]
    )

    result = GrandCypher(host).run(
        "MATCH (n) RETURN n.group, COLLECT(n.value) AS values "
        "ORDER BY n.group DESC"
    )

    assert result == {"n.group": ["y", "x"], "values": [[3], [1, 2]]}


def test_collect_excludes_missing_values_and_orders_by_aggregate():
    host = nx.DiGraph()
    host.add_nodes_from(
        [
            ("a", {"group": "x", "value": 2}),
            ("b", {"group": "x"}),
            ("c", {"group": "y", "value": 1}),
        ]
    )

    result = GrandCypher(host).run(
        "MATCH (n) RETURN n.group, COLLECT(n.value) "
        "ORDER BY COLLECT(n.value) DESC"
    )

    assert result == {
        "n.group": ["x", "y"],
        "COLLECT(n.value)": [[2], [1]],
    }


def test_collect_edge_attributes_from_multigraph():
    host = nx.MultiDiGraph()
    host.add_node("a", name="Alice")
    host.add_node("b", name="Bob")
    host.add_node("c", name="Charlie")
    host.add_edge("a", "b", amount=10)
    host.add_edge("a", "b", amount=20)
    host.add_edge("a", "c", amount=30)

    result = GrandCypher(host).run(
        "MATCH (n)-[r]->(m) RETURN n.name, m.name, COLLECT(r.amount)"
    )

    assert result == {
        "n.name": ["Alice", "Alice"],
        "m.name": ["Bob", "Charlie"],
        "COLLECT(r.amount)": [[10, 20], [30]],
    }


def test_collect_query_can_be_reused():
    host = nx.DiGraph()
    host.add_nodes_from([("a", {"value": 1}), ("b", {"value": 2})])
    grand_cypher = GrandCypher(host)
    query = "MATCH (n) RETURN COLLECT(n.value)"

    expected = {"COLLECT(n.value)": [[1, 2]]}
    assert grand_cypher.run(query) == expected
    assert grand_cypher.run(query) == expected
