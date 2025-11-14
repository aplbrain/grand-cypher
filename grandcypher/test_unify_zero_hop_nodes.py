import networkx as nx
from . import unify_zero_hop_nodes

def add_zero_hop_edge(g, u, v):
    # g.add_edge(u, v, __min_hop__=0, __max_hop__=0, __labels__=["x"])
    g.add_node(u)
    g.add_node(v)


def add_normal_edge(g, u, v):
    g.add_edge(u, v, __min_hop__=1, __max_hop__=1, __labels__=["y"])
    g.add_node(u)
    g.add_node(v)


def test_single_zero_hop_new():
    """
    Single zero-hop edge: U1 -> U2
    """
    g = nx.DiGraph()
    add_zero_hop_edge(g, "U1", "U2")
    paths = {("U1","U2"): ("U1","U1")}

    new_g = unify_zero_hop_nodes(g, paths)
    assert set(new_g.nodes) == {"U1"}
    assert list(new_g.edges) == []


def test_chain_zero_hop_new():
    """
    Chain of zero-hop edges: A -> B -> C
    """
    g = nx.DiGraph()
    add_zero_hop_edge(g, "A", "B")
    add_zero_hop_edge(g, "B", "C")
    paths = {
        ("A","B"): ("A","A"),
        ("B","C"): ("B","B")
    }

    new_g = unify_zero_hop_nodes(g, paths)
    assert set(new_g.nodes) == {"A"}
    assert list(new_g.edges) == []


def test_branching_zero_hop_new():
    """
    Branching zero-hop edges: A -> B, A -> C
    """
    g = nx.DiGraph()
    add_zero_hop_edge(g, "A", "B")
    add_zero_hop_edge(g, "A", "C")
    paths = {
        ("A","B"): ("A","A"),
        ("A","C"): ("A","A")
    }

    new_g = unify_zero_hop_nodes(g, paths)
    assert set(new_g.nodes) == {"A"}
    assert list(new_g.edges) == []


def test_zero_hop_plus_normal_edge_new():
    """
    Mix zero-hop and normal edge: A -[*0]-> B, B -[*1]-> C
    """
    g = nx.DiGraph()
    add_zero_hop_edge(g, "A", "B")
    add_normal_edge(g, "B", "C")
    paths = {
        ("A","B"): ("A","A")
    }

    new_g = unify_zero_hop_nodes(g, paths)
    assert set(new_g.nodes) == {"A", "C"}
    edges = list(new_g.edges(data=True))
    assert len(edges) == 1
    u, v, data = edges[0]
    assert u == "A" and v == "C"
    assert data["__min_hop__"] == 1


def test_multiple_zero_hop_edges_same_direction_new():
    """
    Multiple zero-hop edges in the same direction: A -> B twice
    """
    g = nx.DiGraph()
    add_zero_hop_edge(g, "A", "B")
    add_zero_hop_edge(g, "A", "B")
    paths = {
        ("A","B"): ("A","A")
    }

    new_g = unify_zero_hop_nodes(g, paths)
    assert set(new_g.nodes) == {"A"}
    assert list(new_g.edges) == []


def test_multiple_independent_chains():
    """
    Multiple zero-hop chains: a->b->c and x->y
    """
    g = nx.DiGraph()
    add_zero_hop_edge(g, "a","b")
    add_zero_hop_edge(g, "b","c")
    add_zero_hop_edge(g, "x","y")
    paths = {
        ("a","b"): ("a","a"),
        ("b","c"): ("b","b"),
        ("x","y"): ("x","x")
    }

    new_g = unify_zero_hop_nodes(g, paths)
    assert set(new_g.nodes) == {"a", "x"}
