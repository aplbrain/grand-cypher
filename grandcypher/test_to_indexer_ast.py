from . import (
    ArithmeticExpression,
    AttributeRef,
    Condition,
    CompoundCondition,
    EntityRef,
    IDRef,
    LambdaCompareCondition,
    AND,
    OR,
    to_indexer_ast,
)

# These map to your earlier AST Indexer nodes:
from .indexer import (
    Compare as IndexerCompare,
    AND as IndexerAnd,
    OR as IndexerOr,
    UnsupportedOp
)


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def make_lambda_compare(op_str):
    """operator_function doesn't matter for indexer ast"""
    return LambdaCompareCondition(operator_function=lambda x,y: True, operator=op_str)


# -------------------------------------------------
# TESTS
# -------------------------------------------------


# === 1. Simple Compare ============================

def test_simple_compare_to_indexer_ast():
    cond = LambdaCompareCondition(lambda x,y: True, ">")
    entity = AttributeRef("A", "age")
    value = 10

    ast = to_indexer_ast(cond, entity, value)

    assert isinstance(ast, IndexerCompare)
    assert ast._op == ">"
    assert ast._key == AttributeRef("A", "age")
    assert ast._value == 10


# === 2. CompoundCondition unwrapping ==============

def test_compound_condition_unwraps_into_compare():
    inner = LambdaCompareCondition(lambda x,y: True, "<")
    comp = CompoundCondition(
        should_be=True,
        left=AttributeRef("B", "height"),
        operator=inner,
        right=200,
    )

    ast = to_indexer_ast(comp)

    assert isinstance(ast, IndexerCompare)
    assert ast._op == "<"
    assert ast._key == AttributeRef("B", "height")
    assert ast._value == 200


# === 3. AND maps to IndexerAnd ====================

def test_and_becomes_indexer_and():
    left = LambdaCompareCondition(lambda x,y: True, ">")
    right = LambdaCompareCondition(lambda x,y: True, "<")

    cond = AND(
        CompoundCondition(True, AttributeRef("A", "age"), left, 10),
        CompoundCondition(True, AttributeRef("B", "score"), right, 5),
    )

    ast = to_indexer_ast(cond)

    assert isinstance(ast, IndexerAnd)
    assert isinstance(ast._a, IndexerCompare)
    assert isinstance(ast._b, IndexerCompare)

    assert ast._a._key == AttributeRef("A", "age")
    assert ast._b._key == AttributeRef("B", "score")


# === 4. OR maps to IndexerOr ======================

def test_or_becomes_indexer_or():
    left = LambdaCompareCondition(lambda x,y: True, ">")
    right = LambdaCompareCondition(lambda x,y: True, "<")

    cond = OR(
        CompoundCondition(True, AttributeRef("A", "age"), left, 10),
        CompoundCondition(True, AttributeRef("A", "age"), right, 200),
    )

    ast = to_indexer_ast(cond)

    assert isinstance(ast, IndexerOr)
    assert isinstance(ast._a, IndexerCompare)
    assert isinstance(ast._b, IndexerCompare)


# === 5. Nested AND/OR =============================

def test_nested_ast():
    c1 = CompoundCondition(True, AttributeRef("A", "age"), make_lambda_compare(">"), 10)
    c2 = CompoundCondition(True, AttributeRef("B", "score"), make_lambda_compare("<"), 100)
    c3 = CompoundCondition(True, AttributeRef("A", "age"), make_lambda_compare(">"), 30)

    cond = AND(
        c1,
        OR(c2, c3)
    )

    ast = to_indexer_ast(cond)

    assert isinstance(ast, IndexerAnd)
    assert isinstance(ast._a, IndexerCompare)
    assert isinstance(ast._b, IndexerOr)

    assert isinstance(ast._b._a, IndexerCompare)
    assert isinstance(ast._b._b, IndexerCompare)


# === 6. Unsupported condition → UnsupportedOp ==============

def test_unsupported_condition_returns_unsupportedop():
    class UnknownCondition(Condition):
        pass

    cond = UnknownCondition()

    ast = to_indexer_ast(cond)
    assert isinstance(ast, UnsupportedOp)


# === 7. EXISTS or SUBQUERY → SKIP =================
def test_exists_subquery_returns_skip():
    class ExistsCondition(Condition):
        pass

    cond = ExistsCondition()
    ast = to_indexer_ast(cond)

    assert isinstance(ast, UnsupportedOp)


# === 8. IndexerCompare only for AttributeRef left + literal right ===

def test_attribute_ref_with_literal_produces_compare():
    cond = CompoundCondition(
        should_be=True,
        left=AttributeRef("A", "age"),
        operator=make_lambda_compare(">"),
        right=30,
    )
    ast = to_indexer_ast(cond)
    assert isinstance(ast, IndexerCompare)
    assert ast._key == AttributeRef("A", "age")
    assert ast._value == 30


def test_bare_entity_ref_left_returns_unsupportedop():
    cond = CompoundCondition(
        should_be=True,
        left=EntityRef("A"),
        operator=make_lambda_compare(">"),
        right=5,
    )
    ast = to_indexer_ast(cond)
    assert isinstance(ast, UnsupportedOp)


def test_literal_left_attribute_ref_right_returns_unsupportedop():
    cond = CompoundCondition(
        should_be=True,
        left=100,
        operator=make_lambda_compare("<"),
        right=AttributeRef("A", "age"),
    )
    ast = to_indexer_ast(cond)
    assert isinstance(ast, UnsupportedOp)


def test_arithmetic_left_returns_unsupportedop():
    arith = ArithmeticExpression(AttributeRef("A", "x"), "-", AttributeRef("A", "y"))
    cond = CompoundCondition(
        should_be=True,
        left=arith,
        operator=make_lambda_compare("<"),
        right=50,
    )
    ast = to_indexer_ast(cond)
    assert isinstance(ast, UnsupportedOp)


def test_arithmetic_right_returns_unsupportedop():
    arith = ArithmeticExpression(AttributeRef("A", "x"), "+", 10)
    cond = CompoundCondition(
        should_be=True,
        left=AttributeRef("A", "total"),
        operator=make_lambda_compare(">"),
        right=arith,
    )
    ast = to_indexer_ast(cond)
    assert isinstance(ast, UnsupportedOp)


def test_id_ref_equality_produces_compare():
    cond = CompoundCondition(
        should_be=True,
        left=IDRef("A"),
        operator=make_lambda_compare("=="),
        right=5,
    )
    ast = to_indexer_ast(cond)
    assert isinstance(ast, IndexerCompare)
    assert ast._key == IDRef("A")
    assert ast._value == 5


def test_id_ref_inequality_returns_unsupportedop():
    cond = CompoundCondition(
        should_be=True,
        left=IDRef("A"),
        operator=make_lambda_compare(">"),
        right=5,
    )
    ast = to_indexer_ast(cond)
    assert isinstance(ast, UnsupportedOp)


def test_id_ref_right_returns_unsupportedop():
    cond = CompoundCondition(
        should_be=True,
        left=5,
        operator=make_lambda_compare("<"),
        right=IDRef("A"),
    )
    ast = to_indexer_ast(cond)
    assert isinstance(ast, UnsupportedOp)


def test_arithmetic_in_and_unsupported_branch():
    arith = ArithmeticExpression(AttributeRef("A", "x"), "*", AttributeRef("A", "y"))
    left = CompoundCondition(True, arith, make_lambda_compare(">"), 100)
    right = CompoundCondition(True, AttributeRef("B", "score"), make_lambda_compare("<"), 5)

    cond = AND(left, right)
    ast = to_indexer_ast(cond)

    assert isinstance(ast, IndexerAnd)
    assert isinstance(ast._a, UnsupportedOp)
    assert isinstance(ast._b, IndexerCompare)
