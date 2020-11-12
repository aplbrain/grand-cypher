"""
GrandCypher is a Cypher interpreter for the Grand graph library.

"""
from typing import Tuple, Dict, List
import networkx as nx

import grandiso

from lark import Lark, Tree, Transformer


GrandCypherGrammar = Lark(
    """
start               : query

query               : many_match_clause where_clause return_clause
                    | many_match_clause return_clause


many_match_clause   : (match_clause)+


match_clause        : "match"i node_match "-" edge_match "->" node_match


where_clause        : "where"i condition ("and"i condition)*

condition           : entity_id operator entity_id_or_value

entity_id_or_value  : entity_id
                    | value

?operator           : "=="
                    | ">"
                    | "<>"
                    | "<"
                    | ">="
                    | "<="
                    | "in"i
                    | "contains"i

value               : STRING | NUMBER


return_clause       : "return"i entity_id ("," entity_id)*


?entity_id          : CNAME
                    | CNAME "." CNAME

?node_match         : "(" CNAME ")"
?edge_match         : "[" CNAME "]"


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
        self._node_constraints = []
        self._motif = nx.DiGraph()
        self._matches = None
        self._return_requests = []

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
                    for mapping in self._get_matches()
                ]
            else:
                # Otherwise, just return the node from the host graph
                return [mapping[entity_name] for mapping in self._get_matches()]
        else:
            raise NotImplementedError("Cannot yet return edge data.")

    def return_clause(self, return_clause):
        for item in return_clause:
            if isinstance(item, Tree):
                # This is an entity ID of the form `NAME.ATTRIBUTE`
                item = ".".join(item.children)
                self._return_requests.append(item)
            elif len(item) == 1:
                # This is an entity ID of the form `NAME`
                (item,) = item
                self._return_requests.append(item)

    def returns(self):
        return {r: self._lookup(r) for r in self._return_requests}

    def _get_matches(self):
        if not self._matches:
            self._matches = grandiso.find_motifs(self._motif, self._target_graph)
        return self._matches

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


class GrandCypher:
    def __init__(self, host_graph: nx.Graph) -> None:
        self._transformer = GrandCypherTransformer(host_graph)
        self._host_graph = host_graph

    def run(self, cypher: str) -> Dict[str, List]:
        self._transformer.transform(GrandCypherGrammar.parse(cypher))
        return self._transformer.returns()