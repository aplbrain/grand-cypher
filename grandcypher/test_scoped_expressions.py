import networkx as nx

from . import (
    ArithmeticExpression,
    CompoundCondition,
    ScalarFunctionExpression,
    _OPERATORS,
    _lower,
)
from .struct import Match
from .types import AttributeRef, EntityRef


def _match(**node_mappings):
    return Match(
        node_mappings=node_mappings,
        where_results=None,
        edge_mapping=None,
    )


def test_entity_ref_resolves_scoped_value():
    assert EntityRef("item").evaluate(
        _match(), nx.DiGraph(), {}, scope={"item": {"value": 3}}
    ) == {"value": 3}


def test_attribute_ref_resolves_scoped_attribute():
    assert AttributeRef("item", "value").evaluate(
        _match(), nx.DiGraph(), {}, scope={"item": {"value": 3}}
    ) == 3


def test_scope_shadows_graph_entity():
    host = nx.DiGraph()
    host.add_node("graph-node", value=1)
    match = _match(item="graph-node")

    assert AttributeRef("item", "value").evaluate(
        match, host, {}, scope={"item": {"value": 2}}
    ) == 2


def test_missing_scoped_attribute_returns_none():
    assert AttributeRef("item", "missing").evaluate(
        _match(), nx.DiGraph(), {}, scope={"item": {"value": 3}}
    ) is None


def test_non_mapping_scoped_attribute_returns_none():
    assert AttributeRef("item", "value").evaluate(
        _match(), nx.DiGraph(), {}, scope={"item": 3}
    ) is None


def test_attribute_ref_falls_back_to_graph_without_scope_entry():
    host = nx.DiGraph()
    host.add_node("graph-node", value=1)

    assert AttributeRef("item", "value").evaluate(
        _match(item="graph-node"), host, {}, scope={"other": 2}
    ) == 1


def test_scope_propagates_through_scalar_and_arithmetic_expressions():
    lower = ScalarFunctionExpression("toLower", AttributeRef("item", "name"), _lower)
    expression = ArithmeticExpression(AttributeRef("item", "value"), "+", 2)
    scope = {"item": {"name": "ALICE", "value": 3}}

    assert lower.evaluate(_match(), nx.DiGraph(), {}, scope) == "alice"
    assert expression.evaluate(_match(), nx.DiGraph(), {}, scope) == 5


def test_scope_propagates_through_compound_condition():
    condition = CompoundCondition(
        True,
        AttributeRef("item", "value"),
        _OPERATORS[">"],
        2,
    )

    assert condition(
        _match(), nx.DiGraph(), {}, scope={"item": {"value": 3}}
    ) == (True, [True])
