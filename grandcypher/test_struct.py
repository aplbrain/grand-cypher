from .struct import UnionFind


def test_single_find():
    uf = UnionFind()
    assert uf.find("a") == "a"
    assert uf.parent["a"] == "a"


def test_simple_union():
    uf = UnionFind()
    uf.union("a", "b")
    # Both should have the same root
    root_a = uf.find("a")
    root_b = uf.find("b")
    assert root_a == root_b
    # Union is idempotent
    uf.union("a", "b")
    assert uf.find("a") == uf.find("b")


def test_chain_union():
    uf = UnionFind()
    uf.union("a", "b")
    uf.union("b", "c")
    # All should have the same root
    root = uf.find("a")
    assert uf.find("b") == root
    assert uf.find("c") == root


def test_multiple_disjoint_unions():
    uf = UnionFind()
    uf.union("a", "b")
    uf.union("c", "d")
    # Roots of different sets should be different
    root1 = uf.find("a")
    root2 = uf.find("c")
    assert root1 != root2
    # Union separate sets
    uf.union("b", "c")
    # Now all should have same root
    final_root = uf.find("a")
    for x in ["a","b","c","d"]:
        assert uf.find(x) == final_root


def test_find_creates_node():
    uf = UnionFind()
    # Finding a node not in parent creates it
    assert uf.find("x") == "x"
    assert "x" in uf.parent


def test_idempotent_union_chain():
    uf = UnionFind()
    uf.union("a", "b")
    uf.union("b", "c")
    first_root = uf.find("a")
    uf.union("a", "c")
    # Should still have same root
    assert uf.find("b") == first_root
    assert uf.find("c") == first_root
