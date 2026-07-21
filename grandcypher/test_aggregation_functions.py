"""
Unit tests for AggregationFunction classes.

Tests the class-based aggregation architecture (COUNT, SUM, AVG, MAX, MIN).
"""

import pytest
import networkx as nx
from . import COUNT, SUM, AVG, MAX, MIN
from .struct import Match


@pytest.fixture
def simple_graph():
    """Simple graph for testing aggregations."""
    host = nx.DiGraph()
    host.add_node("A", value=10)
    host.add_node("B", value=20)
    host.add_node("C", value=30)
    host.add_edge("A", "B", weight=5)
    host.add_edge("B", "C", weight=15)
    return host


@pytest.fixture
def simple_matches(simple_graph):
    """Create simple matches for testing."""
    matches = []

    # Match 1: A->B
    match1 = Match(
        node_mappings={"n": "A", "m": "B"},
        where_results=None,
        edge_mapping=None
    )
    matches.append(match1)

    # Match 2: B->C
    match2 = Match(
        node_mappings={"n": "B", "m": "C"},
        where_results=None,
        edge_mapping=None
    )
    matches.append(match2)

    return matches


class TestCOUNT:
    """Tests for COUNT aggregation."""

    def test_count_basic(self, simple_graph, simple_matches):
        """Test basic COUNT functionality."""
        agg = COUNT("n", None)
        # Build scope with values extracted from matches
        scope = {
            "n": [m.node_mappings["n"] for m in simple_matches],  # ["A", "B"]
            "m": [m.node_mappings["m"] for m in simple_matches],  # ["B", "C"]
        }
        result = agg.evaluate(simple_matches, simple_graph, {}, ["m"], scope=scope)

        # Should group by 'm' and count 'n' values
        assert len(result) == 2
        assert all(count == 1 for count in result.values())

    def test_count_str(self):
        """Test __str__ representation."""
        agg = COUNT("r", None)
        assert str(agg) == "COUNT(r)"

        agg_with_attr = COUNT("r", "value")
        assert str(agg_with_attr) == "COUNT(r.value)"

    def test_count_with_none(self, simple_graph):
        """Test COUNT excludes None values."""
        # Create matches with None values
        matches = []
        match = Match(
            node_mappings={"n": "A"},
            where_results=None,
            edge_mapping=None
        )
        matches.append(match)

        agg = COUNT("n", "nonexistent")  # This attribute doesn't exist
        # Build scope with None values (attribute doesn't exist)
        scope = {
            "n.nonexistent": [simple_graph.nodes[m.node_mappings["n"]].get("nonexistent") for m in matches],
        }
        result = agg.evaluate(matches, simple_graph, {}, [], scope=scope)

        # COUNT excludes None values
        assert result[()] == 0


class TestSUM:
    """Tests for SUM aggregation."""

    def test_sum_basic(self, simple_graph, simple_matches):
        """Test basic SUM functionality."""
        agg = SUM("n", "value")
        # Build scope with attribute values from graph nodes
        scope = {
            "n.value": [simple_graph.nodes[m.node_mappings["n"]].get("value") for m in simple_matches],
        }
        result = agg.evaluate(simple_matches, simple_graph, {}, [], scope=scope)

        # Should sum all values: 10 + 20 = 30
        assert result[()] == 30

    def test_sum_str(self):
        """Test __str__ representation."""
        agg = SUM("r", "weight")
        assert str(agg) == "SUM(r.weight)"

    def test_sum_with_none(self, simple_graph):
        """Test SUM treats None as 0."""
        matches = []
        match = Match(
            node_mappings={"n": "A"},
            where_results=None,
            edge_mapping=None
        )
        matches.append(match)

        agg = SUM("n", "nonexistent")  # This attribute doesn't exist (None)
        # Build scope with None values
        scope = {
            "n.nonexistent": [simple_graph.nodes[m.node_mappings["n"]].get("nonexistent") for m in matches],
        }
        result = agg.evaluate(matches, simple_graph, {}, [], scope=scope)

        # Should sum to 0 (None treated as 0)
        assert result[()] == 0


class TestAVG:
    """Tests for AVG aggregation."""

    def test_avg_basic(self, simple_graph, simple_matches):
        """Test basic AVG functionality."""
        agg = AVG("n", "value")
        # Build scope with attribute values
        scope = {
            "n.value": [simple_graph.nodes[m.node_mappings["n"]].get("value") for m in simple_matches],
        }
        result = agg.evaluate(simple_matches, simple_graph, {}, [], scope=scope)

        # Should average: (10 + 20) / 2 = 15
        assert result[()] == 15

    def test_avg_str(self):
        """Test __str__ representation."""
        agg = AVG("r", "weight")
        assert str(agg) == "AVG(r.weight)"

    def test_avg_with_none(self, simple_graph):
        """Test AVG treats None as 0."""
        matches = []
        match = Match(
            node_mappings={"n": "A"},
            where_results=None,
            edge_mapping=None
        )
        matches.append(match)

        agg = AVG("n", "nonexistent")
        # Build scope with None values
        scope = {
            "n.nonexistent": [simple_graph.nodes[m.node_mappings["n"]].get("nonexistent") for m in matches],
        }
        result = agg.evaluate(matches, simple_graph, {}, [], scope=scope)

        # Should average to 0
        assert result[()] == 0


class TestMAX:
    """Tests for MAX aggregation."""

    def test_max_basic(self, simple_graph, simple_matches):
        """Test basic MAX functionality."""
        agg = MAX("n", "value")
        # Build scope with attribute values
        scope = {
            "n.value": [simple_graph.nodes[m.node_mappings["n"]].get("value") for m in simple_matches],
        }
        result = agg.evaluate(simple_matches, simple_graph, {}, [], scope=scope)

        # Should find max: max(10, 20) = 20
        assert result[()] == 20

    def test_max_str(self):
        """Test __str__ representation."""
        agg = MAX("r", "weight")
        assert str(agg) == "MAX(r.weight)"

    def test_max_with_none(self, simple_graph):
        """Test MAX treats None as negative infinity."""
        matches = []
        for node_id in ["A", "B"]:
            match = Match(
                node_mappings={"n": node_id},
                where_results=None,
                edge_mapping=None
            )
            matches.append(match)

        agg = MAX("n", "nonexistent")
        # Build scope with None values
        scope = {
            "n.nonexistent": [simple_graph.nodes[m.node_mappings["n"]].get("nonexistent") for m in matches],
        }
        result = agg.evaluate(matches, simple_graph, {}, [], scope=scope)

        # Should return -inf (all None values)
        assert result[()] == -float("inf")


class TestMIN:
    """Tests for MIN aggregation."""

    def test_min_basic(self, simple_graph, simple_matches):
        """Test basic MIN functionality."""
        agg = MIN("n", "value")
        # Build scope with attribute values
        scope = {
            "n.value": [simple_graph.nodes[m.node_mappings["n"]].get("value") for m in simple_matches],
        }
        result = agg.evaluate(simple_matches, simple_graph, {}, [], scope=scope)

        # Should find min: min(10, 20) = 10
        assert result[()] == 10

    def test_min_str(self):
        """Test __str__ representation."""
        agg = MIN("r", "weight")
        assert str(agg) == "MIN(r.weight)"

    def test_min_with_none(self, simple_graph):
        """Test MIN treats None as positive infinity."""
        matches = []
        for node_id in ["A", "B"]:
            match = Match(
                node_mappings={"n": node_id},
                where_results=None,
                edge_mapping=None
            )
            matches.append(match)

        agg = MIN("n", "nonexistent")
        # Build scope with None values
        scope = {
            "n.nonexistent": [simple_graph.nodes[m.node_mappings["n"]].get("nonexistent") for m in matches],
        }
        result = agg.evaluate(matches, simple_graph, {}, [], scope=scope)

        # Should return +inf (all None values)
        assert result[()] == float("inf")


class TestGrouping:
    """Tests for grouping behavior."""

    def test_grouping_by_one_key(self, simple_graph, simple_matches):
        """Test grouping by a single key."""
        agg = COUNT("n", None)
        # Build scope with node mappings
        scope = {
            "n": [m.node_mappings["n"] for m in simple_matches],
            "m": [m.node_mappings["m"] for m in simple_matches],
        }
        result = agg.evaluate(simple_matches, simple_graph, {}, ["m"], scope=scope)

        # Should have 2 groups (one for each 'm' value)
        assert len(result) == 2
        assert ("B",) in result
        assert ("C",) in result

    def test_grouping_by_multiple_keys(self, simple_graph):
        """Test grouping by multiple keys."""
        matches = []
        for i, (n_val, m_val) in enumerate([("A", "B"), ("A", "C"), ("B", "C")]):
            match = Match(
                node_mappings={"n": n_val, "m": m_val, "o": f"O{i}"},
                where_results=None,
                edge_mapping=None
            )
            matches.append(match)

        agg = COUNT("o", None)
        # Build scope with node mappings
        scope = {
            "o": [m.node_mappings["o"] for m in matches],
            "n": [m.node_mappings["n"] for m in matches],
            "m": [m.node_mappings["m"] for m in matches],
        }
        result = agg.evaluate(matches, simple_graph, {}, ["n", "m"], scope=scope)

        # Should have 3 groups (one for each (n, m) combination)
        assert len(result) == 3
        assert ("A", "B") in result
        assert ("A", "C") in result
        assert ("B", "C") in result

    def test_no_grouping(self, simple_graph, simple_matches):
        """Test aggregation without grouping (single group)."""
        agg = COUNT("n", None)
        # Build scope with node mappings
        scope = {
            "n": [m.node_mappings["n"] for m in simple_matches],
        }
        result = agg.evaluate(simple_matches, simple_graph, {}, [], scope=scope)

        # Should have 1 group (empty tuple)
        assert len(result) == 1
        assert () in result
        assert result[()] == 2  # 2 matches total


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_empty_matches(self, simple_graph):
        """Test aggregation with no matches."""
        agg = COUNT("n", None)
        result = agg.evaluate([], simple_graph, {}, [], scope={})

        # Should return empty dict
        assert result == {}

    def test_evaluate_not_implemented(self, simple_graph):
        """Test that base class evaluate() raises NotImplementedError."""
        from grandcypher import AggregationFunction

        agg = AggregationFunction("n", None)
        with pytest.raises(NotImplementedError):
            agg.evaluate([], simple_graph, {}, [], scope={})
