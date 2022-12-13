"""
GrandCypher is a Cypher interpreter for the Grand graph library.

You can use this tool to search Python graph data-structures by
data/attribute or by structure, using the same language you'd use
to search in a much larger graph database.

"""
from typing import Dict, List, Callable
import random
import string
import networkx as nx

import grandiso

from lark import Lark, Transformer, v_args, Token


_OPERATORS = {
    "=": lambda x, y: x == y,
    "==": lambda x, y: x == y,
    ">=": lambda x, y: x >= y,
    "<=": lambda x, y: x <= y,
    "<": lambda x, y: x < y,
    ">": lambda x, y: x > y,
    "!=": lambda x, y: x != y,
    "<>": lambda x, y: x != y,
    "in": lambda x, y: x in y,
    "contains": lambda x, y: y in x,
    "is": lambda x, y: x is y,
}


_GrandCypherGrammar = Lark(
    """
start               : query

query               : many_match_clause where_clause return_clause
                    | many_match_clause return_clause


many_match_clause   : (match_clause)+


match_clause        : "match"i node_match (edge_match node_match)*

where_clause        : "where"i compound_condition

compound_condition  : condition
                    | "(" compound_condition boolean_arithmetic compound_condition ")"
                    | compound_condition boolean_arithmetic compound_condition

condition           : entity_id op entity_id_or_value

?entity_id_or_value : entity_id
                    | value
                    | "NULL"i -> null

op                  : "==" -> op_eq
                    | "=" -> op_eq
                    | "<>" -> op_neq
                    | ">" -> op_gt
                    | "<" -> op_lt
                    | ">="-> op_gte
                    | "<="-> op_lte
                    | "is"i -> op_is


return_clause       : "return"i entity_id ("," entity_id)*
                    | "return"i entity_id ("," entity_id)* limit_clause
                    | "return"i entity_id ("," entity_id)* skip_clause
                    | "return"i entity_id ("," entity_id)* skip_clause limit_clause

limit_clause        : "limit"i NUMBER
skip_clause         : "skip"i NUMBER


?entity_id          : CNAME
                    | CNAME "." CNAME

node_match          : "(" (CNAME)? (json_dict)? ")"

edge_match          : LEFT_ANGLE? "--" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" CNAME "]-" RIGHT_ANGLE? 

LEFT_ANGLE          : "<"
RIGHT_ANGLE         : ">"

json_dict           : "{" json_rule ("," json_rule)* "}"
?json_rule          : CNAME ":" value

boolean_arithmetic  : "and"i -> where_and
                    | "OR"i -> where_or

key                 : CNAME
?value              : ESTRING
                    | NUMBER
                    | "NULL"i -> null


%import common.CNAME            -> CNAME
%import common.ESCAPED_STRING   -> ESTRING
%import common.SIGNED_NUMBER    -> NUMBER

%import common.WS
%ignore WS

""",
    start="start",
)

__version__ = "0.2.0"


_ALPHABET = string.ascii_lowercase + string.digits


def shortuuid(k=4) -> str:
    return "".join(random.choices(_ALPHABET, k=k))


def _get_entity_from_host(host: nx.DiGraph, entity_name, entity_attribute=None):
    if entity_name in host.nodes():
        # We are looking for a node mapping in the target graph:
        if entity_attribute:
            # Get the correct entity from the target host graph,
            # and then return the attribute:
            return host.nodes[entity_name].get(entity_attribute, None)
        else:
            # Otherwise, just return the node from the host graph
            return entity_name
    else:
        # looking for an edge:
        edge_data = host.get_edge_data(*entity_name)
        if not edge_data:
            return (
                None  # print(f"Nothing found for {entity_name} {entity_attribute}")
            )
        if entity_attribute:
            # looking for edge attribute:
            return edge_data.get(entity_attribute, None)
        else:
            return host.get_edge_data(*entity_name)


CONDITION = Callable[[dict, nx.DiGraph, list], bool]


def and_(cond_a, cond_b) -> CONDITION:
    def inner(match: dict, host: nx.DiGraph, return_endges: list) -> bool:
        return cond_a(match, host, return_endges) and cond_b(match, host, return_endges)
    return inner

def or_(cond_a, cond_b):
    def inner(match: dict, host: nx.DiGraph, return_endges: list) -> bool:
        return cond_a(match, host, return_endges) or cond_b(match, host, return_endges)
    return inner

def cond_(should_be, entity_id, operator, value) -> CONDITION:
    def inner(match: dict, host: nx.DiGraph, return_endges: list) -> bool:
        host_entity_id = entity_id.split(".")
        if host_entity_id[0] in match:
            host_entity_id[0] = match[host_entity_id[0]]
        elif host_entity_id[0] in return_endges:
            # looking for edge...
            edge_mapping = return_endges[host_entity_id[0]]
            host_entity_id[0] = (match[edge_mapping[0]], match[edge_mapping[1]])
        else:
            raise IndexError(f"Entity {host_entity_id} not in graph.")
        try:
            val = operator(_get_entity_from_host(host, *host_entity_id), value)
        except:
            val = False
        if val != should_be:
            return False
        return True
    return inner


_BOOL_ARI = {
    "and": and_,
    "or": or_,
}


class _GrandCypherTransformer(Transformer):
    def __init__(self, target_graph: nx.Graph):
        self._target_graph = target_graph
        self._conditions: List[CONDITION] = []
        self._where_condition: CONDITION = None
        self._motif = nx.DiGraph()
        self._matches = None
        self._return_requests = []
        self._return_edges = {}
        self._limit = None
        self._skip = 0

    def _lookup(self, data_path):
        if not isinstance(data_path, str):
            data_path = data_path.value
        if "." in data_path:
            entity_name, entity_attribute = data_path.split(".")
        else:
            entity_name = data_path
            entity_attribute = None

        if entity_name in self._motif.nodes():
            # We are looking for a node mapping in the target graph:
            if entity_attribute:
                # Get the correct entity from the target host graph,
                # and then return the attribute:
                return [
                    self._target_graph.nodes[mapping[entity_name]].get(
                        entity_attribute, None
                    )
                    for mapping in self._get_true_matches()
                ]
            else:
                # Otherwise, just return the node from the host graph
                return [mapping[entity_name] for mapping in self._get_true_matches()]
        else:
            if data_path in self._return_edges:
                mapping_u, mapping_v = self._return_edges[data_path]
                # We are looking for an edge mapping in the target graph:
                if entity_attribute:
                    # Get the correct entity from the target host graph,
                    # and then return the attribute:
                    return [
                        self._target_graph.get_edge_data(
                            mapping[mapping_u], mapping[mapping_v]
                        ).get(entity_attribute, None)
                        for mapping in self._get_true_matches()
                    ]
                else:
                    # Otherwise, just return the node from the host graph
                    return [
                        self._target_graph.get_edge_data(
                            mapping[mapping_u], mapping[mapping_v]
                        )
                        for mapping in self._get_true_matches()
                    ]

            raise NotImplementedError(f"Unknown entity name: {data_path}")

    def return_clause(self, clause):
        for item in clause:
            if item:
                if not isinstance(item, str):
                    item = str(item.value)
                self._return_requests.append(item)

    def limit_clause(self, limit):
        limit = int(limit[-1])
        self._limit = limit

    def skip_clause(self, skip):
        skip = int(skip[-1])
        self._skip = skip

    def returns(self, ignore_limit=False):
        if self._limit and ignore_limit is False:
            return {
                r: self._lookup(r)[self._skip : self._skip + self._limit]
                for r in self._return_requests
            }
        return {r: self._lookup(r)[self._skip :] for r in self._return_requests}

    def _get_true_matches(self):
        # filter the matches based upon the conditions of the where clause:
        # TODO: promote these to inside the monomorphism search
        actual_matches = []
        for match in self._get_structural_matches():
            for condition in self._conditions:
                if not condition(match, self._target_graph, self._return_edges):
                    break
            else:
                if (not self._where_condition or
                    self._where_condition(match, self._target_graph, self._return_edges)):
                    actual_matches.append(match)
        return actual_matches

    def _get_structural_matches(self):
        if not self._matches:
            matches = []
            for motif in (
                self._motif.subgraph(c)
                for c in nx.weakly_connected_components(self._motif)
            ):
                _matches = grandiso.find_motifs(
                    motif,
                    self._target_graph,
                    limit=(self._limit + self._skip + 1)
                    if (self._skip and self._limit)
                    else None,
                )
                if not matches:
                    matches = _matches
                elif _matches:
                    matches = [{**a, **b} for a in matches for b in _matches]
            self._matches = matches
        return self._matches

    def entity_id(self, entity_id):
        if len(entity_id) == 2:
            return ".".join(entity_id)
        return entity_id.value

    def edge_match(self, edge_name):
        if len(edge_name) == 0:  # --
            res = ("", "b")
        elif len(edge_name) == 1:  # <--, -->, -CNAME-
            edge_name = edge_name[0].value
            if edge_name == "<":
                res = ("", "l")
            elif edge_name == ">":
                res = ("", "r")
            else:
                res = (edge_name, "b")
        elif len(edge_name) == 2:  # <-->, <-CNAME-, -CNAME->
            edge_name = (edge_name[0].value, edge_name[1].value)
            if edge_name == ("<", ">"):
                res = ("", "b")
            elif edge_name[0] == "<":
                res = (edge_name[1], "l")
            else:
                res = (edge_name[0], "r")
        else:  # <-CNAME->
            res = (edge_name[1].value, "b")

        return (Token("CNAME", res[0]), res[1])


    def node_match(self, node_name):
        if not node_name:
            node_name = [Token("CNAME", shortuuid()), {}]
        elif len(node_name) == 1 and not isinstance(node_name[0], Token):
            node_name = [Token("CNAME", shortuuid()), node_name[0]]
        elif len(node_name) == 1:
            node_name = [node_name[0], {}]
        node_name, constraints = node_name
        for key, val in constraints.items():
            cond = cond_(True, f"{node_name}.{key}", _OPERATORS["=="], val)
            self._conditions.append(cond)
        return node_name

    def match_clause(self, match_clause: tuple):
        if len(match_clause) == 1:
            # This is just a node match:
            self._motif.add_node(match_clause[0].value)
            return
        for start in range(0, len(match_clause) - 2, 2):
            (u, (g, d), v) = match_clause[start : start + 3]
            if d == "r":
                edges = ((u.value, v.value),)
            elif d == "l":
                edges = ((v.value, u.value),)
            elif d == "b":
                edges = ((u.value, v.value), (v.value, u.value))
            else:
                raise ValueError(f"Not support direction d={d!r}")

            if g:
                self._return_edges[g.value] = edges[0]
            self._motif.add_edges_from(edges)

    def where_clause(self, where_clause: tuple):
        self._where_condition = where_clause[0]
    
    def compound_condition(self, val):
        if len(val) == 1:
            val = cond_(*val[0])
        else:  # len == 3
            compound_a, operator, compound_b = val
            val = operator(compound_a, compound_b)
        return val

    def where_and(self, val):
        return _BOOL_ARI["and"]

    
    def where_or(self, val):
        return _BOOL_ARI["or"]

    def condition(self, condition):
        if len(condition) == 3:
            (entity_id, operator, value) = condition
            return (True, entity_id, operator, value)

    null = lambda self, _: None
    ESTRING = v_args(inline=True)(eval)
    NUMBER = v_args(inline=True)(eval)

    def op(self, operator):
        return operator

    def op_eq(self, _):
        return _OPERATORS["=="]

    def op_neq(self, _):
        return _OPERATORS["<>"]

    def op_gt(self, _):
        return _OPERATORS[">"]

    def op_lt(self, _):
        return _OPERATORS["<"]

    def op_gte(self, _):
        return _OPERATORS[">="]

    def op_lte(self, _):
        return _OPERATORS["<="]

    def op_is(self, _):
        return _OPERATORS["is"]

    def json_dict(self, tup):
        constraints = {}
        for key, value in tup:
            constraints[key] = value
        return constraints

    def json_rule(self, rule):
        return (rule[0].value, rule[1])


class GrandCypher:
    """
    The user-facing interface for GrandCypher.

    Create a GrandCypher object in order to wrap your NetworkX-flavored graph
    with a Cypher-queryable interface.

    """

    def __init__(self, host_graph: nx.Graph) -> None:

        """
        Create a new GrandCypher object to query graphs with Cypher.

        Arguments:
            host_graph (nx.Graph): The host graph to use as a "graph database"

        Returns:
            None

        """

        self._transformer = _GrandCypherTransformer(host_graph)
        self._host_graph = host_graph

    def run(self, cypher: str) -> Dict[str, List]:
        """
        Run a cypher query on the host graph.

        Arguments:
            cypher (str): The cypher query to run

        Returns:
            Dict[str, List]: A dictionary mapping of results, where keys are
                the items the user requested in the RETURN statement, and the
                values are all possible matches of that structure in the graph.

        """
        self._transformer.transform(_GrandCypherGrammar.parse(cypher))
        return self._transformer.returns()
