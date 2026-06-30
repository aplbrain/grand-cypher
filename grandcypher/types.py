"""Typed operand classes for GrandCypher query processing."""


class EntityRef(str):
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


class AttributeRef(str):
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


class IDRef(str):
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
