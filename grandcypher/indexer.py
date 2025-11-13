"""
indexer modules contains index related classes
"""

from itertools import chain
from typing import Any, Callable, Hashable, TypeVar, Union
from bisect import bisect_left, bisect_right
from cachetools import LRUCache

T = TypeVar("T")
U = TypeVar("U")


IndexDomainType = dict[Hashable, list[Hashable]]
IndexerConditionAST = Callable[["ArrayAttributeIndexer"], IndexDomainType]


class IncrementIndexQuerier:
    """This class takes in attribues sorted in ascending order and provide quick searching funtionality on it.
    """
    def __init__(self, key: Any, indexed_entity_ids: list[T], indexed_entity_attributes: list[U]):
        self.key = key
        self.indexed_entity_ids: list[T] = indexed_entity_ids
        self.indexed_entity_attributes: list[U] = indexed_entity_attributes

    def lt(self, val: U) -> set[T]:
        idx = bisect_left(self.indexed_entity_attributes, val)
        if idx:
            return set(self.indexed_entity_ids[:idx])
        return set()

    def gt(self, val: U) -> set[T]:
        idx = bisect_right(self.indexed_entity_attributes, val)
        if idx != len(self.indexed_entity_attributes):
            return set(self.indexed_entity_ids[idx:])
        return set()

    def ge(self, val: U) -> set[T]:
        idx = bisect_left(self.indexed_entity_attributes, val)
        if idx != len(self.indexed_entity_attributes):
            return set(self.indexed_entity_ids[idx:])
        return set()

    def le(self, val: U) -> set[T]:
        idx = bisect_right(self.indexed_entity_attributes, val)
        if idx:
            return set(self.indexed_entity_ids[:idx])
        return set()

    def eq(self, val: U) -> set[T]:
        lo = bisect_left(self.indexed_entity_attributes, val)
        if lo == len(self.indexed_entity_attributes) or self.indexed_entity_attributes[lo] != val:
            return []

        hi = bisect_right(self.indexed_entity_attributes, val, lo=lo)
        return  set(self.indexed_entity_ids[lo: hi])

    def ne(self, val: U) -> set[T]:
        lo = bisect_left(self.indexed_entity_attributes, val)
        if lo == len(self.indexed_entity_attributes) or self.indexed_entity_attributes[lo] != val:
            return set(self.indexed_entity_ids[::])

        hi = bisect_right(self.indexed_entity_attributes, val, lo=lo)
        return set(self.indexed_entity_ids[i]
                   for i in range(len(self.indexed_entity_attributes)) if i < lo or i >= hi)

    def get_comparator(self, op: str) -> Callable[[U], set[T]]:
        if op == "<":
            return self.lt
        if op == "<=":
            return self.le
        if op == ">":
            return self.gt
        if op == ">=":
            return self.ge
        if op == "==" or op == "=":
            return self.eq
        if op == "!=" or op == "<>":
            return self.ne
        raise ValueError(f"operator {op!r} is not supported")


class NoIndexQuerier:
    """This class assumes there is no ordering in the entity attributes and hence will do the full search
    """
    def __init__(self, key: Any, indexed_entity_ids: list[T], indexed_entity_attributes: list[U]):
        self.key = key
        self.indexed_entity_ids: list[T] = indexed_entity_ids
        self.indexed_entity_attributes: list[U] = indexed_entity_attributes

    def lt(self, val: U) -> set[T]:
        return set(eid for eid, eat in zip(self.indexed_entity_ids, self.indexed_entity_attributes)
                   if eat is not None and eat < val)

    def gt(self, val: U) -> set[T]:
        return set(eid for eid, eat in zip(self.indexed_entity_ids, self.indexed_entity_attributes)
                   if eat is not None and eat > val)

    def ge(self, val: U) -> set[T]:
        return set(eid for eid, eat in zip(self.indexed_entity_ids, self.indexed_entity_attributes)
                   if eat is not None and eat >= val)

    def le(self, val: U) -> set[T]:
        return set(eid for eid, eat in zip(self.indexed_entity_ids, self.indexed_entity_attributes)
                   if eat is not None and eat <= val)

    def eq(self, val: U) -> set[T]:
        return set(eid for eid, eat in zip(self.indexed_entity_ids, self.indexed_entity_attributes)
                   if eat is not None and eat == val)

    def ne(self, val: U) -> set[T]:
        return set(eid for eid, eat in zip(self.indexed_entity_ids, self.indexed_entity_attributes)
                   if eat is not None and eat != val)

    def get_comparator(self, op: str) -> Callable[[U], set[T]]:
        if op == "<":
            return self.lt
        if op == "<=":
            return self.le
        if op == ">":
            return self.gt
        if op == ">=":
            return self.ge
        if op == "==" or op == "=":
            return self.eq
        if op == "!=" or op == "<>":
            return self.ne
        raise ValueError(f"operator {op!r} is not supported")


class ArrayAttributeIndexer:
    """ArrayAttributeIndexer is an interface to create indexed attributes in ascending order.

    ArrayAttributeIndexer provide get_index_querier that will return either IncrementIndexQuerier
    or NoIndexQuerier, both are compatible in term of funtionality. While IncrementIndexQuerier works
    efficiently if attribute values are soreted in ascending order, NoIndexQuerier is less optimal
    as it does full scan for searching.

    ArrayAttributeIndexer will not have any update when attributes change their values.

    Example:
    >>> graph = nx.DiGraph()
    >>> graph.add_node("A", weight=2, name="A")
    >>> graph.add_node("B", weight=1, name="B")
    >>> indexer = ArrayAttributeIndexer(entity_ids=list(graph.nodes.keys()), entity_attributes=list(graph.nodes.values()))
    >>> indexer.create_indices(keys=["weight"])
    >>> q1 = indexer.get_index_querier("weight")
    >>> assert isinstance(q1,IncrementIndexQuerier)
    >>> q2 = indexer.get_index_querier("name")
    >>> assert isinstance(q2,NoIndexQuerier)
    """
    def __init__(self, entity_ids: list[T], entity_attributes: list[dict[str, U]]):
        self.entity_ids: list[T] = entity_ids
        self.entity_attributes: list[dict[str, U]] = entity_attributes
        self.indexed_entity_ids: dict[str, list[T]] = {}
        self.indexed_entity_attributes: dict[str, list[U]] = {}
        self._querier_cache = LRUCache(maxsize=4)

    def create_indices(self, keys: list[Any]):
        """create indices on keys.
        This will create indices on keys in entity_attributes.
        """
        for key in keys:
            self._make_index(
                entity_ids=self.entity_ids,
                entity_attribute_values=[attribs.get(key) for attribs in self.entity_attributes],
                key=key
            )

    def _make_index(self, entity_ids: list[T], entity_attribute_values: list[U], key: Hashable):
        sorted_indices = sorted(list(range(len(entity_attribute_values))), key=lambda i: entity_attribute_values[i])
        self.indexed_entity_ids[key] = [entity_ids[i] for i in sorted_indices]
        self.indexed_entity_attributes[key] = [entity_attribute_values[i] for i in sorted_indices]

    def get_index_querier(self, key: Hashable) -> Union[IncrementIndexQuerier, NoIndexQuerier]:
        """return IncrementIndexQuerier if key is indexed, else NoIndexQuerier"""
        if key not in self._querier_cache:
            if key not in self.indexed_entity_ids:
                self._querier_cache[key] = NoIndexQuerier(
                    key,
                    self.entity_ids,
                    [attribs.get(key) for attribs in self.entity_attributes])
            else:
                self._querier_cache[key] = IncrementIndexQuerier(
                    key=key,
                    indexed_entity_ids=self.indexed_entity_ids[key],
                    indexed_entity_attributes=self.indexed_entity_attributes[key],
                )

        return self._querier_cache[key]


class SKIP:
    def __call__(self, indexer):
        return set()


class AND:
    def __init__(self, a, b):
        self._a = a
        self._b = b

    def __call__(self, indexer):
        ret_a = self._a(indexer)
        ret_b = self._b(indexer)
        if ret_a is None:
            return ret_b
        elif ret_b is None:
            return ret_a
        ret = {}
        common_keys = [k for k in ret_a if k in ret_b]
        ret = {}
        for k in common_keys:
            ret[k] = set(ret_a.pop(k)).intersection(ret_b.pop(k))
        ret.update(ret_a)
        ret.update(ret_b)
        return ret


class OR:
    def __init__(self, a, b):
        self._a = a
        self._b = b

    def __call__(self, indexer):
        ret_a = self._a(indexer)
        ret_b = self._b(indexer)
        if ret_a is None or ret_b is None:
            return None
        common_keys = [k for k in ret_a if k in ret_b]
        ret = {}
        for k in common_keys:
            ret[k] = set(chain.from_iterable((ret_a.pop(k), ret_b.pop(k))))
        ret.update(ret_a)
        ret.update(ret_b)
        return ret


class Compare:
    def __init__(self, op, key, value):
        self._op = op
        self._key = key
        self._value = value

    def __call__(self, indexer: ArrayAttributeIndexer):
        name_attr = self._key.split(".")
        if len(name_attr) == 1:
            try:
                iter(self._value)
                value = self._value
            except TypeError:
                value = [self._value]
            return {self._key: set(value)}
        name, attr= name_attr
        querier = indexer.get_index_querier(attr)
        comparator = querier.get_comparator(self._op)
        return {name: comparator(self._value)}


class UnsupportedOp:
    """Unsupported Operator will return None upon being called"""
    def __init__(self, op, key, value):
        self._op = op
        self._key = key
        self._value = value

    def __call__(self, indexer):
        return None


class IndexerConditionRunner:
    """interface to run Indexer Condition AST"""
    def __init__(self, indexer: ArrayAttributeIndexer):
        self._indexer = indexer

    def find(self, condition_ast: IndexerConditionAST) -> IndexDomainType:
        """find entity domain (entity ids) given a Indexer Condition AST"""
        ret =  condition_ast(self._indexer)
        return ret
