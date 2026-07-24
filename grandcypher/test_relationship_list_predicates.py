import networkx as nx
import pytest

from . import (
    CompoundCondition,
    GrandCypher,
    ListPredicateExpression,
    _OPERATORS,
)
from .struct import Match
from .types import AttributeRef


class EmptyListExpression:
    def evaluate(self, match, host, return_edges, scope=None):
        return []


@pytest.fixture
def path_graph():
    host = nx.DiGraph()
    host.add_node("a", name="Alice")
    host.add_node("b", name="Bob")
    host.add_node("c", name="Charlie")
    host.add_node("d", name="David")
    host.add_edge("a", "b", weight=10, kind="friend")
    host.add_edge("b", "c", weight=20, kind="friend")
    host.add_edge("c", "d", weight=5, kind="blocked")
    return host


def test_relationships_supports_size_in_where_and_return(path_graph):
    result = GrandCypher(path_graph).run(
        "MATCH (a)-[r*1..3]->(b) "
        "WHERE size(relationships(r)) = 2 "
        "RETURN a.name, b.name, size(relationships(r)) AS length"
    )

    assert result == {
        "a.name": ["Alice", "Bob"],
        "b.name": ["Charlie", "David"],
        "length": [2, 2],
    }


@pytest.mark.parametrize(
    ("predicate", "comparison", "starts"),
    [
        ("ALL", "edge.weight > 5", {"Alice"}),
        ("ANY", "edge.weight > 15", {"Alice", "Bob"}),
        ("NONE", "edge.weight < 10", {"Alice"}),
        ("SINGLE", "edge.weight > 15", {"Alice", "Bob"}),
    ],
)
def test_list_predicates(path_graph, predicate, comparison, starts):
    result = GrandCypher(path_graph).run(
        f"MATCH (a)-[r*2]->(b) "
        f"WHERE {predicate}(edge IN relationships(r) WHERE {comparison}) "
        "RETURN a.name"
    )

    assert set(result["a.name"]) == starts


def test_compound_inner_predicate_and_outer_boolean(path_graph):
    result = GrandCypher(path_graph).run(
        "MATCH (a)-[r*2]->(b) "
        "WHERE ALL(edge IN relationships(r) "
        'WHERE edge.weight > 5 AND edge.kind = "friend") '
        'AND a.name = "Alice" '
        "RETURN b.name"
    )

    assert result == {"b.name": ["Charlie"]}


def test_list_predicate_outer_or(path_graph):
    result = GrandCypher(path_graph).run(
        "MATCH (a)-[r*2]->(b) "
        "WHERE ALL(edge IN relationships(r) WHERE edge.weight > 100) "
        'OR a.name = "Alice" '
        "RETURN a.name"
    )

    assert result == {"a.name": ["Alice"]}


@pytest.mark.parametrize(
    ("predicate", "expected"),
    [
        ("ALL", []),
        ("ANY", ["a"]),
        ("NONE", []),
        ("SINGLE", []),
    ],
)
def test_list_predicate_mixed_true_and_null_semantics(predicate, expected):
    host = nx.DiGraph()
    host.add_edge("a", "b", weight=10)
    host.add_edge("b", "c")

    result = GrandCypher(host).run(
        f"MATCH (a)-[r*2]->(b) "
        f"WHERE {predicate}(edge IN relationships(r) WHERE edge.weight > 5) "
        "RETURN ID(a)"
    )

    assert result == {"ID(a)": expected}


@pytest.mark.parametrize("predicate", ["ALL", "ANY", "NONE", "SINGLE"])
def test_list_predicate_null_only_is_filtered(predicate):
    host = nx.DiGraph()
    host.add_edge("a", "b")

    result = GrandCypher(host).run(
        f"MATCH (a)-[r]->(b) "
        f"WHERE {predicate}(edge IN relationships(r) WHERE edge.weight > 5) "
        "RETURN ID(a)"
    )

    assert result == {"ID(a)": []}


def test_relationships_uses_selected_multigraph_edges():
    host = nx.MultiDiGraph()
    host.add_edge("a", "b", weight=1)
    host.add_edge("a", "b", weight=10)

    result = GrandCypher(host).run(
        "MATCH (a)-[r]->(b) "
        "WHERE ALL(edge IN relationships(r) WHERE edge.weight > 5) "
        "RETURN r.weight"
    )

    assert result == {"r.weight": [10]}


def test_relationship_predicate_query_can_be_reused(path_graph):
    grand_cypher = GrandCypher(path_graph)
    query = (
        "MATCH (a)-[r*2]->(b) "
        "WHERE ANY(edge IN relationships(r) WHERE edge.weight > 15) "
        "RETURN a.name"
    )

    expected = {"a.name": ["Alice", "Bob"]}
    assert grand_cypher.run(query) == expected
    assert grand_cypher.run(query) == expected


@pytest.mark.benchmark
def test_benchmark_relationship_list_predicate():
    host = nx.DiGraph()
    for index in range(100):
        host.add_edge(index, index + 1, weight=index % 10)

    result = GrandCypher(host).run(
        "MATCH (a)-[r*2]->(b) "
        "WHERE ALL(edge IN relationships(r) WHERE edge.weight >= 0) "
        "RETURN ID(a)"
    )

    assert len(result["ID(a)"]) == 99


@pytest.mark.parametrize(
    ("predicate", "expected"),
    [("ALL", True), ("ANY", False), ("NONE", True), ("SINGLE", False)],
)
def test_empty_list_semantics(predicate, expected):
    condition = CompoundCondition(
        True, AttributeRef("edge", "weight"), _OPERATORS[">"], 5
    )
    list_predicate = ListPredicateExpression(
        predicate, "edge", EmptyListExpression(), condition
    )
    match = Match(node_mappings={}, where_results=None, edge_mapping=None)

    assert list_predicate(match, nx.DiGraph(), {}) == (expected, [expected])
