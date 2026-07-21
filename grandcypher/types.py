"""Typed operand classes for GrandCypher query processing."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Expression(Protocol):
    """A query expression that can be evaluated for one graph match."""

    def evaluate(self, match, host, return_edges, scope=None) -> Any:
        ...


class ExpressionBase:
    """Marker base for efficient runtime expression dispatch."""


class EntityRef(str, ExpressionBase):
    """Bare node/edge reference, e.g. A.

    str subclass because the RETURN path uses these as dict keys
    and passes them through isinstance(item, str) checks.
    """
    def __new__(cls, entity_name):
        instance = super().__new__(cls, str(entity_name))
        instance.entity_name = str(entity_name)
        return instance

    def __getnewargs__(self):
        return (self.entity_name,)

    def evaluate(self, match, host, return_edges, scope=None):
        raise TypeError(
            f"Cannot use bare entity '{self}' in a comparison. "
            f"Use a property like '{self}.attribute' or ID({self})."
        )


class AttributeRef(str, ExpressionBase):
    """Node/edge attribute reference, e.g. A.age.

    str subclass because the RETURN path uses these as dict keys
    and passes them through isinstance(item, str) checks.
    """
    def __new__(cls, entity_name, attribute):
        instance = super().__new__(cls, f"{entity_name}.{attribute}")
        instance.entity_name = str(entity_name)
        instance.attribute = str(attribute)
        return instance

    def __getnewargs__(self):
        return (self.entity_name, self.attribute)

    def evaluate(self, match, host, return_edges, scope=None):
        if self.entity_name in match.node_mappings:
            host_node_id = match.node_mappings[self.entity_name]
            return host.nodes[host_node_id].get(self.attribute)
        if self.entity_name in return_edges:
            edge_mapping = return_edges[self.entity_name]
            host_edges = match.mth.edge(*edge_mapping).edges
            if len(host_edges) != 1:
                raise TypeError("Cannot get edge attribute from multiple edges")
            edge = host_edges[0]
            edge_id = (edge.u, edge.v, edge.k) if host.is_multigraph() else (edge.u, edge.v)
            return host.edges[edge_id].get(self.attribute)
        raise IndexError(f"Entity {self} not in graph.")


class IDRef(str, ExpressionBase):
    """Reference to ID(A) in WHERE clauses.

    str subclass because the RETURN path uses these as dict keys
    and passes them through isinstance(item, str) checks.
    """
    def __new__(cls, entity_name):
        instance = super().__new__(cls, f"ID({entity_name})")
        instance.entity_name = str(entity_name)
        return instance

    def __getnewargs__(self):
        return (self.entity_name,)

    def evaluate(self, match, host, return_edges, scope=None):
        if self.entity_name in match.node_mappings:
            return match.node_mappings[self.entity_name]
        raise IndexError(f"Entity {self.entity_name} not in match.")
