"""
GrandCypher is a Cypher interpreter for the Grand graph library.

"""
from typing import Tuple, Dict, List
import networkx as nx

import grandiso

from lark import Lark, Tree, Transformer


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
}


GrandCypherGrammar = Lark(
    """
start               : query

query               : many_match_clause where_clause return_clause
                    | many_match_clause return_clause


many_match_clause   : (match_clause)+


match_clause        : "match"i node_match "-" edge_match "->" node_match


where_clause        : "where"i condition ("and"i condition)*

condition           : entity_id op entity_id_or_value

?entity_id_or_value : entity_id
                    | value

op                  : "==" -> op_eq
                    | "<>" -> op_neq
                    | ">" -> op_gt
                    | "<" -> op_lt
                    | ">="-> op_gte
                    | "<="-> op_lte

value               : STRING | NUMBER


return_clause       : "return"i entity_id ("," entity_id)*
                    | "return"i entity_id ("," entity_id)* limit_clause

limit_clause        : "limit"i NUMBER


?entity_id          : CNAME
                    | CNAME "." CNAME

?node_match         : "(" CNAME ")"
?edge_match         : "[" CNAME "]"
                    | "[]"


%import common.CNAME            -> CNAME
%import common.ESCAPED_STRING   -> STRING
%import common.SIGNED_NUMBER    -> NUMBER

%import common.WS
%ignore WS

""",
    start="start",
)


class GrandCypherTransformer(Transformer):
    def __init__(self, target_graph: nx.Graph):
        self._target_graph = target_graph
        self._conditions = []
        self._motif = nx.DiGraph()
        self._matches = None
        self._return_requests = []
        self._limit = None

    def _lookup(self, data_path):
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
            raise NotImplementedError("Cannot yet return edge data.")

    def return_clause(self, return_clause):
        for item in return_clause:
            if item:
                self._return_requests.append(item)

    def limit_clause(self, limit):
        limit = int(limit[-1])
        # if not isinstance(limit, int):
        #     raise TypeError("Limit must be an integer")
        self._limit = limit

    def returns(self, ignore_limit=False):
        if self._limit and ignore_limit is False:
            return {r: self._lookup(r)[: self._limit] for r in self._return_requests}
        return {r: self._lookup(r) for r in self._return_requests}

    def _get_entity_from_host(self, entity_name, entity_attribute=None):

        if entity_name in self._target_graph.nodes():
            # We are looking for a node mapping in the target graph:
            if entity_attribute:
                # Get the correct entity from the target host graph,
                # and then return the attribute:
                return self._target_graph.nodes[entity_name].get(entity_attribute, None)
            else:
                # Otherwise, just return the node from the host graph
                return entity_name
        else:
            raise NotImplementedError("Cannot yet return edge data.")

    def _OP(self, operator_string, left, right):
        try:
            return operator_string(left, right)
        except:
            # This means that the comparison failed.
            return False

    def _get_true_matches(self):
        # filter the matches based upon the conditions of the where clause:
        # TODO: promote these to inside the monomorphism search
        actual_matches = []
        for match in self._get_structural_matches():
            should_include = True
            for condition in self._conditions:
                (should_be, entity_id, operator, value) = condition
                host_entity_id = entity_id.split(".")
                host_entity_id[0] = match[host_entity_id[0]]
                val = self._OP(
                    operator,
                    self._get_entity_from_host(*host_entity_id),
                    value,
                )
                if val != should_be:
                    should_include = False
            if should_include:
                actual_matches.append(match)
        return actual_matches

    def _get_structural_matches(self):
        if not self._matches:
            self._matches = grandiso.find_motifs(self._motif, self._target_graph)
        return self._matches

    def entity_id(self, entity_id):
        if len(entity_id) == 2:
            return ".".join(entity_id)
        return entity_id.value

    def edge_match(self, edge_name):
        return edge_name

    def node_match(self, node_name):
        return node_name

    def match_clause(self, match_clause: tuple):
        """
        .
        """
        (u, _, v) = match_clause
        self._motif.add_edge(u, v)

    def where_clause(self, where_clause: tuple):
        for clause in where_clause:
            self._conditions.append(clause)

    def condition(self, condition):
        if len(condition) == 3:
            (entity_id, operator, value) = condition
            return (True, entity_id, operator, value)

    def value(self, val):
        (val,) = val
        return eval(val.value)

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


class GrandCypher:
    def __init__(self, host_graph: nx.Graph) -> None:
        self._transformer = GrandCypherTransformer(host_graph)
        self._host_graph = host_graph

    def run(self, cypher: str) -> Dict[str, List]:
        self._transformer.transform(GrandCypherGrammar.parse(cypher))
        return self._transformer.returns()