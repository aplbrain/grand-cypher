import pickle

import networkx as nx
import pytest

from grandcypher import ArithmeticExpression, GrandCypher
from grandcypher.struct import EdgeHopKey, EdgeMapping, HopSpec, Match
from grandcypher.types import AttributeRef, Expression, IDRef, EntityRef


def test_attribute_ref_pickle_roundtrip():
    ref = AttributeRef('a', 'name')
    restored = pickle.loads(pickle.dumps(ref))
    assert restored == 'a.name'
    assert type(restored) is AttributeRef
    assert restored.entity_name == 'a'
    assert restored.attribute == 'name'


def test_id_ref_pickle_roundtrip():
    ref = IDRef('a')
    restored = pickle.loads(pickle.dumps(ref))
    assert restored == 'ID(a)'
    assert type(restored) is IDRef
    assert restored.entity_name == 'a'


def test_entity_ref_pickle_roundtrip():
    ref = EntityRef('a')
    restored = pickle.loads(pickle.dumps(ref))
    assert restored == 'a'
    assert type(restored) is EntityRef
    assert restored.entity_name == 'a'


def test_typed_references_implement_expression_protocol():
    assert isinstance(AttributeRef("a", "name"), Expression)
    assert isinstance(IDRef("a"), Expression)
    assert isinstance(EntityRef("a"), Expression)


def test_typed_reference_evaluation():
    host = nx.DiGraph()
    host.add_node("alice", age=30)
    match = Match(node_mappings={"a": "alice"}, where_results=None, edge_mapping=None)

    assert AttributeRef("a", "age").evaluate(match, host, {}) == 30
    assert IDRef("a").evaluate(match, host, {}) == "alice"
    with pytest.raises(TypeError, match="Cannot use bare entity"):
        EntityRef("a").evaluate(match, host, {})


@pytest.mark.parametrize("graph_type", [nx.DiGraph, nx.MultiDiGraph])
def test_edge_attribute_reference_evaluation(graph_type):
    host = graph_type()
    edge_key = host.add_edge("alice", "bob", since=2020)
    hop = HopSpec(edge_id=("a", "b"), nodes=("a", "b"), hop_count=1)
    match = Match(
        node_mappings={"a": "alice", "b": "bob"},
        where_results=None,
        edge_mapping=EdgeMapping(
            edge_hop_map={("a", "b"): hop},
            edge_key_map={
                ("a", "b"): EdgeHopKey(("a", "b"), (edge_key,)),
            },
        ),
    )

    assert AttributeRef("r", "since").evaluate(
        match, host, {"r": ("a", "b")}
    ) == 2020


def test_arithmetic_expression_implements_protocol():
    host = nx.DiGraph()
    host.add_node("alice", age=30)
    match = Match(node_mappings={"a": "alice"}, where_results=None, edge_mapping=None)
    expression = ArithmeticExpression(AttributeRef("a", "age"), "+", 2)

    assert isinstance(expression, Expression)
    assert expression.evaluate(match, host, {}) == 32


def test_query_results_pickle_roundtrip():
    host = nx.DiGraph()
    host.add_node("x", name="Alice", age=30)
    host.add_node("y", name="Bob", age=25)
    host.add_edge("x", "y", since=2020)

    qry = """
    MATCH (A)-[E]->(B)
    WHERE A.name == "Alice"
    RETURN A, A.name, A.age, ID(A), B
    """

    results = GrandCypher(host).run(qry)
    restored = pickle.loads(pickle.dumps(results))

    assert restored == results
    for key in results:
        assert type(restored[key]) is type(results[key])
    for key in restored:
        restored_key_type = type(key)
        assert any(type(k) is restored_key_type for k in results)
