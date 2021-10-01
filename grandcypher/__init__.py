"""
GrandCypher is a Cypher interpreter for the Grand graph library.

You can use this tool to search Python graph data-structures by
data/attribute or by structure, using the same language you'd use
to search in a much larger graph database.

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


_GrandCypherGrammar = Lark(
    """
start               : query

query               : many_match_clause where_clause return_clause
                    | many_match_clause return_clause


many_match_clause   : (match_clause)+


match_clause        : "match"i node_match "-" edge_match "->" node_match
                    | "match"i node_match


where_clause        : "where"i condition ("and"i condition)*

condition           : entity_id op entity_id_or_value

?entity_id_or_value : entity_id
                    | value

op                  : "==" -> op_eq
                    | "=" -> op_eq
                    | "<>" -> op_neq
                    | ">" -> op_gt
                    | "<" -> op_lt
                    | ">="-> op_gte
                    | "<="-> op_lte


return_clause       : "return"i entity_id ("," entity_id)*
                    | "return"i entity_id ("," entity_id)* limit_clause
                    | "return"i entity_id ("," entity_id)* skip_clause
                    | "return"i entity_id ("," entity_id)* skip_clause limit_clause

limit_clause        : "limit"i NUMBER
skip_clause         : "skip"i NUMBER


?entity_id          : CNAME
                    | CNAME "." CNAME

?node_match         : "(" CNAME ")"
                    | "(" CNAME json_dict ")"

?edge_match         : "[" CNAME "]"
                    | "[]"

json_dict           : "{" json_rule ("," json_rule)* "}"
?json_rule          : CNAME ":" value


key                 : CNAME
value               : ESTRING | NUMBER


%import common.CNAME            -> CNAME
%import common.ESCAPED_STRING   -> ESTRING
%import common.SIGNED_NUMBER    -> NUMBER

%import common.WS
%ignore WS

""",
    start="start",
)

__version__ = "0.1.1"

class _GrandCypherTransformer(Transformer):
    def __init__(self, target_graph: nx.Graph):
        self._target_graph = target_graph
        self._conditions = []
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
            # looking for an edge:
            edge_data = self._target_graph.get_edge_data(*entity_name)
            if not edge_data:
                return (
                    None  # print(f"Nothing found for {entity_name} {entity_attribute}")
                )
            if entity_attribute:
                # looking for edge attribute:
                return edge_data.get(entity_attribute, None)
            else:
                return self._target_graph.get_edge_data(*entity_name)

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
                if host_entity_id[0] in match:
                    host_entity_id[0] = match[host_entity_id[0]]
                elif host_entity_id[0] in self._return_edges:
                    # looking for edge...
                    edge_mapping = self._return_edges[host_entity_id[0]]
                    host_entity_id[0] = (match[edge_mapping[0]], match[edge_mapping[1]])
                else:
                    raise IndexError(f"Entity {host_entity_id} not in graph.")
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
        if isinstance(node_name, list):
            node_name, constraints = node_name
        else:
            constraints = {}
        for key, val in constraints.items():
            self._conditions.append(
                (True, f"{node_name}.{key}", _OPERATORS["=="], val)
            )
        return node_name

    def match_clause(self, match_clause: tuple):
        if len(match_clause) == 1:
            # This is just a node match:
            self._motif.add_node(match_clause[0].value)
            return
        (u, g, v) = match_clause
        if g:
            self._return_edges[g.value] = (u.value, v.value)
        self._motif.add_edge(u.value, v.value)

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
