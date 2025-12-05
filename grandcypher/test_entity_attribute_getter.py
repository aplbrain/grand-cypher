"""
Unit tests for EntityAttributeGetter class.

Tests the enhanced EntityAttributeGetter that supports string parsing,
scope variables, and edge references.
"""

import pytest
import networkx as nx
from . import EntityAttributeGetter
from .struct import Match


@pytest.fixture
def simple_graph():
    """Simple graph for testing."""
    host = nx.DiGraph()
    host.add_node("A", name="Alice", value=10)
    host.add_node("B", name="Bob", value=20)
    host.add_node("C", name="Charlie", value=30)
    host.add_edge("A", "B", weight=5)
    host.add_edge("B", "C", weight=15)
    return host


@pytest.fixture
def simple_match(simple_graph):
    """Create a simple match for testing."""
    return Match(
        node_mappings={"n": "A", "m": "B"},
        where_results=None,
        edge_mapping=None
    )


class TestEntityAttributeGetterInit:
    """Tests for EntityAttributeGetter constructor."""

    def test_init_simple_entity(self):
        """Test initializing with simple entity reference: 'n'"""
        getter = EntityAttributeGetter("n")
        assert getter.entity == "n"
        assert getter.attribute is None

    def test_init_entity_with_attribute(self):
        """Test initializing with entity.attribute: 'n.name'"""
        getter = EntityAttributeGetter("n.name")
        assert getter.entity == "n"
        assert getter.attribute == "name"

    def test_init_nested_attribute(self):
        """Test parsing with nested dots (only first dot splits)"""
        getter = EntityAttributeGetter("n.data.value")
        assert getter.entity == "n"
        assert getter.attribute == "data.value"  # Everything after first dot


class TestEntityAttributeGetterEvaluate:
    """Tests for EntityAttributeGetter.evaluate() method."""

    def test_evaluate_node_attribute(self, simple_graph, simple_match):
        """Test getting node attribute from match"""
        getter = EntityAttributeGetter("n.name")
        result = getter.evaluate(simple_match, simple_graph)
        assert result == "Alice"  # Node A has name="Alice"

    def test_evaluate_node_id(self, simple_graph, simple_match):
        """Test getting full node dictionary (no attribute)"""
        getter = EntityAttributeGetter("n")
        result = getter.evaluate(simple_match, simple_graph)
        assert result == {"name": "Alice", "value": 10}  # n returns full node dictionary

    def test_evaluate_nonexistent_attribute(self, simple_graph, simple_match):
        """Test getting nonexistent attribute returns None"""
        getter = EntityAttributeGetter("n.nonexistent")
        result = getter.evaluate(simple_match, simple_graph)
        assert result is None

    def test_evaluate_nonexistent_entity(self, simple_graph, simple_match):
        """Test getting nonexistent entity returns None"""
        getter = EntityAttributeGetter("z")
        result = getter.evaluate(simple_match, simple_graph)
        assert result is None


class TestEntityAttributeGetterScope:
    """Tests for scope variable handling."""

    def test_evaluate_with_scope_simple(self, simple_graph, simple_match):
        """Test scope variable takes priority over node mappings"""
        scope = {"n": {"name": "ScopeName", "value": 100}}
        getter = EntityAttributeGetter("n.name")
        result = getter.evaluate(simple_match, simple_graph, scope=scope)
        # Should get from scope, not from node mapping
        assert result == "ScopeName"

    def test_evaluate_with_scope_entity_only(self, simple_graph, simple_match):
        """Test getting simple scope variable (no attribute)"""
        scope = {"e": {"weight": 10}}
        getter = EntityAttributeGetter("e")
        result = getter.evaluate(simple_match, simple_graph, scope=scope)
        assert result == {"weight": 10}

    def test_evaluate_scope_non_dict(self, simple_graph, simple_match):
        """Test scope variable that is not a dict"""
        scope = {"n": "simple_value"}
        getter = EntityAttributeGetter("n.name")
        result = getter.evaluate(simple_match, simple_graph, scope=scope)
        # Trying to access attribute on non-dict should return None
        assert result is None

    def test_evaluate_scope_priority_order(self, simple_graph, simple_match):
        """Test that scope takes priority over node_mappings"""
        # simple_match has n -> "A" mapping
        # scope has n with different value
        scope = {"n": {"name": "ScopePriority"}}
        getter = EntityAttributeGetter("n.name")
        result = getter.evaluate(simple_match, simple_graph, scope=scope)
        # Should get from scope (priority 1), not node (priority 2)
        assert result == "ScopePriority"


class TestEntityAttributeGetterStrRepresentation:
    """Tests for __str__() and __repr__() methods."""

    def test_str_simple_entity(self):
        """Test __str__() with simple entity"""
        getter = EntityAttributeGetter("n")
        assert str(getter) == "n"

    def test_str_entity_with_attribute(self):
        """Test __str__() with entity.attribute"""
        getter = EntityAttributeGetter("n.name")
        assert str(getter) == "n.name"

    def test_repr_simple_entity(self):
        """Test __repr__() with simple entity"""
        getter = EntityAttributeGetter("m")
        assert repr(getter) == "EntityAttributeGetter('m')"

    def test_repr_entity_with_attribute(self):
        """Test __repr__() with entity.attribute"""
        getter = EntityAttributeGetter("r.weight")
        assert repr(getter) == "EntityAttributeGetter('r'.'weight')"


class TestEntityAttributeGetterIntegration:
    """Integration tests with real Cypher-like scenarios."""

    def test_multiple_attributes_on_different_nodes(self, simple_graph):
        """Test accessing attributes on different nodes in a match"""
        match = Match(
            node_mappings={"start": "A", "end": "C"},
            where_results=None,
            edge_mapping=None
        )

        getter_start = EntityAttributeGetter("start.name")
        getter_end = EntityAttributeGetter("end.value")

        assert getter_start.evaluate(match, simple_graph) == "Alice"
        assert getter_end.evaluate(match, simple_graph) == 30

    def test_fallback_to_none_pattern(self, simple_graph, simple_match):
        """Test pattern: try attribute, fallback if None"""
        # Node "A" has name="Alice"
        getter = EntityAttributeGetter("n.nickname")
        result = getter.evaluate(simple_match, simple_graph)

        # nickname doesn't exist, should return None
        assert result is None

        # Can then use actual attribute as fallback
        getter2 = EntityAttributeGetter("n.name")
        result2 = getter2.evaluate(simple_match, simple_graph)
        assert result2 == "Alice"
