import pickle

import networkx as nx

from grandcypher import GrandCypher
from grandcypher.types import AttributeRef, IDRef, EntityRef


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
