"""
GrandCypher is a Cypher interpreter for the Grand graph library.

You can use this tool to search Python graph data-structures by
data/attribute or by structure, using the same language you'd use
to search in a much larger graph database.

"""

from typing import Dict, Hashable, List, Callable, Optional, Tuple, Union
from collections import OrderedDict
import random
import string
import logging
from functools import lru_cache
import networkx as nx

import grandiso

from lark import Lark, Transformer, v_args, Token, Tree

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


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

condition           : (entity_id | scalar_function) op entity_id_or_value
                    | (entity_id | scalar_function) op_list value_list
                    | "not"i condition -> condition_not

?entity_id_or_value : entity_id
                    | value
                    | NULL -> null
                    | TRUE -> true
                    | FALSE -> false

op                  : "==" -> op_eq
                    | "=" -> op_eq
                    | "<>" -> op_neq
                    | ">" -> op_gt
                    | "<" -> op_lt
                    | ">="-> op_gte
                    | "<="-> op_lte
                    | "is"i -> op_is
                    | "contains"i -> op_contains
                    | "starts with"i -> op_starts_with
                    | "ends with"i -> op_ends_with

op_list             : "in"i -> op_in



return_clause       : "return"i distinct_return? return_item ("," return_item)*
return_item         : (entity_id | aggregation_function | scalar_function | entity_id "." attribute_id) ( "AS"i alias )?
alias               : CNAME

aggregation_function : AGGREGATE_FUNC "(" entity_id ( "." attribute_id )? ")"
AGGREGATE_FUNC       : "COUNT" | "SUM" | "AVG" | "MAX" | "MIN"
attribute_id         : CNAME

scalar_function      : "id"i "(" entity_id ")" -> id_function

distinct_return     : "DISTINCT"i
limit_clause        : "limit"i NUMBER
skip_clause         : "skip"i NUMBER

order_clause        : "order"i "by"i order_items

order_items         : order_item ("," order_item)*

order_item          : (entity_id | aggregation_function) order_direction?

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
                    | LEFT_ANGLE? "-[" CNAME ":" type_list "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" ":" type_list "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" "*" MIN_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" "*" MIN_HOP  ".." MAX_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" CNAME "*" MIN_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" CNAME "*" MIN_HOP  ".." MAX_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" ":" TYPE "*" MIN_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" ":" TYPE "*" MIN_HOP  ".." MAX_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" CNAME ":" TYPE "*" MIN_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" CNAME ":" TYPE "*" MIN_HOP  ".." MAX_HOP "]-" RIGHT_ANGLE?

value_list          : "[" [value ("," value)*] "]"
type_list           : TYPE ( "|" TYPE )*

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
                    | NULL -> null
                    | TRUE -> true
                    | FALSE -> false

NULL.1                : "NULL"i
TRUE.1                : "TRUE"i
FALSE.1               : "FALSE"i


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

__version__ = "1.0.0"


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
    motif_edge_id: Tuple[str, str, Union[int, str]],
    host_edge_id: Tuple[str, str, Union[int, str]],
    motif: Union[nx.Graph, nx.MultiDiGraph],
    host: Union[nx.Graph, nx.MultiDiGraph],
) -> bool:
    """
    Check if an edge in the host graph matches the attributes in the motif,
    including the special '__labels__' set attribute.
    This function formats edges into
    nx.MultiDiGraph format i.e {0: first_relation, 1: ...}.

    Arguments:
        motif_edge_id (str): The motif edge ID
        host_edge_id (str): The host edge ID
        motif (nx.Graph): The motif graph
        host (nx.Graph): The host graph

    Returns:
        bool: True if the host edge matches the attributes in the motif
    """
    motif_u, motif_v = motif_edge_id
    host_u, host_v = host_edge_id

    # Format edges for both DiGraph and MultiDiGraph
    motif_edges = _get_edge_attributes(motif, motif_u, motif_v)
    host_edges = _get_edge_attributes(host, host_u, host_v)

    if not motif_edges or not host_edges:
        # if there are no edges, they don't match
        return False

    # Aggregate all __labels__ into one set
    motif_edges = _aggregate_edge_labels(motif_edges)
    host_edges = _aggregate_edge_labels(host_edges)

    motif_types = motif_edges.get("__labels__", set())
    host_types = host_edges.get("__labels__", set())

    if motif_types and not motif_types.intersection(host_types):
        return False

    for attr, val in motif_edges.items():
        if attr == "__labels__":
            continue
        if host_edges.get(attr) != val:
            return False

    return True


def _get_edge_attributes(graph: Union[nx.Graph, nx.MultiDiGraph], u, v) -> Dict:
    """
    Retrieve edge attributes from a graph, handling both Graph and MultiDiGraph.
    """
    if graph.is_multigraph():
        return graph.get_edge_data(u, v)
    else:
        data = graph.get_edge_data(u, v)
        return {0: data}  # Wrap in dict to mimic MultiDiGraph structure


def _aggregate_edge_labels(edges: Dict) -> Dict:
    """
    Aggregate '__labels__' attributes from edges into a single set.
    """
    aggregated = {"__labels__": set()}
    for edge_id, attrs in edges.items():
        if "__labels__" in attrs and attrs["__labels__"]:
            aggregated["__labels__"].update(attrs["__labels__"])
        elif "__labels__" not in attrs:
            aggregated[edge_id] = attrs
    return aggregated


def _get_entity_from_host(
    host: Union[nx.DiGraph, nx.MultiDiGraph], entity_name, entity_attribute=None
):
    if entity_name in host.nodes():
        # We are looking for a node mapping in the target graph:
        if entity_attribute:
            # Get the correct entity from the target host graph,
            # and then return the attribute:
            return host.nodes[entity_name].get(entity_attribute, None)
        else:
            # Otherwise, just return the dict of attributes:
            return host.nodes[entity_name]
    else:
        # looking for an edge:
        u, v = entity_name
        edge_data = _get_edge_attributes(host, u, v)
        if not edge_data:
            return None  # print(f"Nothing found for {entity_name} {entity_attribute}")

        if entity_attribute:
            # looking for edge attribute:
            if host.is_multigraph():
                # return a list of attribute values for all edges between u and v
                return [attrs.get(entity_attribute) for attrs in edge_data.values()]
            else:
                # return the attribute value for the single edge
                return edge_data[0].get(entity_attribute)
        else:
            return edge_data


def _get_edge(host: Union[nx.DiGraph, nx.MultiDiGraph], mapping, match_path, u, v):
    edge_path = match_path[(u, v)]
    return [
        _get_edge_attributes(host, mapping[u], mapping[v])
        for u, v in zip(edge_path[:-1], edge_path[1:])
    ]


CONDITION = Callable[[dict, nx.DiGraph, list], bool]


def and_(cond_a, cond_b) -> CONDITION:
    def inner(match: dict, host: nx.DiGraph, return_edges: list) -> bool:
        condition_a, where_a = cond_a(match, host, return_edges)
        condition_b, where_b = cond_b(match, host, return_edges)
        where_result = [a and b for a, b in zip(where_a, where_b)]
        return (condition_a and condition_b), where_result

    return inner


def or_(cond_a, cond_b):
    def inner(match: dict, host: nx.DiGraph, return_edges: list) -> bool:
        condition_a, where_a = cond_a(match, host, return_edges)
        condition_b, where_b = cond_b(match, host, return_edges)
        where_result = [a or b for a, b in zip(where_a, where_b)]
        return (condition_a or condition_b), where_result

    return inner


def cond_(should_be, entity_id, operator, value) -> CONDITION:
    def inner(
        match: dict, host: Union[nx.DiGraph, nx.MultiDiGraph], return_edges: list
    ) -> bool:
        # Check if this is an ID function call
        if entity_id.startswith("ID(") and entity_id.endswith(")"):
            # Extract the entity name from ID(entity_name)
            actual_entity_name = entity_id[3:-1]  # Remove "ID(" and ")"
            if actual_entity_name in match:
                # Return the node ID directly
                node_id = match[actual_entity_name]
                try:
                    val = operator(node_id, value)
                except:
                    val = False
                operator_results = [val]
            else:
                raise IndexError(f"Entity {actual_entity_name} not in match.")
        else:
            # Regular entity attribute access
            host_entity_id = entity_id.split(".")
            if host_entity_id[0] in match:
                host_entity_id[0] = match[host_entity_id[0]]
            elif host_entity_id[0] in return_edges:
                # looking for edge...
                edge_mapping = return_edges[host_entity_id[0]]
                host_entity_id[0] = (match[edge_mapping[0]], match[edge_mapping[1]])
            else:
                raise IndexError(f"Entity {host_entity_id} not in graph.")

            operator_results = []
            if isinstance(host, nx.MultiDiGraph):
                # if any of the relations between nodes satisfies condition, return True
                r_vals = _get_entity_from_host(host, *host_entity_id)
                r_vals = [r_vals] if not isinstance(r_vals, list) else r_vals
                for r_val in r_vals:
                    try:
                        operator_results.append(operator(r_val, value))
                    except:
                        operator_results.append(False)
                val = any(operator_results)
            else:
                try:
                    val = operator(_get_entity_from_host(host, *host_entity_id), value)
                except:
                    val = False
                operator_results.append(val)

        if val != should_be:
            return False, operator_results
        return True, operator_results

    return inner


_BOOL_ARI = {
    "and": and_,
    "or": or_,
}


def _data_path_to_entity_name_attribute(data_path):
    if isinstance(data_path, Token):
        data_path = data_path.value
    if "." in data_path:
        entity_name, entity_attribute = data_path.split(".")
    else:
        entity_name = data_path
        entity_attribute = None

    return entity_name, entity_attribute


class _GrandCypherTransformer(Transformer):
    def __init__(self, target_graph: nx.Graph, limit: Optional[int] = None):
        self._target_graph = target_graph
        self._entity2alias = dict()
        self._alias2entity = dict()
        self._paths = []
        self._where_condition = None  # type: Optional[CONDITION]
        self._motif = nx.MultiDiGraph()
        self._matches = None
        self._matche_paths = None
        self._return_requests = []
        self._return_edges = {}
        self._aggregate_functions = []
        self._aggregation_attributes = set()
        self._original_return_requests = set()
        self._distinct = False
        self._order_by = None
        self._order_by_attributes = set()
        self._limit = limit
        self._skip = 0
        self._max_hop = 100
        self._hints: Optional[List[Dict[Hashable, Hashable]]] = None

    def set_hints(self, hints=None):
        self._hints = hints
        return self

    def transform(self, tree, hints=None):
        self.set_hints(hints)
        return super().transform(tree)

    def _lookup(self, data_paths: List[str], offset_limit) -> Dict[str, List]:
        def _filter_edge(edge, where_results):
            # no where condition -> return edge
            if where_results == []:
                return edge
            else:
                # exclude edge(s) from multiedge that don't satisfy the where condition
                edge = {k: v for k, v in edge[0].items() if where_results[k] is True}
                return [edge]

        if not data_paths:
            return {}

        motif_nodes = self._motif.nodes()

        # Get true matches FIRST, before processing data paths
        true_matches = self._get_true_matches()

        result = {}
        processed_paths = set()  # Keep track of processed paths

        for data_path in data_paths:
            entity_name, _ = _data_path_to_entity_name_attribute(data_path)
            # Special handling for ID function
            if entity_name.upper().startswith("ID(") and entity_name.endswith(")"):
                # Extract the original entity name
                original_entity = entity_name[3:-1]
                if original_entity in motif_nodes:
                    # Return the node ID directly instead of the node attributes
                    ret = [mapping[0][original_entity] for mapping, _ in true_matches]
                    result[data_path] = ret[offset_limit]
                    result[original_entity] = ret[
                        offset_limit
                    ]  # Also store under original entity name
                    processed_paths.add(data_path)  # Mark as processed
                    processed_paths.add(
                        original_entity
                    )  # Mark original also as processed
                    continue
            if (
                entity_name not in motif_nodes
                and entity_name not in self._return_edges
                and entity_name not in self._paths
            ):
                raise NotImplementedError(f"Unknown entity name: {data_path}")

        for data_path in data_paths:
            if data_path in processed_paths:  # Skip already processed paths
                continue

            entity_name, entity_attribute = _data_path_to_entity_name_attribute(
                data_path
            )

            if entity_name in motif_nodes:
                # We are looking for a node mapping in the target graph:

                if entity_attribute:
                    # Get the correct entity from the target host graph,
                    # and then return the attribute:
                    ret = (
                        self._target_graph.nodes[mapping[0][entity_name]].get(
                            entity_attribute, None
                        )
                        for mapping, _ in true_matches
                    )
                else:
                    # Return the full node dictionary with all attributes
                    ret = (
                        self._target_graph.nodes[mapping[0][entity_name]]
                        for mapping, _ in true_matches
                    )

            elif entity_name in self._paths:
                ret = []
                for mapping, _ in true_matches:
                    mapping = mapping[0]
                    path, nodes = [], list(mapping.values())
                    for x, node in enumerate(nodes):
                        # Edge
                        if x > 0:
                            path.append(
                                self._target_graph.get_edge_data(nodes[x - 1], node)
                            )

                        # Node
                        path.append(node)

                    ret.append(path)

            else:
                mapping_u, mapping_v = self._return_edges[data_path.split(".")[0]]
                # We are looking for an edge mapping in the target graph:
                is_hop = self._motif.edges[(mapping_u, mapping_v, 0)]["__is_hop__"]
                ret = (
                    _filter_edge(
                        _get_edge(
                            self._target_graph,
                            mapping[0],
                            match_path,
                            mapping_u,
                            mapping_v,
                        ),
                        mapping[1],
                    )
                    for mapping, match_path in true_matches
                )
                ret = (r[0] if is_hop else r for r in ret)
                # we keep the original list if len > 2 (edge hop 2+)

                # Get all edge labels from the motif -- this is used to filter the relations for multigraphs
                motif_edge_labels = set()
                for edge in self._motif.get_edge_data(mapping_u, mapping_v).values():
                    if edge.get("__labels__", None):
                        motif_edge_labels.update(edge["__labels__"])

                if entity_attribute:
                    # Get the correct entity from the target host graph,
                    # and then return the attribute:
                    if (
                        isinstance(self._motif, nx.MultiDiGraph)
                        and len(motif_edge_labels) > 0
                    ):
                        # filter the retrieved edge(s) based on the motif edge labels
                        filtered_ret = []
                        for r in ret:
                            r = {
                                k: v
                                for k, v in r.items()
                                if v.get("__labels__", None).intersection(
                                    motif_edge_labels
                                )
                            }
                            if len(r) > 0:
                                filtered_ret.append(r)

                        ret = filtered_ret

                    # get the attribute from the retrieved edge(s)
                    ret_with_attr = []
                    for r in ret:
                        r_attr = {}
                        if isinstance(r, dict):
                            r = [r]
                        for el in r:
                            for i, v in enumerate(el.values()):
                                r_attr[(i, list(v.get("__labels__", [i]))[0])] = v.get(
                                    entity_attribute, None
                                )
                                # eg, [{(0, 'paid'): 70, (1, 'paid'): 90}, {(0, 'paid'): 400, (1, 'friend'): None, (2, 'paid'): 650}]
                            ret_with_attr.append(r_attr)

                    ret = ret_with_attr

            result[data_path] = list(ret)[offset_limit]

        return result

    def return_clause(self, clause):
        # collect all entity identifiers to be returned
        for item in clause:
            if item:
                alias = self._extract_alias(item)
                item = item.children[0] if isinstance(item, Tree) else item
                if isinstance(item, Tree) and item.data == "aggregation_function":
                    func, entity = self._parse_aggregation_token(item)
                    if alias:
                        self._entity2alias[
                            self._format_aggregation_key(func, entity)
                        ] = alias
                    self._aggregation_attributes.add(entity)
                    self._aggregate_functions.append((func, entity))
                else:
                    if not isinstance(item, str):
                        item = str(item.value)
                    self._original_return_requests.add(item)

                    if alias:
                        self._entity2alias[item] = alias
                    self._return_requests.append(item)

        self._alias2entity.update({v: k for k, v in self._entity2alias.items()})

    def _extract_alias(self, item: Tree):
        """
        Extract the alias from the return item (if it exists)
        """

        if len(item.children) == 1:
            return None
        item_keys = [it.data if isinstance(it, Tree) else None for it in item.children]
        if any(k == "alias" for k in item_keys):
            # get the index of the alias
            alias_index = item_keys.index("alias")
            return str(item.children[alias_index].children[0].value)

        return None

    def _parse_aggregation_token(self, item: Tree):
        """
        Parse the aggregation function token and return the function and entity
            input: Tree('aggregation_function', [Token('AGGREGATE_FUNC', 'SUM'), Token('CNAME', 'r'), Tree('attribute_id', [Token('CNAME', 'value')])])
            output: ('SUM', 'r.value')
        """
        func = str(item.children[0].value)  # AGGREGATE_FUNC
        entity = str(item.children[1].value)
        if len(item.children) > 2:
            entity += "." + str(item.children[2].children[0].value)

        return func, entity

    def _format_aggregation_key(self, func, entity):
        return f"{func}({entity})"

    def order_clause(self, order_clause):
        self._order_by = []
        for item in order_clause[0].children:
            if (
                isinstance(item.children[0], Tree)
                and item.children[0].data == "aggregation_function"
            ):
                func, entity = self._parse_aggregation_token(item.children[0])
                field = self._format_aggregation_key(func, entity)
                self._order_by_attributes.add(entity)
            else:
                field = str(
                    item.children[0]
                )  # assuming the field name is the first child
                self._order_by_attributes.add(field)

            # Default to 'ASC' if not specified
            if len(item.children) > 1 and str(item.children[1].data).lower() != "desc":
                direction = "ASC"
            else:
                direction = "DESC"

            self._order_by.append((field, direction))  # [('n.age', 'DESC'), ...]

    def distinct_return(self, distinct):
        self._distinct = True

    def limit_clause(self, limit):
        limit = int(limit[-1])
        self._limit = limit

    def skip_clause(self, skip):
        skip = int(skip[-1])
        self._skip = skip

    def aggregate(self, func, results, entity, group_keys):
        # Collect data based on group keys
        grouped_data = {}
        for i in range(len(results[entity])):
            group_tuple = tuple(results[key][i] for key in group_keys if key in results)
            if group_tuple not in grouped_data:
                grouped_data[group_tuple] = []
            grouped_data[group_tuple].append(results[entity][i])

        def _collate_data(data, unique_labels, func):
            # for ["COUNT", "SUM", "AVG"], we treat None as 0
            if func in ["COUNT", "SUM", "AVG"]:
                collated_data = {
                    label: [
                        (v or 0)
                        for rel in data
                        for k, v in rel.items()
                        if k[1] == label
                    ]
                    for label in unique_labels
                }
            # for ["MAX", "MIN"], we treat None as non-existent
            elif func in ["MAX", "MIN"]:
                collated_data = {
                    label: [
                        v
                        for rel in data
                        for k, v in rel.items()
                        if (k[1] == label and v is not None)
                    ]
                    for label in unique_labels
                }

            return collated_data

        # Apply aggregation function
        aggregate_results = {}
        for group, data in grouped_data.items():
            # data => [{(0, 'paid'): 70, (1, 'paid'): 90}]
            unique_labels = set([k[1] for rel in data for k in rel.keys()])
            collated_data = _collate_data(data, unique_labels, func)
            if func == "COUNT":
                count_data = {label: len(data) for label, data in collated_data.items()}
                aggregate_results[group] = count_data
            elif func == "SUM":
                sum_data = {label: sum(data) for label, data in collated_data.items()}
                aggregate_results[group] = sum_data
            elif func == "AVG":
                sum_data = {label: sum(data) for label, data in collated_data.items()}
                count_data = {label: len(data) for label, data in collated_data.items()}
                avg_data = {
                    label: (
                        sum_data[label] / count_data[label]
                        if count_data[label] > 0
                        else 0
                    )
                    for label in sum_data
                }
                aggregate_results[group] = avg_data
            elif func == "MAX":
                max_data = {label: max(data) for label, data in collated_data.items()}
                aggregate_results[group] = max_data
            elif func == "MIN":
                min_data = {label: min(data) for label, data in collated_data.items()}
                aggregate_results[group] = min_data

        aggregate_results = [v for v in aggregate_results.values()]
        return aggregate_results

    def returns(self, ignore_limit=False):
        data_paths = (
            self._return_requests
            + list(self._order_by_attributes)
            + list(self._aggregation_attributes)
        )
        # aliases should already be requested in their original form, so we will remove them for lookup
        data_paths = [d for d in data_paths if d not in self._alias2entity]
        results = self._lookup(
            data_paths,
            offset_limit=slice(0, None),
        )
        if len(self._aggregate_functions) > 0:
            group_keys = [
                key
                for key in results.keys()
                if not any(key.endswith(func[1]) for func in self._aggregate_functions)
            ]

            aggregated_results = {}
            for func, entity in self._aggregate_functions:
                aggregated_data = self.aggregate(func, results, entity, group_keys)
                func_key = self._format_aggregation_key(func, entity)
                aggregated_results[func_key] = aggregated_data
                self._return_requests.append(func_key)
            results.update(aggregated_results)

        # update the results with the given alias(es)
        results = {self._entity2alias.get(k, k): v for k, v in results.items()}

        if self._order_by:
            results = self._apply_order_by(results)

        # Apply DISTINCT before pagination
        if self._distinct:
            results = self._apply_distinct(results)

        # Only after all other transformations, apply pagination
        results = self._apply_pagination(results, ignore_limit)
        self._return_requests = list(map(str, self._return_requests))

        # Only include keys that were asked for in `RETURN` in the final results
        results = {
            self._entity2alias.get(key, key): values
            for key, values in results.items()
            if key in self._return_requests
            or self._alias2entity.get(key, key) in self._return_requests
        }

        # HACK: convert to [None] if edge is None
        for key, values in results.items():
            parsed_values = []
            for v in values:
                if v == [{0: None}]:  # edge is None
                    parsed_values.append([None])
                else:
                    parsed_values.append(v)
            results[key] = parsed_values

        return results

    def _apply_order_by(self, results):
        if self._order_by:
            sort_lists = [
                (results[field], field, direction)
                for field, direction in self._order_by
            ]

            if sort_lists:
                # Generate a list of indices sorted by the specified fields
                indices = range(
                    len(next(iter(results.values())))
                )  # Safe because all lists are assumed to be of the same length
                for sort_list, field, direction in reversed(
                    sort_lists
                ):  # reverse to ensure the first sort key is primary
                    if all(isinstance(item, dict) for item in sort_list):
                        # (for edge attributes) If all items in sort_list are dictionaries
                        # example: ([{(0, 'paid'): 9, (1, 'paid'): 40}, {(0, 'paid'): 14}], 'DESC')

                        # sort within each edge first
                        sorted_sublists = []
                        for sublist in sort_list:
                            # Create a new sorted dictionary directly
                            sorted_dict = {}
                            # Get keys sorted by their values
                            sorted_keys = sorted(
                                sublist.keys(),
                                key=lambda k: sublist[k] or 0,  # 0 if `None`
                                reverse=(direction == "DESC"),
                            )
                            # Insert keys in sorted order
                            for k in sorted_keys:
                                sorted_dict[k] = sublist[k]
                            sorted_sublists.append(sorted_dict)
                        sort_list = sorted_sublists

                        # then sort the indices based on the sorted sublists
                        indices = sorted(
                            indices,
                            key=lambda i: list(sort_list[i].values())[0]
                            or 0,  # 0 if `None`
                            reverse=(direction == "DESC"),
                        )
                        # update results with sorted edge attributes list
                        results[field] = sort_list
                    else:
                        # (for node attributes) single values
                        indices = sorted(
                            indices,
                            key=lambda i: sort_list[i],
                            reverse=(direction == "DESC"),
                        )

                # Reorder all lists in results using sorted indices
                for key in results:
                    results[key] = [results[key][i] for i in indices]

        return results

    def _apply_distinct(self, results):
        if self._order_by:
            assert self._order_by_attributes.issubset(self._return_requests), (
                "In a WITH/RETURN with DISTINCT or an aggregation, it is not possible to access variables declared before the WITH/RETURN"
            )

        # ordered dict to maintain the first occurrence of each unique tuple based on return requests
        unique_rows = OrderedDict()

        # Iterate over each 'row' by index
        for i in range(
            len(next(iter(results.values())))
        ):  # assume all columns are of the same length
            # create a tuple key of all the values from return requests for this row
            row_key = tuple(
                results[key][i] for key in self._return_requests if key in results
            )

            if row_key not in unique_rows:
                unique_rows[row_key] = (
                    i  # store the index of the first occurrence of this unique row
                )

        # construct the results based on unique indices collected
        distinct_results = {key: [] for key in self._return_requests}
        for row_key, index in unique_rows.items():
            for _, key in enumerate(self._return_requests):
                distinct_results[key].append(results[key][index])

        return distinct_results

    def _apply_pagination(self, results, ignore_limit):
        """
        Apply pagination (skip & limit) to results.

        Args:
            results: Dictionary of result lists
            ignore_limit: Whether to ignore the limit constraint

        Returns:
            Dictionary with paginated results
        """
        # If there are no results, return early
        if not results:
            return results

        # Get the length of any result list (all should be the same length)
        if not any(results.values()):
            return results

        result_length = len(next(iter(results.values())))
        if result_length == 0:
            return results

        # Apply skip first
        start_index = min(self._skip or 0, result_length)

        # Then apply limit if needed
        if self._limit is not None and not ignore_limit:
            end_index = min(start_index + self._limit, result_length)
        else:
            end_index = result_length

        # Apply pagination to all result lists
        paginated_results = {}
        for key, values in results.items():
            paginated_results[key] = values[start_index:end_index]

        return paginated_results

    def _get_true_matches(self):
        """Get the true matches after applying WHERE conditions and hints.
        Returns the matches along with their paths.

        Returns:
            List of tuples containing (match, path)
        """
        if not self._matches:
            self_matches = []
            self_matche_paths = []

            for my_motif, edge_hop_map in self._edge_hop_motifs(self._motif):
                # Process zero hop edges
                zero_hop_edges = [
                    k for k, v in edge_hop_map.items() if len(v) == 2 and v[0] == v[1]
                ]

                # Collect all valid matches before applying pagination
                for match in self._matches_iter(my_motif):
                    # Handle zero hop edges
                    valid_match = True
                    for a, b in zero_hop_edges:
                        if b in match and match[b] != match[a]:
                            valid_match = False
                            break
                        if not _is_node_attr_match(
                            b, match[a], self._motif, self._target_graph
                        ):
                            valid_match = False
                            break
                        match[b] = match[a]

                    if not valid_match:
                        continue

                    # Apply WHERE condition if present
                    if self._where_condition:
                        satisfies_where, where_results = self._where_condition(
                            match, self._target_graph, self._return_edges
                        )
                        if not satisfies_where:
                            continue
                    else:
                        where_results = []

                    self_matches.append((match, where_results))
                    self_matche_paths.append(edge_hop_map)

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
                hints=self._hints if self._hints is not None else [],
            )
            for c in nx.weakly_connected_components(motif)
        ]

        # Single match clause iterator
        if iterators and len(iterators) == 1:
            yield from iterators[0]
        else:
            iterations, matches = 0, {}
            for x, iterator in enumerate(iterators):
                for match in iterator:
                    if x not in matches:
                        matches[x] = []
                    matches[x].append(match)
                    iterations += 1
                    if self._is_limit(len(matches[x])):
                        break

            join = []
            for match in matches.values():
                if join:
                    join = [{**a, **b} for a in join for b in match]
                else:
                    join = match
            yield from join

    def _edge_hop_motifs(self, motif: nx.MultiDiGraph) -> List[Tuple[nx.Graph, dict]]:
        """generate a list of edge-hop-expanded motif with edge-hop-map.

        Arguments:
            motif (nx.Graph): The motif graph

        Returns:
            List[Tuple[nx.Graph, dict]]: list of motif and edge-hop-map. \
                edge-hop-map is a mapping from an edge to a real edge path
                where a real edge path can have more than 2 element (hop >= 2)
                or it can have 2 same element (hop = 0).
        """
        new_motif = nx.MultiDiGraph()
        for n in motif.nodes:
            if motif.out_degree(n) == 0 and motif.in_degree(n) == 0:
                new_motif.add_node(n, **motif.nodes[n])
        motifs: List[Tuple[nx.DiGraph, dict]] = [(new_motif, {})]

        if motif.is_multigraph():
            edge_iter = motif.edges(keys=True)
        else:
            edge_iter = motif.edges(keys=False)

        for edge in edge_iter:
            if motif.is_multigraph():
                u, v, k = edge
            else:
                u, v = edge
                k = 0  # Dummy key for DiGraph
            new_motifs = []
            min_hop = motif.edges[u, v, k]["__min_hop__"]
            max_hop = motif.edges[u, v, k]["__max_hop__"]
            edge_type = motif.edges[u, v, k]["__labels__"]
            hops = []
            if min_hop == 0:
                new_motif = nx.MultiDiGraph()
                new_motif.add_node(u, **motif.nodes[u])
                new_motifs.append((new_motif, {(u, v): (u, u)}))
            elif min_hop >= 1:
                for _ in range(1, min_hop):
                    hops.append(shortuuid())
            for _ in range(max(min_hop, 1), max_hop):
                new_edges = [u] + hops + [v]
                new_motif = nx.MultiDiGraph()
                new_motif.add_edges_from(
                    zip(new_edges, new_edges[1:]), __labels__=edge_type
                )
                new_motif.add_node(u, **motif.nodes[u])
                new_motif.add_node(v, **motif.nodes[v])
                new_motifs.append((new_motif, {(u, v): tuple(new_edges)}))
                hops.append(shortuuid())
            motifs = self._product_motifs(motifs, new_motifs)
        return motifs

    def _product_motifs(
        self,
        motifs_1: List[Tuple[nx.Graph, dict]],
        motifs_2: List[Tuple[nx.Graph, dict]],
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

    def edge_match(self, edge_tokens):
        def flatten_tokens(edge_tokens):
            flat_tokens = []
            for token in edge_tokens:
                if isinstance(token, Tree):
                    flat_tokens.extend(
                        flatten_tokens(token.children)
                    )  # Recursively flatten the tree
                else:
                    flat_tokens.append(token)
            return flat_tokens

        direction = cname = min_hop = max_hop = None
        edge_types = []
        edge_tokens = flatten_tokens(edge_tokens)

        for token in edge_tokens:
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
                edge_types.append(token.value)
            else:
                cname = token

        direction = direction if direction is not None else "b"
        if (min_hop is not None or max_hop is not None) and (direction == "b"):
            raise TypeError("Bidirectional edge does not support edge hopping")

        # Handle the case where no edge types are specified, defaulting to a generic type if needed
        if edge_types == []:
            edge_types = None

        return (cname, edge_types, direction, min_hop, max_hop)

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
                t = set([t] if type(t) is str else t)
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

    def id_function(self, entity_id):
        entity_name = entity_id[0].value
        # Add the raw entity ID to the return requests as well
        # This ensures tests like test_id can still access res["A"]
        # self._return_requests.append(entity_name)
        # Return a special identifier that will be processed in _lookup method
        return f"ID({entity_name})"

    def value_list(self, items):
        return list(items)

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

    def _is_limit(self, length):
        """Check if the current number of results has reached the limit.

        Args:
            length: The current number of results.

        Returns:
            True if we've reached the limit, False otherwise.
        """
        return self._limit is not None and length >= self._limit


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

    def run(self, cypher: str, hints: Optional[List[dict]] = None) -> Dict[str, List]:
        """
        Run a cypher query on the host graph.

        Arguments:
            cypher (str): The cypher query to run
            hints (list[dict]): A list of partial-mapping hints to pass along
                                to grandiso.find_motifs

        Returns:
            Dict[str, List]: A dictionary mapping of results, where keys are
                the items the user requested in the RETURN statement, and the
                values are all possible matches of that structure in the graph.

        """
        self._transformer.transform(_GrandCypherGrammar.parse(cypher), hints=hints)
        return self._transformer.returns()
