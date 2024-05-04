"""
GrandCypher is a Cypher interpreter for the Grand graph library.

You can use this tool to search Python graph data-structures by
data/attribute or by structure, using the same language you'd use
to search in a much larger graph database.

"""

from typing import Dict, List, Callable, Tuple
from collections import OrderedDict
import random
import string
from functools import lru_cache
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
    "starts_with": lambda x, y: x.startswith(y),
    "ends_with": lambda x, y: x.endswith(y),
}


_GrandCypherGrammar = Lark(
    r"""
start               : query

query               : many_match_clause where_clause return_clause order_clause? skip_clause? limit_clause?
                    | many_match_clause return_clause order_clause? skip_clause? limit_clause?


many_match_clause   : (match_clause)+


match_clause        : "match"i path_clause? node_match (edge_match node_match)*

path_clause         : CNAME EQUAL

where_clause        : "where"i compound_condition

compound_condition  : condition
                    | "(" compound_condition boolean_arithmetic compound_condition ")"
                    | compound_condition boolean_arithmetic compound_condition

condition           : entity_id op entity_id_or_value
                    | "not"i condition -> condition_not

?entity_id_or_value : entity_id
                    | value
                    | "NULL"i -> null
                    | "TRUE"i -> true
                    | "FALSE"i -> false

op                  : "==" -> op_eq
                    | "=" -> op_eq
                    | "<>" -> op_neq
                    | ">" -> op_gt
                    | "<" -> op_lt
                    | ">="-> op_gte
                    | "<="-> op_lte
                    | "is"i -> op_is
                    | "in"i -> op_in
                    | "contains"i -> op_contains
                    | "starts with"i -> op_starts_with
                    | "ends with"i -> op_ends_with



return_clause       : "return"i distinct_return? entity_id ("," entity_id)*

distinct_return     : "DISTINCT"i
limit_clause        : "limit"i NUMBER
skip_clause         : "skip"i NUMBER

order_clause        : "order"i "by"i order_items

order_items         : order_item ("," order_item)*

order_item          : entity_id order_direction?

order_direction     : "ASC"i -> asc
                    | "DESC"i -> desc
                    | -> no_direction


?entity_id          : CNAME
                    | CNAME "." CNAME

node_match          : "(" (CNAME)? (json_dict)? ")"
                    | "(" (CNAME)? ":" TYPE (json_dict)? ")"

edge_match          : LEFT_ANGLE? "--" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" CNAME "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" CNAME ":" TYPE "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" ":" TYPE "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" "*" MIN_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" "*" MIN_HOP  ".." MAX_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" CNAME "*" MIN_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" CNAME "*" MIN_HOP  ".." MAX_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" ":" TYPE "*" MIN_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" ":" TYPE "*" MIN_HOP  ".." MAX_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" CNAME ":" TYPE "*" MIN_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" CNAME ":" TYPE "*" MIN_HOP  ".." MAX_HOP "]-" RIGHT_ANGLE?



LEFT_ANGLE          : "<"
RIGHT_ANGLE         : ">"
EQUAL               : "="
MIN_HOP             : INT
MAX_HOP             : INT
TYPE                : CNAME

json_dict           : "{" json_rule ("," json_rule)* "}"
?json_rule          : CNAME ":" value

boolean_arithmetic  : "and"i -> where_and
                    | "OR"i -> where_or

key                 : CNAME
?value              : ESTRING
                    | NUMBER
                    | "NULL"i -> null
                    | "TRUE"i -> true
                    | "FALSE"i -> false


%import common.CNAME            -> CNAME
%import common.ESCAPED_STRING   -> ESTRING
%import common.SIGNED_NUMBER    -> NUMBER
%import common.INT              -> INT

%import common.WS
%ignore WS
COMMENT: "//" /[^\n]/*
%ignore COMMENT

""",
    start="start",
)

__version__ = "0.7.0"


_ALPHABET = string.ascii_lowercase + string.digits


def shortuuid(k=4) -> str:
    return "".join(random.choices(_ALPHABET, k=k))


@lru_cache()
def _is_node_attr_match(
    motif_node_id: str, host_node_id: str, motif: nx.Graph, host: nx.Graph
) -> bool:
    """
    Check if a node in the host graph matches the attributes in the motif.

    Arguments:
        motif_node_id (str): The motif node ID
        host_node_id (str): The host graph ID
        motif (nx.Graph): The motif graph
        host (nx.Graph): The host graph

    Returns:
        bool: True if the host node matches the attributes in the motif

    """
    motif_node = motif.nodes[motif_node_id]
    host_node = host.nodes[host_node_id]

    for attr, val in motif_node.items():
        if attr == "__labels__":
            if val and val - host_node.get("__labels__", set()):
                return False
            continue
        if host_node.get(attr) != val:
            return False

    return True


@lru_cache()
def _is_edge_attr_match(
    motif_edge_id: Tuple[str, str],
    host_edge_id: Tuple[str, str],
    motif: nx.Graph,
    host: nx.Graph,
) -> bool:
    """
    Check if an edge in the host graph matches the attributes in the motif.
    This also check the __labels__ of edges.

    Arguments:
        motif_edge_id (str): The motif edge ID
        host_edge_id (str): The host edge ID
        motif (nx.Graph): The motif graph
        host (nx.Graph): The host graph

    Returns:
        bool: True if the host edge matches the attributes in the motif

    """
    motif_edge = motif.edges[motif_edge_id]
    host_edge = host.edges[host_edge_id]

    for attr, val in motif_edge.items():
        if attr == "__labels__":
            if val and val - host_edge.get("__labels__", set()):
                return False
            continue
        if host_edge.get(attr) != val:
            return False

    return True


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
            return None  # print(f"Nothing found for {entity_name} {entity_attribute}")
        if entity_attribute:
            # looking for edge attribute:
            return edge_data.get(entity_attribute, None)
        else:
            return host.get_edge_data(*entity_name)


def _get_edge(host: nx.DiGraph, mapping, match_path, u, v):
    edge_path = match_path[(u, v)]
    return [
        host.get_edge_data(mapping[u], mapping[v])
        for u, v in zip(edge_path[:-1], edge_path[1:])
    ]


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


def _data_path_to_entity_name_attribute(data_path):
    if not isinstance(data_path, str):
        data_path = data_path.value
    if "." in data_path:
        entity_name, entity_attribute = data_path.split(".")
    else:
        entity_name = data_path
        entity_attribute = None

    return entity_name, entity_attribute


class _GrandCypherTransformer(Transformer):
    def __init__(self, target_graph: nx.Graph, limit=None):
        self._target_graph = target_graph
        self._paths = []
        self._where_condition: CONDITION = None
        self._motif = nx.DiGraph()
        self._matches = None
        self._matche_paths = None
        self._return_requests = []
        self._return_edges = {}
        self._distinct = False
        self._order_by = None
        self._order_by_attributes = set()
        self._limit = limit
        self._skip = 0
        self._max_hop = 100

    def _lookup(self, data_paths: List[str], offset_limit) -> Dict[str, List]:
        if not data_paths:
            return {}

        motif_nodes = self._motif.nodes()

        for data_path in data_paths:
            entity_name, _ = _data_path_to_entity_name_attribute(data_path)
            if entity_name not in motif_nodes and entity_name not in self._return_edges and entity_name not in self._paths:
                raise NotImplementedError(f"Unknown entity name: {data_path}")

        result = {}
        true_matches = self._get_true_matches()

        for data_path in data_paths:
            entity_name, entity_attribute = _data_path_to_entity_name_attribute(
                data_path
            )

            if entity_name in motif_nodes:
                # We are looking for a node mapping in the target graph:

                ret = (mapping[entity_name] for mapping, _ in true_matches)
                # by default, just return the node from the host graph

                if entity_attribute:
                    # Get the correct entity from the target host graph,
                    # and then return the attribute:
                    ret = (
                        self._target_graph.nodes[node].get(entity_attribute, None)
                        for node in ret
                    )

            elif entity_name in self._paths:
                ret = []
                for mapping, _ in true_matches:
                    path, nodes = [], list(mapping.values())
                    for x, node in enumerate(nodes):
                        # Edge
                        if x > 0:
                            path.append(self._target_graph.get_edge_data(nodes[x - 1], node))

                        # Node
                        path.append(node)

                    ret.append(path)

            else:
                mapping_u, mapping_v = self._return_edges[data_path]
                # We are looking for an edge mapping in the target graph:
                is_hop = self._motif.edges[(mapping_u, mapping_v)]["__is_hop__"]
                ret = (
                    _get_edge(
                        self._target_graph, mapping, match_path, mapping_u, mapping_v
                    )
                    for mapping, match_path in true_matches
                )
                ret = (r[0] if is_hop else r for r in ret)
                # we keep the original list if len > 2 (edge hop 2+)

                if entity_attribute:
                    # Get the correct entity from the target host graph,
                    # and then return the attribute:
                    ret = (r.get(entity_attribute, None) for r in ret)

            result[data_path] = list(ret)[offset_limit]

        return result
    
    def return_clause(self, clause):        
        # collect all entity identifiers to be returned
        for item in clause:
            if item:
                if not isinstance(item, str):
                    item = str(item.value)
                self._return_requests.append(item)


    def order_clause(self, order_clause):
        self._order_by = []
        for item in order_clause[0].children:
            field = str(item.children[0])  # assuming the field name is the first child
            # Default to 'ASC' if not specified
            if len(item.children) > 1 and str(item.children[1].data).lower() != 'desc':
                direction = 'ASC'
            else:
                direction = 'DESC'
            
            self._order_by.append((field, direction))   # [('n.age', 'DESC'), ...]
            self._order_by_attributes.add(field)

    def distinct_return(self, distinct):
        self._distinct = True

    def limit_clause(self, limit):
        limit = int(limit[-1])
        self._limit = limit

    def skip_clause(self, skip):
        skip = int(skip[-1])
        self._skip = skip

    def returns(self, ignore_limit=False):

        results = self._lookup(
            self._return_requests + list(self._order_by_attributes), 
            offset_limit=slice(0, None)
        )
        if self._order_by:
            results = self._apply_order_by(results)
        if self._distinct:
            results = self._apply_distinct(results)
        results = self._apply_pagination(results, ignore_limit)


        # Exclude order-by-only attributes from the final results
        results = {
            key: values for key, values in results.items() if key in self._return_requests
        }

        return results
    
    def _apply_order_by(self, results):
        if self._order_by:
            sort_lists = [(results[field], direction) for field, direction in self._order_by if field in results]

            if sort_lists:
                # Generate a list of indices sorted by the specified fields
                indices = range(len(next(iter(results.values()))))  # Safe because all lists are assumed to be of the same length
                for sort_list, direction in reversed(sort_lists):  # reverse to ensure the first sort key is primary
                    indices = sorted(indices, key=lambda i: sort_list[i], reverse=(direction == 'DESC'))

                # Reorder all lists in results using sorted indices
                for key in results:
                    results[key] = [results[key][i] for i in indices]
        
        return results
    
    def _apply_distinct(self, results):
        if self._order_by:
            assert self._order_by_attributes.issubset(self._return_requests), "In a WITH/RETURN with DISTINCT or an aggregation, it is not possible to access variables declared before the WITH/RETURN"

        # ordered dict to maintain the first occurrence of each unique tuple based on return requests
        unique_rows = OrderedDict()
        
        # Iterate over each 'row' by index
        for i in range(len(next(iter(results.values())))):  # assume all columns are of the same length
            # create a tuple key of all the values from return requests for this row
            row_key = tuple(results[key][i] for key in self._return_requests if key in results)
            
            if row_key not in unique_rows:
                unique_rows[row_key] = i  # store the index of the first occurrence of this unique row
        
        # construct the results based on unique indices collected
        distinct_results = {key: [] for key in self._return_requests}
        for row_key, index in unique_rows.items():
            for _, key in enumerate(self._return_requests):
                distinct_results[key].append(results[key][index])
        
        return distinct_results
    
    def _apply_pagination(self, results, ignore_limit):
        # apply LIMIT and SKIP (if set) after ordering
        if self._limit is not None and not ignore_limit:
            start_index = self._skip
            end_index = start_index + self._limit
            for key in results.keys():
                results[key] = results[key][start_index:end_index]
        # else just apply SKIP (if set)
        else:
            for key in results.keys():
                start_index = self._skip
                results[key] = results[key][start_index:]
        
        return results

    def _get_true_matches(self):
        if not self._matches:
            self_matches = []
            self_matche_paths = []
            complete = False

            for my_motif, edge_hop_map in self._edge_hop_motifs(self._motif):
                # Iteration is complete
                if complete:
                    break

                zero_hop_edges = [
                    k for k, v in edge_hop_map.items() if len(v) == 2 and v[0] == v[1]
                ]

                # Iterate over generated matches
                for match in self._matches_iter(my_motif):
                    # matches can contains zero hop edges from A to B
                    # there are 2 cases to take care
                    # (1) there are both A and B in the match. This case is the result of query A -[*0]-> B --> C.
                    #   If A != B break else continue to (2)
                    # (2) there is only A in the match. This case is the result of query A -[*0]-> B.
                    #   If A is qualified to be B (node attr match), set B = A else break
                    for a, b in zero_hop_edges:
                        if b in match and match[b] != match[a]:
                            break
                        if not _is_node_attr_match(
                            b, match[a], self._motif, self._target_graph
                        ):
                            break
                        match[b] = match[a]
                    else:  # For/else loop
                        # Check if match matches where condition and add
                        if not self._where_condition or self._where_condition(
                            match, self._target_graph, self._return_edges
                        ):
                            self_matches.append(match)
                            self_matche_paths.append(edge_hop_map)

                            # Check if limit reached; stop ONLY IF we are not ordering
                            if self._is_limit(len(self_matches)) and not self._order_by:
                                complete = True
                                break

            self._matches = self_matches
            self._matche_paths = self_matche_paths

        return list(zip(self._matches, self._matche_paths))

    def _matches_iter(self, motif):
        # Get list of all match iterators
        iterators = [
            grandiso.find_motifs_iter(
                motif.subgraph(c),
                self._target_graph,
                is_node_attr_match=_is_node_attr_match,
                is_edge_attr_match=_is_edge_attr_match,
            )
            for c in nx.weakly_connected_components(motif)
        ]

        # Single match clause iterator
        if iterators and len(iterators) == 1:
            yield from iterators[0]

        # Multi match clause, requires a cartesian join
        else:
            iterations, matches = 0, {}
            for x, iterator in enumerate(iterators):
                for match in iterator:
                    if x not in matches:
                        matches[x] = []

                    matches[x].append(match)
                    iterations += 1

                    # Continue to next clause if limit reached
                    if self._is_limit(len(matches[x])):
                        continue

            # Cartesian product of all match clauses
            join = []
            for match in matches.values():
                if join:
                    join = [{**a, **b} for a in join for b in match]
                else:
                    join = match

            # Yield cartesian product
            yield from join

    def _is_limit(self, count):
        # Check if limit reached
        return self._limit and count >= (self._limit + self._skip)

    def _edge_hop_motifs(self, motif: nx.DiGraph) -> List[Tuple[nx.Graph, dict]]:
        """generate a list of edge-hop-expanded motif with edge-hop-map.

        Arguments:
            motif (nx.Graph): The motif graph

        Returns:
            List[Tuple[nx.Graph, dict]]: list of motif and edge-hop-map. \
                edge-hop-map is a mapping from an edge to a real edge path
                where a real edge path can have more than 2 element (hop >= 2)
                or it can have 2 same element (hop = 0).
        """
        new_motif = nx.DiGraph()
        for n in motif.nodes:
            if motif.out_degree(n) == 0 and motif.in_degree(n) == 0:
                new_motif.add_node(n, **motif.nodes[n])
        motifs: List[Tuple[nx.DiGraph, dict]] = [(new_motif, {})]
        for u, v in motif.edges:
            new_motifs = []
            min_hop = motif.edges[u, v]["__min_hop__"]
            max_hop = motif.edges[u, v]["__max_hop__"]
            edge_type = motif.edges[u, v]["__labels__"]
            hops = []
            if min_hop == 0:
                new_motif = nx.DiGraph()
                new_motif.add_node(u, **motif.nodes[u])
                new_motifs.append((new_motif, {(u, v): (u, u)}))
            elif min_hop >= 1:
                for _ in range(1, min_hop):
                    hops.append(shortuuid())
            for _ in range(max(min_hop, 1), max_hop):
                new_edges = [u] + hops + [v]
                new_motif = nx.DiGraph()
                new_motif.add_edges_from(
                    list(zip(new_edges[:-1], new_edges[1:])), __labels__=edge_type
                )
                new_motif.add_node(u, **motif.nodes[u])
                new_motif.add_node(v, **motif.nodes[v])
                new_motifs.append((new_motif, {(u, v): tuple(new_edges)}))
                hops.append(shortuuid())
            motifs = self._product_motifs(motifs, new_motifs)
        return motifs

    def _product_motifs(
        self,
        motifs_1: List[Tuple[nx.DiGraph, dict]],
        motifs_2: List[Tuple[nx.DiGraph, dict]],
    ):
        new_motifs = []
        for motif_1, mapping_1 in motifs_1:
            for motif_2, mapping_2 in motifs_2:
                motif = nx.DiGraph()
                motif.add_nodes_from(motif_1.nodes.data())
                motif.add_nodes_from(motif_2.nodes.data())
                motif.add_edges_from(motif_1.edges.data())
                motif.add_edges_from(motif_2.edges.data())
                new_motifs.append((motif, {**mapping_1, **mapping_2}))
        return new_motifs

    def entity_id(self, entity_id):
        if len(entity_id) == 2:
            return ".".join(entity_id)
        return entity_id.value

    def edge_match(self, edge_name):
        direction = cname = min_hop = max_hop = edge_type = None

        for token in edge_name:
            if token.type == "MIN_HOP":
                min_hop = int(token.value)
            elif token.type == "MAX_HOP":
                max_hop = int(token.value) + 1
            elif token.type == "LEFT_ANGLE":
                direction = "l"
            elif token.type == "RIGHT_ANGLE" and direction == "l":
                direction = "b"
            elif token.type == "RIGHT_ANGLE":
                direction = "r"
            elif token.type == "TYPE":
                edge_type = token.value
            else:
                cname = token

        direction = direction if direction is not None else "b"
        if (min_hop is not None or max_hop is not None) and (direction == "b"):
            raise TypeError("not support edge hopping for bidirectional edge")

        return (cname, edge_type, direction, min_hop, max_hop)

    def node_match(self, node_name):
        cname = node_type = json_data = None
        for token in node_name:
            if not isinstance(token, Token):
                json_data = token
            elif token.type == "CNAME":
                cname = token
            elif token.type == "TYPE":
                node_type = token.value
        cname = cname or Token("CNAME", shortuuid())
        json_data = json_data or {}
        node_type = set([node_type]) if node_type else set()

        return (cname, node_type, json_data)

    def match_clause(self, match_clause: Tuple):
        if len(match_clause) == 1:
            # This is just a node match:
            u, ut, js = match_clause[0]
            self._motif.add_node(u.value, __labels__=ut, **js)
            return

        match_clause = match_clause[1:] if not match_clause[0] else match_clause
        for start in range(0, len(match_clause) - 2, 2):
            ((u, ut, ujs), (g, t, d, minh, maxh), (v, vt, vjs)) = match_clause[
                start : start + 3
            ]
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

            ish = minh is None and maxh is None
            minh = minh if minh is not None else 1
            maxh = maxh if maxh is not None else minh + 1
            if maxh > self._max_hop:
                raise ValueError(f"max hop is caped at 100, found {maxh}!")
            if t:
                t = set([t])
            self._motif.add_edges_from(
                edges, __min_hop__=minh, __max_hop__=maxh, __is_hop__=ish, __labels__=t
            )

            self._motif.add_node(u, __labels__=ut, **ujs)
            self._motif.add_node(v, __labels__=vt, **vjs)

    def path_clause(self, path_clause: tuple):
        self._paths.append(path_clause[0])

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

    def condition_not(self, processed_condition):
        return (not processed_condition[0][0], *processed_condition[0][1:])

    null = lambda self, _: None
    true = lambda self, _: True
    false = lambda self, _: False
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

    def op_in(self, _):
        return _OPERATORS["in"]

    def op_contains(self, _):
        return _OPERATORS["contains"]

    def op_starts_with(self, _):
        return _OPERATORS["starts_with"]

    def op_ends_with(self, _):
        return _OPERATORS["ends_with"]

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

    def __init__(self, host_graph: nx.Graph, limit: int = None) -> None:
        """
        Create a new GrandCypher object to query graphs with Cypher.

        Arguments:
            host_graph (nx.Graph): The host graph to use as a "graph database"
            limit (int): The default limit to apply to queries when not otherwise provided

        Returns:
            None

        """

        self._transformer = _GrandCypherTransformer(host_graph, limit)
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
