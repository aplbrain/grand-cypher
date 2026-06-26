from lark import Token, Tree

from . import _GrandCypherGrammar


class TestParsing:
    def test_simple_match_query(self):
        tree = _GrandCypherGrammar.parse(
            """
        MATCH (A)-[B]->(C)
        WHERE A > A
        RETURN A
        """
        )
        assert len(tree.children[0].children) == 3

    def test_keywords_case_insensitive(self):
        tree = _GrandCypherGrammar.parse(
            """
        mAtCh (A)-[B]->(C)
        WHERe A > A
        return A
        """
        )
        assert len(tree.children[0].children) == 3


class TestArithmeticParsing:
    def test_parse_subtraction(self):
        tree = _GrandCypherGrammar.parse(
            """
        MATCH (A)-[B]->(C)
        WHERE A.x - A.y < 50
        RETURN A
        """
        )
        where = tree.children[0].children[1]
        condition = where.children[0].children[0]
        assert condition.children[0].data == "arith_sub"
        assert condition.children[1].data == "op_lt"
        assert condition.children[2] == Token("NUMBER", "50")

    def test_parse_addition(self):
        tree = _GrandCypherGrammar.parse(
            """
        MATCH (A)
        WHERE A.x + 10 > 20
        RETURN A
        """
        )
        where = tree.children[0].children[1]
        condition = where.children[0].children[0]
        assert condition.children[0].data == "arith_add"
        assert condition.children[1].data == "op_gt"
        assert condition.children[2] == Token("NUMBER", "20")

    def test_parse_multiplication(self):
        tree = _GrandCypherGrammar.parse(
            """
        MATCH (A)
        WHERE A.price * A.qty > 100
        RETURN A
        """
        )
        where = tree.children[0].children[1]
        condition = where.children[0].children[0]
        assert condition.children[0].data == "arith_mul"
        assert condition.children[1].data == "op_gt"
        assert condition.children[2] == Token("NUMBER", "100")

    def test_parse_division(self):
        tree = _GrandCypherGrammar.parse(
            """
        MATCH (A)
        WHERE A.total / A.count >= 5
        RETURN A
        """
        )
        where = tree.children[0].children[1]
        condition = where.children[0].children[0]
        assert condition.children[0].data == "arith_div"
        assert condition.children[1].data == "op_gte"
        assert condition.children[2] == Token("NUMBER", "5")

    def test_parse_modulo(self):
        tree = _GrandCypherGrammar.parse(
            """
        MATCH (A)
        WHERE A.value % 2 == 0
        RETURN A
        """
        )
        where = tree.children[0].children[1]
        condition = where.children[0].children[0]
        assert condition.children[0].data == "arith_mod"
        assert condition.children[1].data == "op_eq"
        assert condition.children[2] == Token("NUMBER", "0")

    def test_parse_parenthesized(self):
        tree = _GrandCypherGrammar.parse(
            """
        MATCH (A)
        WHERE (A.x + A.y) * 2 < 100
        RETURN A
        """
        )
        where = tree.children[0].children[1]
        condition = where.children[0].children[0]
        lhs = condition.children[0]
        assert lhs.data == "arith_mul"
        assert lhs.children[0].data == "arith_add"
        assert condition.children[1].data == "op_lt"
        assert condition.children[2] == Token("NUMBER", "100")

    def test_parse_arithmetic_preserves_precedence(self):
        tree = _GrandCypherGrammar.parse(
            """
        MATCH (A)
        WHERE A.x + A.y * 2 < 100
        RETURN A
        """
        )
        where = tree.children[0].children[1]
        compound = where.children[0]
        condition = compound.children[0]
        lhs = condition.children[0]
        assert isinstance(lhs, Tree)
        assert lhs.data == "arith_add"
        assert lhs.children[1].data == "arith_mul"

    def test_parse_arithmetic_both_sides(self):
        tree = _GrandCypherGrammar.parse(
            """
        MATCH (A)
        WHERE A.x - 1 > A.y + 1
        RETURN A
        """
        )
        where = tree.children[0].children[1]
        condition = where.children[0].children[0]
        assert condition.children[0].data == "arith_sub"
        assert condition.children[1].data == "op_gt"
        assert condition.children[2].data == "arith_add"

    def test_parse_chained_arithmetic(self):
        tree = _GrandCypherGrammar.parse(
            """
        MATCH (A)
        WHERE A.x + A.y - A.z > 0
        RETURN A
        """
        )
        where = tree.children[0].children[1]
        compound = where.children[0]
        condition = compound.children[0]
        lhs = condition.children[0]
        assert isinstance(lhs, Tree)
        assert lhs.data == "arith_sub"
        assert lhs.children[0].data == "arith_add"

    def test_parse_nested_parenthesized(self):
        tree = _GrandCypherGrammar.parse(
            """
        MATCH (A)
        WHERE ((A.x + 1) * 2) - 3 > 10
        RETURN A
        """
        )
        where = tree.children[0].children[1]
        condition = where.children[0].children[0]
        lhs = condition.children[0]
        assert lhs.data == "arith_sub"
        assert lhs.children[0].data == "arith_mul"
        assert lhs.children[0].children[0].data == "arith_add"
        assert condition.children[1].data == "op_gt"
        assert condition.children[2] == Token("NUMBER", "10")
