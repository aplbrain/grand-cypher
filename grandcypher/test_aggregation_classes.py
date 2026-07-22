import networkx as nx
import pytest

from . import Avg, Count, GrandCypher, Max, Min, Sum


@pytest.mark.parametrize(
    ("aggregation", "expected"),
    [
        (Count, 3),
        (Sum, 3),
        (Avg, 1),
        (Max, 2),
        (Min, 1),
    ],
)
def test_aggregation_expression_preserves_existing_null_behavior(aggregation, expected):
    result = aggregation("value").evaluate({"value": [1, None, 2]}, [])

    assert result == {(): expected}


def test_aggregation_expression_groups_values():
    result = Sum("value").evaluate(
        {"group": ["a", "a", "b"], "value": [1, 2, 5]}, ["group"]
    )

    assert result == {("a",): 3, ("b",): 5}


def test_aggregation_alias_order_and_multiple_functions():
    host = nx.DiGraph()
    host.add_nodes_from(
        [
            ("a", {"group": "x", "value": 1}),
            ("b", {"group": "x", "value": 3}),
            ("c", {"group": "y", "value": 10}),
        ]
    )

    result = GrandCypher(host).run(
        "MATCH (n) RETURN n.group, SUM(n.value) AS total, AVG(n.value) AS average "
        "ORDER BY SUM(n.value) DESC"
    )

    assert result == {
        "n.group": ["y", "x"],
        "total": [10, 4],
        "average": [10, 2],
    }


def test_aggregation_query_can_be_reused():
    host = nx.DiGraph()
    host.add_nodes_from([("a", {"group": "x"}), ("b", {"group": "x"})])
    grand_cypher = GrandCypher(host)
    query = "MATCH (n) RETURN n.group, COUNT(n)"

    expected = {"n.group": ["x"], "COUNT(n)": [2]}
    assert grand_cypher.run(query) == expected
    assert grand_cypher.run(query) == expected


def test_aliased_ordered_aggregation_query_can_be_reused():
    host = nx.DiGraph()
    host.add_nodes_from(
        [("a", {"group": "x", "value": 1}), ("b", {"group": "y", "value": 2})]
    )
    grand_cypher = GrandCypher(host)
    query = (
        "MATCH (n) RETURN n.group, SUM(n.value) AS total "
        "ORDER BY SUM(n.value) DESC"
    )

    expected = {"n.group": ["y", "x"], "total": [2, 1]}
    assert grand_cypher.run(query) == expected
    assert grand_cypher.run(query) == expected
