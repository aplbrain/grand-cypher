"""
GrandCypher is a Cypher interpreter for the Grand graph library.

You can use this tool to search Python graph data-structures by
data/attribute or by structure, using the same language you'd use
to search in a much larger graph database.

"""

from typing import Any, Dict, Generator, Hashable, List, Callable, Optional, Tuple, Union
from collections import OrderedDict
import random
import string
from functools import lru_cache
import networkx as nx
from grandcypher.struct import (
    EdgeHopKey, EdgeMapping, EdgeWithKey, HopAssignment, Match, NodeMapping, generate_edge_hop_specs,
    generate_hop_assignments, materialize_motif, unify_zero_hop_nodes)
from lark import Lark, Transformer, v_args, Token, Tree
from itertools import chain, product

import grandiso

from .hinter  import HintType, Hinter
from .indexer import (
    Compare as IndexerCompare, OR as IndexerOr,
    AND as IndexerAnd, ArrayAttributeIndexer, IndexerConditionAST,
    UnsupportedOp as IndexerUnsupportedOp, IndexerConditionRunner)
from .types import EntityRef, AttributeRef, IDRef


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

condition           : arith_expr op arith_expr
                    | (entity_id | scalar_function) op_list value_list  // IN: no arithmetic on LHS by design
                    | sub_query
                    | "not"i condition -> condition_not

?arith_expr         : arith_term
                    | arith_expr "+" arith_term -> arith_add
                    | arith_expr "-" arith_term -> arith_sub

?arith_term         : arith_atom
                    | arith_term "*" arith_atom -> arith_mul
                    | arith_term "/" arith_atom -> arith_div
                    | arith_term "%" arith_atom -> arith_mod

?arith_atom         : entity_id
                    | scalar_function
                    | value
                    | NULL -> null
                    | TRUE -> true
                    | FALSE -> false
                    | "(" arith_expr ")"

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

sub_op              : "EXISTS" -> subop_exist

sub_query           : sub_op "{" sub_query_body "}"

sub_query_body      : many_match_clause where_clause? return_clause?


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
                    | "(" (CNAME)? ":" type_list (json_dict)? ")"

edge_match          : LEFT_ANGLE? "--" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" CNAME "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" CNAME ":" type_list "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" ":" type_list "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" "*" MIN_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" "*" MIN_HOP  ".." MAX_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" CNAME "*" MIN_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" CNAME "*" MIN_HOP  ".." MAX_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" ":" type_list "*" MIN_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" ":" type_list "*" MIN_HOP  ".." MAX_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" CNAME ":" type_list "*" MIN_HOP "]-" RIGHT_ANGLE?
                    | LEFT_ANGLE? "-[" CNAME ":" type_list "*" MIN_HOP  ".." MAX_HOP "]-" RIGHT_ANGLE?

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

__version__ = "1.0.1"


_ALPHABET = string.ascii_lowercase + string.digits


def shortuuid(k=4) -> str:
    return "".join(random.choices(_ALPHABET, k=k))


class SUBOP:
    pass


class SUBOP_EXIST(SUBOP):

    def __call__(self, match: dict, executor: "GrandCypherExecutor"):
        executor.clear_matches()
        # backup some settings
        bk_hints = executor._hints
        bk_run_without_return = executor.run_without_return
        bk_limit = executor._limit
        bk_doublecheck_hint = executor._doublecheck_hint_result
        bk_auto_where_hints = executor._auto_where_hints
        bk_auto_node_jsondata_hints = executor._auto_node_jsondata_hints
        # settings such that it favor EXISTS operation
        executor.set_hints([match])
        # we don't need return, and we only need 1 row
        executor.run_without_return = True
        executor._limit = 1
        executor._doublecheck_hint_result = True
        executor._auto_where_hints = False
        executor._auto_node_jsondata_hints = False
        # run and ignore return
        executor.returns()
        # recover the settings
        executor.set_hints(bk_hints)
        executor.run_without_return = bk_run_without_return
        executor._limit = bk_limit
        executor._doublecheck_hint_result = bk_doublecheck_hint
        executor._auto_where_hints = bk_auto_where_hints
        executor._auto_node_jsondata_hints = bk_auto_node_jsondata_hints

        if executor._matches:
            return True
        return False


_SUB_OPERATORS = {
    "EXISTS": SUBOP_EXIST
}


_ARITH_OPS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    # Integer division to match Neo4j/Cypher semantics
    "/": lambda a, b: a // b if isinstance(a, int) and isinstance(b, int) else a / b,
    "%": lambda a, b: a % b,
}


class ArithmeticExpression:
    def __init__(self, left, op: str, right):
        self.left = left
        self.op = op
        self.right = right

    def resolve(self, match, host, return_edges):
        left_val = _resolve_operand(self.left, match, host, return_edges)
        right_val = _resolve_operand(self.right, match, host, return_edges)
        try:
            return _ARITH_OPS[self.op](left_val, right_val)
        except (TypeError, ZeroDivisionError, OverflowError):
            return None

    def __str__(self):
        return f"({self.left} {self.op} {self.right})"


def _resolve_operand(operand, match, host, return_edges):
    if isinstance(operand, ArithmeticExpression):
        return operand.resolve(match, host, return_edges)
    if isinstance(operand, IDRef):
        if operand.entity_name in match.node_mappings:
            return match.node_mappings[operand.entity_name]
        raise IndexError(f"Entity {operand.entity_name} not in match.")
    if isinstance(operand, AttributeRef):
        entity_name = operand.entity_name
        attribute = operand.attribute
        if entity_name in match.node_mappings:
            host_node_id = match.node_mappings[entity_name]
            return get_node_from_host(host, host_node_id, attribute)
        if entity_name in return_edges:
            edge_mapping = return_edges[entity_name]
            host_edges = match.mth.edge(*edge_mapping).edges
            return get_edge_from_host(host, host_edges, attribute)
        raise IndexError(f"Entity {operand} not in graph.")
    if isinstance(operand, EntityRef):
        raise TypeError(
            f"Cannot use bare entity '{operand}' in a comparison. "
            f"Use a property like '{operand}.attribute' or ID({operand})."
        )
    return operand


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
            host_types = host_node.get("__labels__", set())
            if val and not val.intersection(host_types):
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
    host_keys: Union[tuple[Hashable], None] = None,
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

    if host.is_multigraph():
        if host_keys is None and host.has_edge(host_u, host_v):
            host_keys =  host.get_edge_data(host_u, host_v).keys()
        if not host_keys:
            host_edges = []
        else:
            host_edges = [_get_edge_attributes(host, host_u, host_v, k) for k in host_keys]
    else:
        edge = _get_edge_attributes(host, host_u, host_v)
        if edge is None:
            host_edges = []
        else:
            host_edges: list[dict] = [edge]

    # NOTE: assume motif isn't a multi Digraph
    motif_edge = _get_edge_attributes(motif, motif_u, motif_v)

    # zero hop
    if motif_edge is None and not host_edges:
        return True

    if not motif_edge or not host_edges:
        # if there are no edges, they don't match
        return False

    motif_labels = motif_edge.get("__labels__", set())
    motif_labels = motif_labels if motif_labels is not None else set()

    for host_edge in host_edges:
        host_labels: set = host_edge.get("__labels__", set())
        for attr, val in motif_edge.items():
            if attr == "__labels__":
                if not motif_labels:
                    continue
                elif not host_labels.intersection(motif_labels):
                    break
            elif host_edge.get(attr) != val:
                break
        else:
            return True

    return False


def _get_edge_attributes(graph: Union[nx.Graph, nx.MultiDiGraph], u, v, k=None) -> Dict:
    """
    Retrieve edge attributes from a graph, handling both Graph and MultiDiGraph.
    """
    if graph.is_multigraph():
        if k is None and u != v:
            raise ValueError("cannot get edge attribues of None key for multigraph")
        elif k is None:
            # This suggest that u == v and there is no edge (not even self loop edge)
            return None
        return graph.get_edge_data(u, v, key=k)
    else:
        return graph.get_edge_data(u, v)  # Wrap in dict to mimic MultiDiGraph structure


def get_node_from_host(
    host: Union[nx.DiGraph, nx.MultiDiGraph], entity_name, entity_attribute=None,
):
    data = host.nodes[entity_name]
    # We are looking for a node mapping in the target graph:
    if entity_attribute:
        # Get the correct entity from the target host graph,
        # and then return the attribute:
        return data.get(entity_attribute, None)
    return data


def get_edge_from_host(
    host: Union[nx.DiGraph, nx.MultiDiGraph],
    entity_name: list[EdgeWithKey],
    entity_attribute=None
) -> Union[list[dict], dict, Any]:
    """
    Retrieve edge data from a host graph given a list of `EdgeWithKey` objects.

    Parameters
    ----------
    host : nx.DiGraph or nx.MultiDiGraph
        The graph from which to fetch edge attributes.

    entity_name : list[EdgeWithKey]
        A list of edges (u, v, k, hop_count) that identify edges in the host graph.

    entity_attribute : str, optional
        If provided, return only this attribute from the edge data.
        If multiple edges exist, this only works when the returned result is a single dict.
        Otherwise raises TypeError.

    Returns
    -------
    list[dict] | dict | Any
        Case breakdown:
        - If no edges found → `[]`
        - If exactly one edge found:
            - If no `entity_attribute` → the edge's attribute dict
            - If `entity_attribute` provided → value of that attribute or None
        - If multiple edges found:
            - If no `entity_attribute` → list of attribute dicts
            - If `entity_attribute` provided → TypeError

    Raises
    ------
    TypeError
        If `entity_attribute` is requested but multiple edges are returned.

    Notes
    -----
    Internally relies on `_get_edge_attributes(host, u, v, k)` to fetch data.
    """

    edge_data: list[dict[dict]] = (
        _get_edge_attributes(host, e.u, e.v, e.k) for e in entity_name)
    edge_data = [d for d in edge_data if d is not None]
    if not edge_data:
        return []
    if len(edge_data) == 1:
        edge_data = edge_data[0]

    if entity_attribute:
        if isinstance(edge_data, dict):
            return edge_data.get(entity_attribute)
        raise TypeError("cannot access attribute in list")

    else:
        return edge_data


def find_multiedge_keys(
    target_graph: Union[nx.DiGraph, nx.MultiDiGraph],
    match: NodeMapping,
    edge_hop_map: HopAssignment
):
    """
    Determine which edge keys exist in a host graph for each hop in each HopSpec.

    For each HopSpec inside `edge_hop_map`, this function inspects its hop path
    (`hop_spec.nodes`) and looks at every consecutive (u → v) pair.
    It then queries the corresponding host graph edges using the node mapping
    provided in `match`.

    Behavior differs depending on whether the host is a `MultiDiGraph`:

    - **MultiDiGraph:**
        Returns a list of available edge keys for each (u, v) pair.
        If the host graph contains no edge for that pair, returns `[-1]`.

        Example:
            host edges A→B with keys {0, 2, 5}
            → result[(A, B)] = [0, 2, 5]

    - **DiGraph:**
        Edge keys are conceptually always `None`, so:
        - If an edge exists → `[None]`
        - If not → `[-1]`

    Parameters
    ----------
    target_graph : nx.DiGraph or nx.MultiDiGraph
        The host graph in which real edges and multiedge keys are queried.

    match : NodeMapping
        A mapping from motif node names → host node names.

    edge_hop_map : HopAssignment
        A mapping {MapKey -> HopSpec}, where each HopSpec describes a hop path
        (e.g., ['A', 'x1', 'x2', 'B']).

    Returns
    -------
    dict[tuple[str, str], list[int] | list[None] | list[-1]]
        A dictionary mapping each hop (u, v) in motif coordinates to:
            - list of integer edge keys (MultiDiGraph),
            - [None] if a DiGraph edge exists,
            - [-1] if no matching edge exists in host.

    Notes
    -----
    - Using `-1` to indicate “no valid edge” allows the downstream Cartesian
      product generator to still function.
    - Keys are returned *in motif node space*, not host node space.
    """
    result = {}
    for hop_spec in edge_hop_map.values():
        if not hop_spec:
            continue
        edge_paths = hop_spec.nodes

        if isinstance(target_graph, nx.MultiDiGraph):
            for i in range(len(edge_paths)-1):
                start = edge_paths[i]
                end = edge_paths[i+1]
                if hop_spec.hop_count == 0:
                    result[(start, end)] = [-1]
                else:
                    result[(start, end)] = target_graph.get_edge_data(match[start], match[end])
                    result[(start, end)] = list(result[(start, end)].keys()) if result[(start, end)] is not None else [-1]
        else:
            for i in range(len(edge_paths)-1):
                start = edge_paths[i]
                end = edge_paths[i+1]
                if hop_spec.hop_count == 0:
                    result[(start, end)] = [-1]
                else:
                    result[(start, end)] = target_graph.get_edge_data(match[start], match[end])
                    result[(start, end)] = [None] if result[(start, end)] is not None else [-1]
    return result


def generate_multiedge_edge_hop_key(
    edge_hop_map: HopAssignment,
    multi_edge_keys: Dict[tuple[str, str], Optional[int]]
) -> Generator[list[EdgeHopKey], None, None]:
    """
    Generate all possible combinations of edge-hop key assignments across all
    motif edges that may expand into multi-hop paths.

    This function uses the output from `find_multiedge_keys` (a mapping of
    (u, v) → list of edge keys) and computes the Cartesian product of all
    possible key selections, per HopSpec, across all motif edges.

    It yields **one complete assignment at a time**, where each assignment is
    represented as a list of `EdgeHopKey` objects—one per motif edge.

    Example
    -------
    Suppose a motif edge A→B expands into two hops (A→x, x→B) and the host
    MultiDiGraph has keys:
        (A, x): [0, 1]
        (x, B): [5]
    Then the resulting combinations are:
        - keys=(0, 5)
        - keys=(1, 5)

    If a hop has no valid edge (`[-1]`), its corresponding EdgeHopKey will have
    an **empty tuple** (i.e., no key assignment): `keys=tuple()`.

    Parameters
    ----------
    edge_hop_map : HopAssignment
        A mapping {MapKey -> HopSpec}, describing the node paths for each
        motif edge.

    multi_edge_keys : dict[(str, str), list[int] | list[None] | list[-1]]
        Output of `find_multiedge_keys`.
        Maps each hop (u, v) in motif coordinates → possible edge keys.

    Yields
    ------
    list[EdgeHopKey]
        One full multi-edge hop-key assignment.
        The list is ordered by the iteration order of `edge_hop_map`.

    Notes
    -----
    - `-1` entries (meaning “no valid edge”) are converted into an empty
      `tuple()` so the calling code can detect hop failure explicitly.
    - The Cartesian product is computed in two layers:
        1. For each HopSpec (per motif edge): keys across hops.
        2. Across all HopSpecs: product of all per-edge sequences.
    - This generator lazily produces combinations without storing them all,
      making it scalable for large products.
    """
    result: list[list[EdgeHopKey]] = []

    for key, hop_spec in edge_hop_map.items():
        edge_paths = hop_spec.nodes
        edge_path_keys = []
        for i in range(len(edge_paths)-1):
            start = edge_paths[i]
            end = edge_paths[i+1]
            edge_path_keys.append(
                multi_edge_keys[(start, end)]
            )
        result.append(product(*edge_path_keys))

    for row in product(*result):
        ret = []
        for key, val in zip(edge_hop_map.keys(), row):
            ret.append(
                EdgeHopKey(
                    edge_id=key,
                    keys=val if val[0] != -1 else tuple()
                )
            )
        yield ret


CONDITION = Callable[[dict, nx.DiGraph, list], bool]


class Condition:
    ...

class BoolCondition(Condition):
    ...


class AND(BoolCondition):
    def __init__(self, condition_a: CONDITION, condition_b: CONDITION):
        self._condition_a = condition_a
        self._condition_b = condition_b
        self._operator = "and"

    def __call__(self, match: dict, host: nx.DiGraph, return_edges: list) -> bool:
        condition_a, where_a = self._condition_a(match, host, return_edges)
        condition_b, where_b = self._condition_b(match, host, return_edges)
        where_result = [a and b for a, b in zip(where_a, where_b)]
        return (condition_a and condition_b), where_result


class OR(BoolCondition):
    def __init__(self, condition_a: CONDITION, condition_b: CONDITION):
        self._condition_a = condition_a
        self._condition_b = condition_b
        self._operator = "or"

    def __call__(self, match: dict, host: nx.DiGraph, return_edges: list) -> tuple[bool, dict]:
        condition_a, where_a = self._condition_a(match, host, return_edges)
        condition_b, where_b = self._condition_b(match, host, return_edges)
        where_result = [a or b for a, b in zip(where_a, where_b)]
        return (condition_a or condition_b), where_result


class CompareCondition(Condition):
    ...


class LambdaCompareCondition(CompareCondition):
    def __init__(self, operator_function: Callable[[Any, Any], bool], operator: str):
        self._operator_function = operator_function
        self._operator = operator

    def __call__(self, value1, value2):
        return self._operator_function(value1, value2)

    def __str__(self) -> str:
        return f"{self._operator!r} condition at: " + super().__str__()


class CompoundCondition(Condition):
    """compound condition"""
    def __init__(self, should_be: bool, left, operator, right):
        self._should_be = should_be
        self._left = left
        self._operator = operator
        self._right = right

    def __str__(self):
        return f"compound of {self._operator} for {self._left}: {self._right}"

    def __call__(self, match: Match, host: nx.DiGraph, return_edges: list) -> bool:
        if isinstance(self._operator, SUBOP):
            val = self._operator(match.node_mappings, self._right)
        else:
            left = _resolve_operand(self._left, match, host, return_edges)
            right = _resolve_operand(self._right, match, host, return_edges)
            try:
                val = self._operator(left, right)
            except (TypeError, AttributeError):
                val = False
        operator_results = [val]
        if val is None:
            val = False
        if val != self._should_be:
            return False, operator_results
        return True, operator_results


def none_wrapper(func) -> Callable[[Any, Any], Union[bool, None]]:
    def inner(x, y) -> Union[bool, None]:
        try:
            return func(x, y)
        except TypeError:
            return None
    return inner


_OPERATORS = {
    "=": LambdaCompareCondition(none_wrapper(lambda x, y: x == y), "="),
    "==": LambdaCompareCondition(none_wrapper(lambda x, y: x == y), "=="),
    ">=": LambdaCompareCondition(none_wrapper(lambda x, y: x >= y), ">="),
    "<=": LambdaCompareCondition(none_wrapper(lambda x, y: x <= y), "<="),
    "<": LambdaCompareCondition(none_wrapper(lambda x, y: x < y), "<"),
    ">": LambdaCompareCondition(none_wrapper(lambda x, y: x > y), ">"),
    "!=": LambdaCompareCondition(none_wrapper(lambda x, y: x != y), "!="),
    "<>": LambdaCompareCondition(none_wrapper(lambda x, y: x != y), "<>"),
    "in": LambdaCompareCondition(lambda x, y: x in y, "in"),
    "contains": LambdaCompareCondition(lambda x, y: y in x, "contains"),
    "is": LambdaCompareCondition(lambda x, y: x is y, "is"),
    "starts_with": LambdaCompareCondition(lambda x, y: x.startswith(y), "starts_with"),
    "ends_with": LambdaCompareCondition(lambda x, y: x.endswith(y), "ends_with"),
}


_BOOL_ARI = {
    "and": AND,
    "or": OR,
}


def _data_path_to_entity_name_attribute(data_path):
    if isinstance(data_path, IDRef):
        return data_path.entity_name, None
    if isinstance(data_path, AttributeRef):
        return data_path.entity_name, data_path.attribute
    if isinstance(data_path, EntityRef):
        return data_path.entity_name, None
    if isinstance(data_path, Token):
        data_path = data_path.value
    if "." in data_path:
        entity_name, entity_attribute = data_path.split(".")
    else:
        entity_name = data_path
        entity_attribute = None
    return entity_name, entity_attribute


# this is to convert WHERE OPERATOR to INDEXER OPERATOR
WHERE_OPERATORS_TO_INDEXER_OPERATORS = {
    "=": "==",
    "==": "==",
    ">": ">",
    ">=": ">=",
    "<": "<",
    "<=": "<=",
}


# this is to conver WHERE NOT OPERATOR to INDEXER OPERATOR
NOT_WHERE_OPERATORS_TO_INDEXER_OPERATORS = {
    "=": "!=",
    "==": "!=",
    ">": "<=",
    ">=": "<",
    "<": ">=",
    "<=": ">",
}


def create_node_indexer(target_graph: nx.DiGraph) -> ArrayAttributeIndexer:
    """create indexer for graph nodes"""
    indexer = ArrayAttributeIndexer(
        entity_ids=list(target_graph.nodes()),
        entity_attributes=list(target_graph.nodes[n] for n in target_graph.nodes))
    return indexer


def to_indexer_ast(condition: Condition, left = None, right = None, should_be=True) -> IndexerConditionAST:
    """convert where condition to IndexerConditionAST which can be run with IndexerConditionRunner"""
    if isinstance(condition, CompoundCondition):
        return to_indexer_ast(condition=condition._operator,
                                left=condition._left,
                                right=condition._right,
                                should_be=condition._should_be)
    if (isinstance(condition, LambdaCompareCondition) and
        condition._operator in WHERE_OPERATORS_TO_INDEXER_OPERATORS and
        isinstance(left, AttributeRef) and
        isinstance(right, (int, float, str, bool, type(None)))):
        operator = condition._operator
        if should_be is True:
            operator = WHERE_OPERATORS_TO_INDEXER_OPERATORS[operator]
        else:
            operator = NOT_WHERE_OPERATORS_TO_INDEXER_OPERATORS[operator]
        return IndexerCompare(operator, left, right)
    if (isinstance(condition, LambdaCompareCondition) and
        condition._operator == "==" and
        should_be is True and
        isinstance(left, IDRef) and
        isinstance(right, (int, float, str, bool))):
        return IndexerCompare("==", left, right)
    if isinstance(condition, OR):
        return IndexerOr(
            to_indexer_ast(condition._condition_a, left, right),
            to_indexer_ast(condition._condition_b, left, right),
        )
    if isinstance(condition, AND):
        return IndexerAnd(
            to_indexer_ast(condition._condition_a, left, right),
            to_indexer_ast(condition._condition_b, left, right),
        )
    return IndexerUnsupportedOp(condition, left, right)


def motif_to_indexer_ast(motif: nx.DiGraph) -> IndexerConditionAST:
    # TODO: Test
    ast = None
    for cname, json_data in motif.nodes(data=True):
        for k, v in json_data.items():
            if k == "__labels__":
                continue
            k = AttributeRef(cname, k)
            if ast is None:
                ast = IndexerCompare("==", k, v)
            else:
                ast = IndexerAnd(
                    ast,
                    IndexerCompare("==", k, v)
                )
    return ast


class GrandCypherExecutor:
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
        self._hints: Optional[List[HintType]] = None
        self._parent_executor: Optional["GrandCypherExecutor"] = None
        self._child_executors: list["GrandCypherExecutor"] = []
        # tell the executor not to check the return values
        self.run_without_return = False
        # level of subquery
        self._level = 0
        # tell the engine to double check hint related nodes and edges structure
        # as they are ignored in grandiso
        self._doublecheck_hint_result = False
        # whether auto_where_hints should be generated
        self._auto_where_hints = True
        # EXPERIEMENT feature
        self._auto_node_jsondata_hints = True
        node_ids = list(self._target_graph.nodes)
        # EXPERIMENT feature. Array Indexer doesn't update data when nodes in graph are updated.
        self._node_indexer = ArrayAttributeIndexer(
            entity_ids=node_ids,
            entity_attributes=[self._target_graph.nodes[nid] for nid in node_ids]
        )

    def create_node_indices(self, node_attribute_keys: list[str]):
        self._node_indexer.create_indices(node_attribute_keys)

    def set_hints(self, hints=None):
        self._hints = hints
        return self

    def clear_matches(self):
        self._matches = None

    def _lookup(self, data_paths: List[str], offset_limit) -> Dict[str, List]:

        if not data_paths and not self.run_without_return:
            return {}

        motif_nodes = self._motif.nodes()

        # Get true matches FIRST, before processing data paths
        true_matches = self._get_true_matches()
        result = {}
        processed_paths = set()  # Keep track of processed paths

        # handling RETURN ID(A)
        for data_path in data_paths:
            if isinstance(data_path, IDRef):
                original_entity = data_path.entity_name
                if original_entity in motif_nodes:
                    ret = [match.mth.node(original_entity) for match in true_matches]
                    result[data_path] = ret[offset_limit]
                    result[original_entity] = ret[offset_limit]
                    processed_paths.add(data_path)
                    processed_paths.add(original_entity)
                    continue
            else:
                entity_name, _ = _data_path_to_entity_name_attribute(data_path)
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
                        self._target_graph.nodes[match.mth.node(entity_name)].get(
                            entity_attribute, None
                        )
                        for match in true_matches
                    )
                else:
                    # Return the full node dictionary with all attributes
                    ret = (
                        self._target_graph.nodes[match.mth.node(entity_name)]
                        for match in true_matches
                    )

            elif entity_name in self._paths:
                ret = []
                # for mapping, _, _ in true_matches:
                    # mapping = mapping[0]
                for match in true_matches:
                    mapping = match.node_mappings
                    path, nodes = [], list(mapping.values())
                    for x, node in enumerate(nodes):
                        # Edge
                        # TODO: this edge getting might not be correct in the case of MultiGraph
                        if x > 0:
                            path.append(
                                self._target_graph.get_edge_data(nodes[x - 1], node)
                            )

                        # Node
                        path.append(node)

                    ret.append(path)

            else:
                edge_mapping = self._return_edges[entity_name]
                # We are looking for an edge mapping in the target graph:
                ret = []
                for match in true_matches:
                    host_edges = match.mth.edge(*edge_mapping).edges
                    ret.append(
                        get_edge_from_host(
                            self._target_graph,
                            host_edges,
                            entity_attribute,
                        )
                    )

            result[data_path] = list(ret)[offset_limit]
        return result

    def _format_aggregation_key(self, func, entity):
        return f"{func}({entity})"

    def aggregate(self, func, results, entity, group_keys):
        # Collect data based on group keys
        grouped_data = {}
        for i in range(len(results[entity])):
            group_tuple = tuple(results[key][i] for key in group_keys if key in results)
            if group_tuple not in grouped_data:
                grouped_data[group_tuple] = []
            grouped_data[group_tuple].append(results[entity][i])


        def _collate_data(data, func):
            # for ["COUNT", "SUM", "AVG"], we treat None as 0
            if func in ["COUNT", "SUM", "AVG"]:
                collated_data = [
                    # label: [
                    (v or 0)
                    for v in data
                ]
            elif func in ["MAX", "MIN"]:
                collated_data = [
                    v
                    for v in data
                ]


            return collated_data

        # Apply aggregation function
        aggregate_results = {}
        for group, data in grouped_data.items():
            collated_data = _collate_data(data, func)
            if func == "COUNT":
                aggregate_results[group] = len(collated_data)
            elif func == "SUM":
                aggregate_results[group] = sum(collated_data)
            elif func == "AVG":
                aggregate_results[group] = sum(collated_data) / len(collated_data)
            elif func == "MAX":
                aggregate_results[group] = max([(d if d is not None else -float("inf")) for d in collated_data])
            elif func == "MIN":
                aggregate_results[group] = min([(d if d is not None else float("inf")) for d in collated_data ])
        # aggregate_results = [v for v in aggregate_results.values()]
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
                aggregated_values = list(aggregated_data.values())
                aggregated_keys = list(aggregated_data.keys())
                func_key = self._format_aggregation_key(func, entity)
                aggregated_results[func_key] = aggregated_values
                self._return_requests.append(func_key)
                # TODO: the group_keys is the same for all func
                # let's have aggregated keys 1st
                # then have aggregated values
                # so we don't have to repeat the groups key population here
                # for i in range(len(gro up_keys)):
                #     results[group_keys[i]] = [k[i] for k in aggregated_keys]
            results.update(aggregated_results)
            for i in range(len(group_keys)):
                results[group_keys[i]] = [k[i] for k in aggregated_keys]

        # update the results with the given alias(es)
        results = {self._entity2alias.get(k, k): v for k, v in results.items()}

        if self._order_by:
            results = self._apply_order_by(results)

        # Apply DISTINCT before pagination
        if self._distinct:
            results = self._apply_distinct(results)

        # Only after all other transformations, apply pagination
        results = self._apply_pagination(results, ignore_limit)
        self._return_requests = [
            r if isinstance(r, (EntityRef, AttributeRef, IDRef)) else str(r)
            for r in self._return_requests
        ]

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
                            key=lambda i: float("inf") if sort_list[i] is None else sort_list[i],
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

    def _get_true_matches(self) -> tuple[Match]:
        """Get the true matches after applying WHERE conditions and hints.
        Returns the matches along with their paths.

        Returns:
            List of tuples containing (match, path)
        """
        if not self._matches:
            self_matches = []
            complete = False

            for my_motif, edge_hop_map, alias in self._edge_hop_motifs(self._motif):
                # Iteration is complete
                if complete:
                    break

                # alias is provided - no need to rebuild UnionFind
                zero_hop_nodes = set(
                    chain.from_iterable(hs.edge_id for hs in edge_hop_map.values() if hs.hop_count == 0))

                matches = self._matches_iter(my_motif)

                # Collect all valid matches before applying pagination
                for match in matches:
                    match = Match(
                        node_mappings=match,
                        where_results=None,
                        edge_mapping=None
                    )
                    # Handle zero hop nodes
                    # In zero edge hop edges, we check if the node are actually the collapsed node
                    valid_match = True
                    for u1 in zero_hop_nodes:
                        # take out the collapsed to node
                        u2 = alias[u1]
                        if not _is_node_attr_match(
                            u1, match.mth.node(u2), self._motif, self._target_graph
                        ):
                            valid_match = False
                            break
                        # the match might not contain the mapping for the un-collapsed node, let's put it in
                        match.node_mappings[u1] = match.node_mappings[u2]

                    if not valid_match:
                        continue
                    multi_edge_keys = find_multiedge_keys(self._target_graph, match.node_mappings, edge_hop_map)
                    for edge_key_mapping in generate_multiedge_edge_hop_key(edge_hop_map, multi_edge_keys):
                        edge_mapping = EdgeMapping(
                            edge_hop_map=edge_hop_map,
                            edge_key_map={e.edge_id: e for e in edge_key_mapping}
                        )
                        edges = chain.from_iterable(edge_path.edges for edge_path in edge_mapping.edge_paths)

                        # DOUBLE CHECK EDGE
                        # =================================================
                        # CASE1 multigraph
                        # Since the match_iter grandiso doesn't return the proper edge key for multigraph
                        # we need to double check them here to make sure matches correct
                        # For example, consider this test case
                        # host = nx.MultiDiGraph()
                        # host.add_node("a", name="Alice", age=30)
                        # host.add_node("b", name="Bob", age=40)
                        # host.add_node("c", name="Charlie", age=50)
                        # host.add_edge("a", "b", __labels__={"friend"}, years=3)
                        # host.add_edge("a", "c", __labels__={"colleague"}, years=10)
                        # host.add_edge("b", "c", __labels__={"colleague"}, duration=10)
                        # host.add_edge("b", "c", __labels__={"mentor"}, years=2)
                        # qry = """
                        # MATCH (a)-[r:colleague]->(b)
                        # RETURN a.name, b.name, r.duration
                        # """
                        # there are two edge between b and c, with label colleague and mentor
                        # the mentor should be rejected here
                        # ================================================
                        # CASE 2: equijoin
                        # The grandiso doesn't check when we explicitly do the equijoin
                        # G = nx.DiGraph()
                        # G.add_node("x")
                        # G.add_node("y")
                        # G.add_node("z")
                        # G.add_edge("x", "y")
                        # G.add_edge("y", "x")
                        # G.add_edge("x", "x")
                        # G.add_edge("z", "x")
                        # qry = """
                        # MATCH (n)-->(n)
                        # RETURN ID(n)
                        # """
                        # Grandiso return both x and y, but only x is correct, y is not
                        valid_match = True
                        for edge in edges:
                            # SKIP if hop = 0, there is no edge
                            if edge.h == 0:
                                continue
                            motif_u, motif_v = edge.u, edge.v
                            motif_u, motif_v = alias.get(motif_u, motif_u), alias.get(motif_v, motif_v)
                            host_u, host_v = match.mth.node(motif_u), match.mth.node(motif_v)
                            # skip if there is 1 edge between 2 nodes and they are different (not equijoin)
                            if edge.u != edge.v and self._target_graph.number_of_edges(host_u, host_v) < 2:
                                continue
                            host_keys = (edge.k,) if edge.k is not None else tuple()
                            if not _is_edge_attr_match(motif_edge_id=(motif_u, motif_v),
                                                        host_edge_id=(host_u, host_v),
                                                        motif=my_motif,
                                                        host=self._target_graph,
                                                        host_keys=host_keys):
                                valid_match = False
                                break
                        if not valid_match:
                            continue

                        match = Match(
                            node_mappings=match.node_mappings,
                            where_results=None,
                            edge_mapping=edge_mapping
                        )

                        # Apply WHERE condition if present
                        if self._where_condition:
                            satisfies_where, where_results = self._where_condition(
                                match, self._target_graph, self._return_edges
                            )
                            if not satisfies_where:
                                continue
                        else:
                            where_results = []
                        match.where_results = where_results
                        self_matches.append(match)

                        # Check if limit reached; stop ONLY IF we are not ordering
                        if self._is_limit(len(self_matches)) and not self._order_by:
                            complete = True
                            break

                    if complete:
                        break

            self._matches = tuple(self_matches)

        return self._matches

    def _matches_iter(self, motif):
        hinter = Hinter(_is_node_attr_match, _is_edge_attr_match)
        if self._hints:
            hints = self._hints
        elif self._auto_where_hints or self._auto_node_jsondata_hints:
            indexer = self._node_indexer
            condition_asts = []
            if self._auto_node_jsondata_hints and hasattr(self._target_graph, "pred"):
                condition_asts.append(motif_to_indexer_ast(self._motif))
            if self._auto_where_hints:
                condition_asts.append(to_indexer_ast(self._where_condition))

            ast = condition_asts[0]
            for c_ast in condition_asts:
                if c_ast is None:
                    continue
                if ast is None:
                    ast = c_ast
                else:
                    ast = IndexerAnd(ast, c_ast)

            entity_domain = IndexerConditionRunner(indexer=indexer).find(ast)
            hints = hinter.index_domain_to_hints(entity_domain)
        else:
            hints = []

        # Get list of all match iterators
        iterators = []
        for c in nx.weakly_connected_components(motif):

            c_motif = motif.subgraph(c)
            # NOTE: making sure only giving hints to "relevant" nodes.
            c_hints = hinter.take_hints_with_keys(hints, c)
            if self._auto_where_hints:
                c_hints = hinter.eliminate_supersets(c_hints)
            grandiso_finder = grandiso.find_motifs_iter(
                c_motif,
                self._target_graph,
                # is_node_structural_match=_is_node_structural_match,
                is_node_attr_match=_is_node_attr_match,
                is_edge_attr_match=_is_edge_attr_match,
                # Giving wrong hint will cause error
                hints=c_hints ,
            )
            iterators.append((grandiso_finder, c_motif, c_hints))
        # Single match clause iterator
        if iterators and len(iterators) == 1:
            grandiso_finder, c_motif, c_hints = iterators[0]
            for match in grandiso_finder:
                # as hints are not checked against node and edge match in grandiso
                # let's do double check here
                if c_hints and not hinter.doublecheck(
                    host=self._target_graph,
                    motif=c_motif,
                    match=match,
                    hints=c_hints):
                    continue
                yield match
        else:
            iterations, matches = 0, {}
            for x, iterator in enumerate(iterators):
                grandiso_finder, c_motif, c_hints = iterator
                for match in grandiso_finder:
                    if self._doublecheck_hint_result and not hinter.doublecheck(
                        host=self._target_graph,
                        motif=c_motif,
                        match=match,
                        hints=c_hints):
                        continue
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

    def _edge_hop_motifs(self, motif: nx.MultiDiGraph) -> Generator[Tuple[nx.Graph, HopAssignment, dict], None, None]:
        """Generate edge-hop-expanded motifs with node unification.

        Arguments:
            motif (nx.Graph): The motif graph

        Yields:
            Tuple[nx.Graph, HopAssignment, dict]:
                - my_motif: Unified and materialized motif
                - edge_hop_map: Original hop assignment (unchanged)
                - alias: Mapping from original nodes to representatives
        """
        hop_specs = generate_edge_hop_specs(motif)
        hop_assignments = list(generate_hop_assignments(hop_specs))

        for hop_assignment in hop_assignments:
            # Step 1: Materialize (without unification)
            materialized_motif = materialize_motif(hop_assignment, motif)

            # Step 2: Unify zero-hop nodes and get alias
            my_motif, alias = unify_zero_hop_nodes(materialized_motif, hop_assignment.values())

            # Step 3: Yield unified motif, original hop_assignment, and alias
            yield my_motif, hop_assignment, alias

    def _is_limit(self, length):
        """Check if the current number of results has reached the limit.

        Args:
            length: The current number of results.

        Returns:
            True if we've reached the limit, False otherwise.
        """
        return self._limit is not None and length >= (self._limit + self._skip)


class GrandCypherTransformer(Transformer):
    def __init__(self, target_graph: nx.Graph, limit: Optional[int] = None):
        self._limit = limit
        self._target_graph = target_graph
        self._executors = [GrandCypherExecutor(target_graph, limit)]
        self._match_clause_count = 0

    def return_clause(self, clause):
        # collect all entity identifiers to be returned

        for item in clause:
            if item:
                alias = self._extract_alias(item)
                item = item.children[0] if isinstance(item, Tree) else item
                if isinstance(item, Tree) and item.data == "aggregation_function":
                    func, entity = self._parse_aggregation_token(item)
                    if alias:
                        self._executors[-1]._entity2alias[
                            self._executors[-1]._format_aggregation_key(func, entity)
                        ] = alias
                    self._executors[-1]._aggregation_attributes.add(entity)
                    self._executors[-1]._aggregate_functions.append((func, entity))
                else:
                    if not isinstance(item, str):
                        item = str(item.value)
                    self._executors[-1]._original_return_requests.add(item)

                    if alias:
                        self._executors[-1]._entity2alias[item] = alias
                    self._executors[-1]._return_requests.append(item)

        self._executors[-1]._alias2entity.update({v: k for k, v in self._executors[-1]._entity2alias.items()})

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

    def set_hints(self, hints=None):
        # self._hints = hints
        self._executors[-1].set_hints(hints)
        return self

    def transform(self, tree, hints=None):
        self.set_hints(hints)
        return super().transform(tree)

    def order_clause(self, order_clause):
        self._executors[-1]._order_by = []
        for item in order_clause[0].children:
            if (
                isinstance(item.children[0], Tree)
                and item.children[0].data == "aggregation_function"
            ):
                func, entity = self._parse_aggregation_token(item.children[0])
                field = self._executors[-1]._format_aggregation_key(func, entity)
                self._executors[-1]._order_by_attributes.add(entity)
            else:
                field = str(
                    item.children[0]
                )  # assuming the field name is the first child
                self._executors[-1]._order_by_attributes.add(field)

            # Default to 'ASC' if not specified
            if len(item.children) > 1 and str(item.children[1].data).lower() != "desc":
                direction = "ASC"
            else:
                direction = "DESC"

            self._executors[-1]._order_by.append((field, direction))  # [('n.age', 'DESC'), ...]

    def distinct_return(self, distinct):
        self._executors[-1]._distinct = True

    def limit_clause(self, limit):
        limit = int(limit[-1])
        self._executors[-1]._limit = limit

    def skip_clause(self, skip):
        skip = int(skip[-1])
        self._executors[-1]._skip = skip

    def entity_id(self, entity_id):
        if len(entity_id) == 2:
            return AttributeRef(entity_id[0], entity_id[1])
        return EntityRef(entity_id[0].value)

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
        cname = node_types = json_data = None
        for item in node_name:
            if not isinstance(item,Tree):
                if not isinstance(item, Token):
                    json_data = item
                elif item.type == "CNAME":
                    cname = item
                elif item.type == "TYPE":
                    node_types = set([item.value])
            elif isinstance(item,Tree):
                if item.data.value =='type_list':
                    node_types=set([token.value for token in item.children])
        cname = cname or Token("CNAME", shortuuid())
        json_data = json_data or {}
        node_types = node_types if node_types else set()

        return (cname, node_types, json_data)

    def many_match_clause(self, many_match_clause):
        self._match_clause_count += 1
        return self

    def match_clause(self, match_clause: Tuple): # construct the motif
        if self._match_clause_count == len(self._executors):
            subquery_executor = GrandCypherExecutor(self._target_graph, self._limit)
            parent_executor = self._executors[-1]
            subquery_executor._parent_executor = parent_executor
            subquery_executor._level = parent_executor._level + 1
            self._executors[-1]._child_executors.append(subquery_executor)
            self._executors.append(subquery_executor)

        if len(match_clause) == 1:
            # This is just a node match:
            u, ut, js = match_clause[0]
            self._executors[-1]._motif.add_node(u.value, __labels__=ut, **js)
            return

        match_clause = match_clause[1:] if not match_clause[0] else match_clause
        for start in range(0, len(match_clause) - 2, 2):
            # u/v (token) - representing variable name of node
            # ut/vt (set) - representing labels
            # ujs/vjs (dict) - representing json rules
            # g (token) - representing variable name of relation
            # t (set) - representing relation labels (types)
            # d (str) - representing direction: r,l,b
            # minh/maxh (int) - min/max hops
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
                self._executors[-1]._return_edges[g.value] = edges[0]

            ish = minh is None and maxh is None
            minh = minh if minh is not None else 1
            maxh = maxh if maxh is not None else minh + 1
            if maxh > self._executors[-1]._max_hop:
                raise ValueError(f"max hop is caped at 100, found {maxh}!")
            if t:
                t = set([t] if type(t) is str else t)
            self._executors[-1]._motif.add_edges_from(
                edges, __min_hop__=minh, __max_hop__=maxh, __is_hop__=ish, __labels__=t
            )

            self._executors[-1]._motif.add_node(u, __labels__=ut, **ujs)
            self._executors[-1]._motif.add_node(v, __labels__=vt, **vjs)

    def path_clause(self, path_clause: tuple):
        self._executors[-1]._paths.append(path_clause[0])
        return

    def where_clause(self, where_clause: tuple):
        self._executors[-1]._where_condition = where_clause[0]

    def compound_condition(self, val):
        if len(val) == 1:
            val = CompoundCondition(*val[0])
        else:  # len == 3
            compound_a, operator, compound_b = val
            val = operator(compound_a, compound_b)
        return val

    def where_and(self, val):
        return _BOOL_ARI["and"]

    def where_or(self, val):
        return _BOOL_ARI["or"]

    def condition(self, condition):
        if len(condition) == 1:  # sub query
            condition = condition[0]

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
        return IDRef(entity_name)

    def value_list(self, items):
        return list(items)

    def op(self, operator):
        return operator

    def arith_add(self, items):
        return ArithmeticExpression(items[0], "+", items[1])

    def arith_sub(self, items):
        return ArithmeticExpression(items[0], "-", items[1])

    def arith_mul(self, items):
        return ArithmeticExpression(items[0], "*", items[1])

    def arith_div(self, items):
        return ArithmeticExpression(items[0], "/", items[1])

    def arith_mod(self, items):
        return ArithmeticExpression(items[0], "%", items[1])

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

    def subop_exist(self, val):
        return _SUB_OPERATORS["EXISTS"]()

    def sub_query(self, items):
        executor = self._executors.pop()
        self._match_clause_count -= 1
        # return entity_id = "" to match with other condition
        return ["", items[0], executor]

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

        self._transformer = GrandCypherTransformer(host_graph, limit)
        self._host_graph = host_graph

    @property
    def auto_node_jsondata_hints(self):
        return self._transformer._executors[0]._auto_node_jsondata_hints

    @auto_node_jsondata_hints.setter
    def auto_node_jsondata_hints(self, val: bool):
        """(EXPERIMENT) set auto hint"""
        self._transformer._executors[0]._auto_node_jsondata_hints = val

    @property
    def auto_where_hints(self):
        return self._transformer._executors[0]._auto_where_hints

    @auto_where_hints.setter
    def auto_where_hints(self, val: bool):
        """(EXPERIMENT) set auto hint"""
        self._transformer._executors[0]._auto_where_hints = val

    def create_node_indices(self, keys: list[str]) -> "GrandCypher":
        """(EXPERIMENT) create node indices by keys
        Arguments:
            keys (list[str]): list of node keys to make indexes
        Returns:
            GrandCypher: The self GrandCypher
        """
        self._transformer._executors[0].create_node_indices(keys)

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
        return self._transformer._executors[0].returns()
