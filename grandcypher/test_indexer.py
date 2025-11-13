import pytest
from .indexer import (
    SKIP, AND, OR, Compare, IndexerConditionRunner, NoIndexQuerier, ArrayAttributeIndexer,
    IncrementIndexQuerier)


# ----- STUB CLASSES FOR TESTING -----

class FakeQuerier:
    """Returns comparator functions that return fixed sets."""
    def __init__(self, attr_results):
        self.attr_results = attr_results   # dict op → set

    def get_comparator(self, op):
        return lambda value: self.attr_results[op]


class FakeIndexer:
    """Return fake querier per attribute."""
    def __init__(self, mapping):
        # mapping: attr → {op → set_of_ids}
        self.mapping = mapping

    def get_index_querier(self, attr):
        if attr not in self.mapping:
            raise KeyError(f"No such attribute: {attr}")
        return FakeQuerier(self.mapping[attr])


def test_skip_returns_empty_set():
    s = SKIP()
    indexer = FakeIndexer({})
    assert s(indexer) == set()


def test_compare_returns_correct_mapping():
    indexer = FakeIndexer({
        "age": {
            ">": {10, 11},
        }
    })

    c = Compare(">", "A.age", 20)
    result = c(indexer)

    assert result == {"A": {10, 11}}


def test_and_basic_intersection():
    indexer = FakeIndexer({
        "age": {">": {1,2,3}},
        "height": {"<": {2,3,4}},
    })

    left  = Compare(">", "A.age", 20)       # {"A": {1,2,3}}
    right = Compare("<", "A.height", 100)   # {"A": {2,3,4}}

    node = AND(left, right)
    result = node(indexer)

    assert result == {"A": {2,3}}


def test_and_left_is_skip():
    """AND where left is SKIP → returns right"""
    indexer = FakeIndexer({
        "age": {">": {1,2,3}},
    })

    left = SKIP()
    right = Compare(">", "A.age", 20)
    node = AND(left, right)

    assert node(indexer) == {"A": {1,2,3}}


def test_and_right_is_skip():
    """AND where right is SKIP → returns left"""
    indexer = FakeIndexer({
        "age": {">": {1}},
    })

    left = Compare(">", "A.age", 20)
    right = SKIP()
    node = AND(left, right)

    assert node(indexer) == {"A": {1}}


def test_and_two_variables():
    """AND merging independent variables"""
    indexer = FakeIndexer({
        "age": {">": {1,2}},
        "score": {"<": {5,6}},
    })

    a = Compare(">", "A.age", 20)        # {"A": {1,2}}
    b = Compare("<", "B.score", 200)     # {"B": {5,6}}

    node = AND(a, b)
    result = node(indexer)

    assert result == {
        "A": {1,2},
        "B": {5,6},
    }


def test_or_union():
    """OR union merging"""
    indexer = FakeIndexer({
        "age": {">": {1,2}, "<": {2,3}},
    })

    a = Compare(">", "A.age", 20)      # {"A": {1,2}}
    b = Compare("<", "A.age", 100)     # {"A": {2,3}}

    node = OR(a, b)
    result = node(indexer)

    assert result == {"A": {1,2,3}}


def test_or_disjoint_keys():
    """OR with different variables"""
    indexer = FakeIndexer({
        "age": {">": {1}},
        "score": {"<": {9}},
    })

    a = Compare(">", "A.age", 0)         # {"A": {1}}
    b = Compare("<", "B.score", 100)     # {"B": {9}}

    result = OR(a, b)(indexer)

    assert result == {
        "A": {1},
        "B": {9},
    }


def test_runner_executes_ast():
    """Test IndexerConditionRunner"""
    indexer = FakeIndexer({
        "age": {">": {7}},
    })

    ast = Compare(">", "A.age", 10)
    runner = IndexerConditionRunner(indexer)

    assert runner.find(ast) == {"A": {7}}


# ==========================================================
# TESTS FOR COMPLEX NESTED ASTs
# ==========================================================


def test_nested_ast():
    """Nested AND + OR"""
    indexer = FakeIndexer({
        "age": {">": {1,2,3}, "<": {3,4}},
        "score": {"==": {10}},
    })

    ast = AND(
        OR(
            Compare(">", "A.age", 10),   # {1,2,3}
            Compare("<", "A.age", 100),  # {3,4}
        ),
        Compare("==", "B.score", 10)     # {10}
    )

    result = ast(indexer)

    assert result == {
        "A": {1,2,3,4},
        "B": {10},
    }


def test_or_with_skip():
    """Test OR collapsing keys with SKIP"""
    indexer = FakeIndexer({
        "age": {">": {5}},
    })

    ast = OR(
        SKIP(),                         # {}
        Compare(">", "A.age", 10)       # {"A": {5}}
    )

    result = ast(indexer)
    assert result == {"A": {5}}


# ==========================================================
# TESTS FOR NoIndexQuerier
# ==========================================================


@pytest.fixture
def noindex_querier() -> NoIndexQuerier:
    entity_ids = ["A", "B", "C", "D", "E"]
    entity_attrs = [3, None, 7, 3, 10]
    return NoIndexQuerier("age", entity_ids, entity_attrs)



class TestNoIndexQuerier:

    def test_lt(self, noindex_querier: NoIndexQuerier):
        result = noindex_querier.lt(5)
        # A(3), D(3) < 5; ignore None; C(7), E(10) are >5
        assert result == {"A", "D"}

    def test_gt(self, noindex_querier: NoIndexQuerier):
        result = noindex_querier.gt(5)
        assert result == {"C", "E"}

    def test_ge(self, noindex_querier: NoIndexQuerier):
        result = noindex_querier.ge(3)
        # A(3), C(7), D(3), E(10)
        assert result == {"A", "C", "D", "E"}

    def test_le(self, noindex_querier: NoIndexQuerier):
        result = noindex_querier.le(3)
        assert result == {"A", "D"}

    def test_eq(self, noindex_querier: NoIndexQuerier):
        result = noindex_querier.eq(3)
        assert result == {"A", "D"}

    def test_ne(self, noindex_querier: NoIndexQuerier):
        result = noindex_querier.ne(3)
        # B(None) ignored → remaining: C(7), E(10)
        assert result == {"C", "E"}

    def test_eq_none_ignored(self, noindex_querier: NoIndexQuerier):
        # Should always return empty because None is ignored in comparisons
        result = noindex_querier.eq(None)
        assert result == set()

    def test_get_comparator_supported_ops(self, noindex_querier: NoIndexQuerier):
        assert noindex_querier.get_comparator("<") == noindex_querier.lt
        assert noindex_querier.get_comparator("<=") == noindex_querier.le
        assert noindex_querier.get_comparator(">") == noindex_querier.gt
        assert noindex_querier.get_comparator(">=") == noindex_querier.ge
        assert noindex_querier.get_comparator("==") == noindex_querier.eq
        assert noindex_querier.get_comparator("=") == noindex_querier.eq
        assert noindex_querier.get_comparator("!=") == noindex_querier.ne
        assert noindex_querier.get_comparator("<>") == noindex_querier.ne

    def test_get_comparator_unsupported_operator(self, noindex_querier: NoIndexQuerier):
        with pytest.raises(ValueError):
            noindex_querier.get_comparator("IN")

        with pytest.raises(ValueError):
            noindex_querier.get_comparator("LIKE")

        with pytest.raises(ValueError):
            noindex_querier.get_comparator("===")

    def test_all(self):
        q = NoIndexQuerier(
            key="",
            indexed_entity_ids=[3, 4, 1, 2, 5, 6],
            indexed_entity_attributes=[2, 2, 1, 1, 3, 3]
        )
        assert q.lt(2) == {1, 2}
        assert q.gt(2) == {5, 6}
        assert q.le(2) == {3, 4, 1, 2}
        assert q.ge(2) == {3, 4, 5, 6}
        assert q.eq(2) == {3, 4}
        assert q.ne(2) == {1, 2, 5, 6}


@pytest.fixture
def inc_index_querier() -> NoIndexQuerier:
    entity_ids = ["A", "C", "D", "E"]
    entity_attrs = [3, 7, 3, 10]
    return NoIndexQuerier("age", entity_ids, entity_attrs)


class TestIncrementIndexQuerier:

    def test_lt(self, inc_index_querier: NoIndexQuerier):
        result = inc_index_querier.lt(5)
        # A(3), D(3) < 5; ignore None; C(7), E(10) are >5
        assert result == {"A", "D"}

    def test_gt(self, inc_index_querier: NoIndexQuerier):
        result = inc_index_querier.gt(5)
        assert result == {"C", "E"}

    def test_ge(self, inc_index_querier: NoIndexQuerier):
        result = inc_index_querier.ge(3)
        # A(3), C(7), D(3), E(10)
        assert result == {"A", "C", "D", "E"}

    def test_le(self, inc_index_querier: NoIndexQuerier):
        result = inc_index_querier.le(3)
        assert result == {"A", "D"}

    def test_eq(self, inc_index_querier: NoIndexQuerier):
        result = inc_index_querier.eq(3)
        assert result == {"A", "D"}

    def test_ne(self, inc_index_querier: NoIndexQuerier):
        result = inc_index_querier.ne(3)
        # B(None) ignored → remaining: C(7), E(10)
        assert result == {"C", "E"}

    def test_eq_none_ignored(self, inc_index_querier: NoIndexQuerier):
        # Should always return empty because None is ignored in comparisons
        result = inc_index_querier.eq(None)
        assert result == set()

    def test_get_comparator_supported_ops(self, inc_index_querier: NoIndexQuerier):
        assert inc_index_querier.get_comparator("<") == inc_index_querier.lt
        assert inc_index_querier.get_comparator("<=") == inc_index_querier.le
        assert inc_index_querier.get_comparator(">") == inc_index_querier.gt
        assert inc_index_querier.get_comparator(">=") == inc_index_querier.ge
        assert inc_index_querier.get_comparator("==") == inc_index_querier.eq
        assert inc_index_querier.get_comparator("=") == inc_index_querier.eq
        assert inc_index_querier.get_comparator("!=") == inc_index_querier.ne
        assert inc_index_querier.get_comparator("<>") == inc_index_querier.ne

    def test_get_comparator_unsupported_operator(self, inc_index_querier: NoIndexQuerier):
        with pytest.raises(ValueError):
            inc_index_querier.get_comparator("IN")

        with pytest.raises(ValueError):
            inc_index_querier.get_comparator("LIKE")

        with pytest.raises(ValueError):
            inc_index_querier.get_comparator("===")

    def test_all(self):
        q = IncrementIndexQuerier(
            key="",
            indexed_entity_ids=[1, 2, 3, 4, 5, 6],
            indexed_entity_attributes=[1, 1, 2, 2, 3, 3]
        )
        assert q.lt(2) == {1, 2}
        assert q.gt(2) == {5, 6}
        assert q.le(2) == {1, 2, 3, 4}
        assert q.ge(2) == {3, 4, 5, 6}
        assert q.eq(2) == {3, 4}
        assert q.ne(2) == {1, 2, 5, 6}


class TestArrayAttributeIndexer:
    def test_create_indices(self):
        indexer = ArrayAttributeIndexer(
            entity_ids=[3, 4, 1, 2, 5, 6],
            entity_attributes=[{"k1": 2, "k2": 2},
                               {"k1": 2, "k2": 2},
                               {"k1": 1, "k2": 1},
                               {"k1": 1, "k2": 1},
                               {"k1": 3, "k2": 3},
                               {"k1": 3, "k2": 3}]
        )

        assert len(indexer.indexed_entity_ids) == 0
        assert len(indexer.indexed_entity_attributes) == 0

        indexer.create_indices(["k1"])
        assert indexer.indexed_entity_ids["k1"] == [1, 2, 3, 4, 5, 6]
        assert indexer.indexed_entity_attributes["k1"] == [1, 1, 2, 2, 3, 3]

    def test_get_index_querier(self):
        indexer = ArrayAttributeIndexer(
            entity_ids=[3, 4, 1, 2, 5, 6],
            entity_attributes=[{"k1": 2, "k2": 2},
                               {"k1": 2, "k2": 2},
                               {"k1": 1, "k2": 1},
                               {"k1": 1, "k2": 1},
                               {"k1": 3, "k2": 3},
                               {"k1": 3, "k2": 3}]
        )


        indexer.create_indices(["k1"])

        incr_querier = indexer.get_index_querier("k1")
        assert incr_querier.indexed_entity_ids == [1, 2, 3, 4, 5, 6]
        assert incr_querier.indexed_entity_attributes == [1, 1, 2, 2, 3, 3]

        no_querier = indexer.get_index_querier("k2")
        assert no_querier.indexed_entity_ids == [3, 4, 1, 2, 5, 6]
        assert no_querier.indexed_entity_attributes == [2, 2, 1, 1, 3, 3]
