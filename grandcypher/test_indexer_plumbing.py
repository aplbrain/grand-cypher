"""Plumbing tests that verify the indexer produces correct hints for grandiso.

These tests mock grandiso.find_motifs_iter to inspect the hints kwarg,
ensuring the indexer narrows candidates correctly (or doesn't when it can't).
"""

from unittest.mock import patch

import grandiso
import networkx as nx

from . import GrandCypher


def _get_hints(host, qry):
    """Run a query and return the hints passed to grandiso."""
    with patch(
        "grandcypher.grandiso.find_motifs_iter",
        wraps=grandiso.find_motifs_iter,
    ) as mock:
        GrandCypher(host).run(qry)
        return mock.call_args.kwargs["hints"]


def _hint_values(hints, entity):
    """Extract the set of node IDs hinted for an entity."""
    return {h[entity] for h in hints if entity in h}


class TestIndexerProducesHints:

    def test_equality_filters_to_matching_node(self):
        host = nx.DiGraph()
        host.add_node(1, name="Alice")
        host.add_node(2, name="Bob")
        host.add_node(3, name="Charlie")
        host.add_edge(1, 2)
        host.add_edge(2, 3)

        hints = _get_hints(host, 'MATCH (A) WHERE A.name == "Bob" RETURN A')
        assert _hint_values(hints, "A") == {2}

    def test_inequality_filters_to_matching_nodes(self):
        host = nx.DiGraph()
        host.add_node(1, age=10)
        host.add_node(2, age=30)
        host.add_node(3, age=50)
        host.add_edge(1, 2)
        host.add_edge(2, 3)

        hints = _get_hints(host, "MATCH (A) WHERE A.age > 20 RETURN A")
        assert _hint_values(hints, "A") == {2, 3}

    def test_hint_only_constrains_referenced_entity(self):
        host = nx.DiGraph()
        host.add_node(1, age=10)
        host.add_node(2, age=30)
        host.add_node(3, age=50)
        host.add_edge(1, 2)
        host.add_edge(2, 3)

        hints = _get_hints(host, "MATCH (A)-[]->(B) WHERE A.age > 20 RETURN A, B")
        assert _hint_values(hints, "A") == {2, 3}
        assert all("B" not in h for h in hints)


class TestIndexerFallsBackToFullScan:

    def test_id_equality_produces_hints(self):
        host = nx.DiGraph()
        host.add_node(1, name="Alice")
        host.add_node(2, name="Bob")
        host.add_node(3, name="Charlie")
        host.add_edge(1, 2)
        host.add_edge(2, 3)

        hints = _get_hints(host, "MATCH (A) WHERE ID(A) == 2 RETURN A")
        assert _hint_values(hints, "A") == {2}

    def test_id_inequality_produces_no_hints(self):
        host = nx.DiGraph()
        host.add_node(1, name="Alice")
        host.add_node(2, name="Bob")
        host.add_edge(1, 2)

        hints = _get_hints(host, "MATCH (A) WHERE ID(A) > 1 RETURN A")
        assert hints == []

    def test_arithmetic_produces_no_hints(self):
        host = nx.DiGraph()
        host.add_node(1, age=10)
        host.add_node(2, age=30)
        host.add_edge(1, 2)

        hints = _get_hints(host, "MATCH (A) WHERE A.age + 10 > 30 RETURN A")
        assert hints == []

    def test_edge_attribute_produces_no_hints(self):
        host = nx.DiGraph()
        host.add_node(1, name="Alice")
        host.add_node(2, name="Bob")
        host.add_edge(1, 2, weight=10)
        host.add_edge(2, 1, weight=50)

        hints = _get_hints(host, "MATCH (A)-[E]->(B) WHERE E.weight > 20 RETURN A, B")
        assert hints == []
