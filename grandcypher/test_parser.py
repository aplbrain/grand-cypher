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
