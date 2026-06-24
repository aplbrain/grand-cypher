from . import (
    ArithmeticExpression,
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
    entity = "A.age"
    value = 10

    ast = to_indexer_ast(cond, entity, value)

    assert isinstance(ast, IndexerCompare)
    assert ast._op == ">"
    assert ast._key == "A.age"
    assert ast._value == 10


# === 2. CompoundCondition unwrapping ==============

def test_compound_condition_unwraps_into_compare():
    inner = LambdaCompareCondition(lambda x,y: True, "<")
    comp = CompoundCondition(
        should_be=True,
        left="B.height",
        operator=inner,
        right=200,
    )

    ast = to_indexer_ast(comp)

    assert isinstance(ast, IndexerCompare)
    assert ast._op == "<"
    assert ast._key == "B.height"
    assert ast._value == 200


# === 3. AND maps to IndexerAnd ====================

def test_and_becomes_indexer_and():
    left = LambdaCompareCondition(lambda x,y: True, ">")
    right = LambdaCompareCondition(lambda x,y: True, "<")

    cond = AND(
        CompoundCondition(True, "A.age", left, 10),
        CompoundCondition(True, "B.score", right, 5),
    )

    ast = to_indexer_ast(cond)

    assert isinstance(ast, IndexerAnd)
    assert isinstance(ast._a, IndexerCompare)
    assert isinstance(ast._b, IndexerCompare)

    assert ast._a._key == "A.age"
    assert ast._b._key == "B.score"


# === 4. OR maps to IndexerOr ======================

def test_or_becomes_indexer_or():
    left = LambdaCompareCondition(lambda x,y: True, ">")
    right = LambdaCompareCondition(lambda x,y: True, "<")

    cond = OR(
        CompoundCondition(True, "A.age", left, 10),
        CompoundCondition(True, "A.age", right, 200),
    )

    ast = to_indexer_ast(cond)

    assert isinstance(ast, IndexerOr)
    assert isinstance(ast._a, IndexerCompare)
    assert isinstance(ast._b, IndexerCompare)


# === 5. Nested AND/OR =============================

def test_nested_ast():
    c1 = CompoundCondition(True, "A.age", make_lambda_compare(">"), 10)
    c2 = CompoundCondition(True, "B.score", make_lambda_compare("<"), 100)
    c3 = CompoundCondition(True, "A.age", make_lambda_compare(">"), 30)

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


# === 8. ArithmeticExpression in left/right → UnsupportedOp ===

def test_arithmetic_left_returns_unsupportedop():
    arith = ArithmeticExpression("A.x", "-", "A.y")
    cond = CompoundCondition(
        should_be=True,
        left=arith,
        operator=make_lambda_compare("<"),
        right=50,
    )

    ast = to_indexer_ast(cond)
    assert isinstance(ast, UnsupportedOp)


def test_arithmetic_value_returns_unsupportedop():
    arith = ArithmeticExpression("A.x", "+", 10)
    cond = CompoundCondition(
        should_be=True,
        left="A.total",
        operator=make_lambda_compare(">"),
        right=arith,
    )

    ast = to_indexer_ast(cond)
    assert isinstance(ast, UnsupportedOp)


def test_arithmetic_in_and_returns_unsupportedop_branch():
    arith = ArithmeticExpression("A.x", "*", "A.y")
    left = CompoundCondition(True, arith, make_lambda_compare(">"), 100)
    right = CompoundCondition(True, "B.score", make_lambda_compare("<"), 5)

    cond = AND(left, right)
    ast = to_indexer_ast(cond)

    assert isinstance(ast, IndexerAnd)
    assert isinstance(ast._a, UnsupportedOp)
    assert isinstance(ast._b, IndexerCompare)


# === 9. IDRef strips to entity_name ===

def test_id_ref_entity_strips_to_entity_name():
    cond = CompoundCondition(
        should_be=True,
        left=IDRef("A"),
        operator=make_lambda_compare(">"),
        right=5,
    )

    ast = to_indexer_ast(cond)
    assert isinstance(ast, IndexerCompare)
    assert ast._key == "A"
    assert ast._value == 5
