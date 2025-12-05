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

condition           : (entity_id | scalar_function | list_predicate_function) op entity_id_or_value
                    | (entity_id | scalar_function | list_predicate_function) op_list value_list
                    | list_predicate_function
                    | sub_query
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

sub_op              : "EXISTS" -> subop_exist

sub_query           : sub_op "{" sub_query_body "}"

sub_query_body      : many_match_clause where_clause? return_clause?


op_list             : "in"i -> op_in



return_clause       : "return"i distinct_return? return_item ("," return_item)*
return_item         : (entity_id | aggregation_function | scalar_function | entity_id "." attribute_id) ( "AS"i alias )?
alias               : CNAME

aggregation_function : AGGREGATE_FUNC "(" entity_id ( "." attribute_id )? ")"
AGGREGATE_FUNC       : "COUNT" | "SUM" | "AVG" | "MAX" | "MIN" | "COLLECT"
attribute_id         : CNAME

scalar_function      : "id"i "(" entity_id ")" -> id_function
                     | "size"i "(" list_expression ")" -> size_function
                     | "tolower"i "(" scalar_func_arg ")" -> tolower_function
                     | "toupper"i "(" scalar_func_arg ")" -> toupper_function
                     | "trim"i "(" scalar_func_arg ")" -> trim_function
                     | "type"i "(" entity_id ")" -> type_function
                     | "coalesce"i "(" coalesce_args ")" -> coalesce_function

scalar_func_arg      : scalar_function
                     | entity_id ("." attribute_id)?

coalesce_args        : coalesce_arg ("," coalesce_arg)*
coalesce_arg         : value
                     | entity_id ("." attribute_id)?

list_predicate_function : "all"i "(" CNAME "in"i list_expression "where"i compound_condition ")"  -> all_function
                        | "any"i "(" CNAME "in"i list_expression "where"i compound_condition ")"  -> any_function
                        | "none"i "(" CNAME "in"i list_expression "where"i compound_condition ")"  -> none_function
                        | "single"i "(" CNAME "in"i list_expression "where"i compound_condition ")"  -> single_function

list_expression      : "relationships"i "(" entity_id ")"  -> relationships_function
                     | entity_id  -> entity_list

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


class ScalarFunction(Condition):
    """
    Base class for scalar functions that return a single value per row.

    Characteristics:
    - Return single value (not aggregate)
    - Can be used in WHERE clauses (comparison)
    - Can be used in RETURN clauses (output)
    - Evaluated once per match

    Examples: ID(), SIZE(), type(), timestamp()
    """

    def __call__(self, match: Match, host: nx.DiGraph, return_edges: list,
                 scope: Optional[dict] = None):
        """Evaluate scalar function for a single match."""
        raise NotImplementedError

    def __str__(self) -> str:
        """Return string representation for result keys."""
        raise NotImplementedError


class EntityAttributeGetter:
    """
    Wrapper to distinguish entity references from literal values.

    This class is used to represent references to graph entities and their attributes
    (e.g., n.name, n) in expressions, allowing the runtime to distinguish them from
    literal string values (e.g., "Unknown").

    Examples:
        EntityAttributeGetter("n.name") represents n.name
        EntityAttributeGetter("n") represents n
    """

    def __init__(self, expression: str):
        """
        Initialize entity attribute getter from expression string.

        Args:
            expression: The entity reference (e.g., "n", "n.name", "r.weight")
        """
        # Parse expression: "n.name" -> entity="n", attribute="name"
        if "." in expression:
            self.entity, self.attribute = expression.split(".", 1)
        else:
            self.entity = expression
            self.attribute = None

    def evaluate(self, match: Match, host: nx.DiGraph,
                 return_edges: dict = None, scope: dict = None):
        """
        Evaluate this entity reference against a match.

        Priority order for resolution:
        1. Scope variables (highest priority - for list predicates)
        2. Node mappings (standard case)
        3. Edge mappings (for edge references)
        4. None (not found)

        Args:
            match: The current match containing node mappings
            host: The graph to query
            return_edges: Optional edge mappings for edge references
            scope: Optional scope dictionary for list predicate variables

        Returns:
            The attribute value if found, None otherwise
        """
        # 1. Check scope first (highest priority for list predicates)
        if scope and self.entity in scope:
            element = scope[self.entity]
            if self.attribute:
                # Scope variable with attribute access: e.related
                return element.get(self.attribute) if isinstance(element, dict) else None
            # Simple scope variable: e
            return element

        # 2. Check node mappings (standard case)
        if self.entity in match.node_mappings:
            node_id = match.node_mappings[self.entity]
            if self.attribute:
                # Node with attribute: n.name
                return host.nodes[node_id].get(self.attribute)
            # Simple node reference: n - return full node dictionary
            return dict(host.nodes[node_id])

        # 3. Check edge mappings (for edge references)
        if return_edges and self.entity in return_edges:
            edge_mapping = return_edges[self.entity]
            host_edges = match.mth.edge(*edge_mapping).edges
            return get_edge_from_host(host, host_edges, self.attribute)

        return None

    def __str__(self) -> str:
        """String representation for debugging."""
        if self.attribute:
            return f"{self.entity}.{self.attribute}"
        return self.entity

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        if self.attribute:
            return f"EntityAttributeGetter({self.entity!r}.{self.attribute!r})"
        return f"EntityAttributeGetter({self.entity!r})"


class ID(ScalarFunction):
    """
    Implements id() scalar function.
    Returns the node ID from the host graph.

    Usage:
    - WHERE: WHERE ID(n) = 1
    - RETURN: RETURN ID(n) AS nodeId
    """

    def __init__(self, entity_name: str):
        self._entity_name = entity_name

    def __call__(self, match: Match, host: nx.DiGraph, return_edges: list,
                 scope: Optional[dict] = None):
        """Return the node ID from the match."""
        if self._entity_name in match.node_mappings:
            return match.node_mappings[self._entity_name]
        else:
            raise IndexError(f"Entity {self._entity_name} not in match.")

    def __str__(self) -> str:
        return f"ID({self._entity_name})"


class AggregationFunction(Condition):
    """
    Base class for aggregation functions that compute over multiple matches.

    Unlike ScalarFunction (per-match evaluation), AggregationFunction requires
    the full result set to compute values.

    Characteristics:
    - Requires multiple matches to evaluate
    - Needs grouping context
    - Used in RETURN and ORDER BY clauses
    - Architecture supports future WITH statements

    Examples: COUNT, SUM, AVG, MAX, MIN
    """

    def __init__(self, entity: str, entity_attribute: Optional[str] = None):
        """
        Initialize aggregation function.

        Args:
            entity: Entity name (e.g., 'r' in COUNT(r))
            entity_attribute: Optional attribute (e.g., 'value' in SUM(r.value))
        """
        self._entity = entity
        self._entity_attribute = entity_attribute

    def evaluate(self, matches: List[Match], host: nx.DiGraph,
                 return_edges: dict, group_keys: List[str], scope: dict) -> Dict[tuple, Any]:
        """
        Evaluate aggregation over all matches with grouping.

        Args:
            matches: All matches to aggregate over
            host: Target graph
            return_edges: Edge mappings
            group_keys: Entity names to group by (e.g., ["n.name"])
            scope: Pre-computed values from outer context (e.g., from _lookup)

        Returns:
            Dict mapping group_tuple -> aggregated_value
        """
        raise NotImplementedError(f"{self.__class__.__name__}.evaluate() must be implemented")

    def __str__(self) -> str:
        """String representation for result keys: COUNT(r) or SUM(r.value)"""
        entity_str = self._entity
        if self._entity_attribute:
            entity_str += f".{self._entity_attribute}"
        return f"{self.__class__.__name__}({entity_str})"

    def _group_matches(self, scope: dict, group_keys: List[str]) -> Dict[tuple, List[Any]]:
        """
        Group values and extract data for aggregation using scope.

        Uses pre-computed values from scope when available (RETURN case),
        otherwise would need fallback extraction (future WITH case).

        Args:
            scope: Pre-computed values from outer context (e.g., {"n.name": [...], "r.value": [...]})
            group_keys: Keys to group by (e.g., ["n.name"])

        Returns:
            Dict mapping group_tuple -> list of values to aggregate
        """
        # Build entity path: "r" or "r.value"
        entity_path = self._entity + ('.' + self._entity_attribute if self._entity_attribute else '')

        # Get entity values from scope (already extracted by _lookup)
        entity_values = scope.get(entity_path, [])

        # Group by group_keys (adapted from old aggregate() method)
        grouped_data = {}
        for i in range(len(entity_values)):
            # Build group tuple from scope values
            group_tuple = tuple(scope.get(key, [])[i] if i < len(scope.get(key, [])) else None
                              for key in group_keys)

            if group_tuple not in grouped_data:
                grouped_data[group_tuple] = []
            grouped_data[group_tuple].append(entity_values[i])

        return grouped_data


class COUNT(AggregationFunction):
    """
    COUNT aggregation function.
    Returns the number of non-null values.
    """

    def evaluate(self, matches: List[Match], host: nx.DiGraph,
                 return_edges: dict, group_keys: List[str], scope: dict) -> Dict[tuple, int]:
        grouped = self._group_matches(scope, group_keys)
        # COUNT only counts non-null values (filter out None)
        return {group: sum(1 for v in values if v is not None) for group, values in grouped.items()}


class SUM(AggregationFunction):
    """
    SUM aggregation function.
    Returns the sum of numeric values (None treated as 0).
    """

    def evaluate(self, matches: List[Match], host: nx.DiGraph,
                 return_edges: dict, group_keys: List[str], scope: dict) -> Dict[tuple, float]:
        grouped = self._group_matches(scope, group_keys)
        # SUM treats None as 0
        return {group: sum(v or 0 for v in values)
                for group, values in grouped.items()}


class AVG(AggregationFunction):
    """
    AVG aggregation function.
    Returns the average of numeric values (None treated as 0).
    """

    def evaluate(self, matches: List[Match], host: nx.DiGraph,
                 return_edges: dict, group_keys: List[str], scope: dict) -> Dict[tuple, float]:
        grouped = self._group_matches(scope, group_keys)
        # AVG treats None as 0
        result = {}
        for group, values in grouped.items():
            collated = [v or 0 for v in values]
            result[group] = sum(collated) / len(collated) if collated else 0
        return result


class MAX(AggregationFunction):
    """
    MAX aggregation function.
    Returns the maximum value (None treated as negative infinity).
    """

    def evaluate(self, matches: List[Match], host: nx.DiGraph,
                 return_edges: dict, group_keys: List[str], scope: dict) -> Dict[tuple, Any]:
        grouped = self._group_matches(scope, group_keys)
        # MAX treats None as -infinity
        return {group: max((d if d is not None else -float("inf")) for d in values)
                for group, values in grouped.items()}


class MIN(AggregationFunction):
    """
    MIN aggregation function.
    Returns the minimum value (None treated as positive infinity).
    """

    def evaluate(self, matches: List[Match], host: nx.DiGraph,
                 return_edges: dict, group_keys: List[str], scope: dict) -> Dict[tuple, Any]:
        grouped = self._group_matches(scope, group_keys)
        # MIN treats None as +infinity
        return {group: min((d if d is not None else float("inf")) for d in values)
                for group, values in grouped.items()}


class COLLECT(AggregationFunction):
    """
    COLLECT aggregation function.
    Collects all values into a list (like SQL's array_agg).
    """

    def evaluate(self, matches: List[Match], host: nx.DiGraph,
                 return_edges: dict, group_keys: List[str], scope: dict) -> Dict[tuple, list]:
        grouped = self._group_matches(scope, group_keys)
        # Collect all values (including None) into lists
        return {group: list(values) for group, values in grouped.items()}


class BoolCondition(Condition):
    ...


class AND(BoolCondition):
    def __init__(self, condition_a: CONDITION, condition_b: CONDITION):
        self._condition_a = condition_a
        self._condition_b = condition_b
        self._operator = "and"

    def __call__(self, match: dict, host: nx.DiGraph, return_edges: list, scope: dict = None) -> bool:
        condition_a, where_a = self._condition_a(match, host, return_edges, scope)
        condition_b, where_b = self._condition_b(match, host, return_edges, scope)
        where_result = [a and b for a, b in zip(where_a, where_b)]
        return (condition_a and condition_b), where_result


class OR(BoolCondition):
    def __init__(self, condition_a: CONDITION, condition_b: CONDITION):
        self._condition_a = condition_a
        self._condition_b = condition_b
        self._operator = "or"

    def __call__(self, match: dict, host: nx.DiGraph, return_edges: list, scope: dict = None) -> tuple[bool, dict]:
        condition_a, where_a = self._condition_a(match, host, return_edges, scope)
        condition_b, where_b = self._condition_b(match, host, return_edges, scope)
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
    def __init__(self, should_be: bool, entity_id, operator, value):
        """
        Initialize CompoundCondition.

        Args:
            should_be: Boolean expectation for the condition
            entity_id: Either a ScalarFunction or string entity reference (e.g., "n.name")
            operator: Comparison operator
            value: Value to compare against
        """
        self._should_be = should_be
        self._operator = operator
        self._value = value

        # Wrap entity references in EntityAttributeGetter at init time
        if isinstance(entity_id, ScalarFunction):
            self._entity_id = entity_id
        else:
            # Store both the original string and the getter
            self._entity_id_str = entity_id
            self._entity_id = EntityAttributeGetter(entity_id)

    def __str__(self):
        entity_repr = self._entity_id_str if hasattr(self, '_entity_id_str') else str(self._entity_id)
        return f"compound of {self._operator} for key {entity_repr}: value {self._value}"

    def __call__(self, match: Match, host: nx.DiGraph, return_edges: list, scope: dict = None) -> bool:
        # Handle scalar functions (ID, SIZE, etc.)
        if isinstance(self._entity_id, ScalarFunction):
            # Evaluate scalar function to get value
            scalar_value = self._entity_id(match, host, return_edges, scope)

            # Apply comparison operator
            val = self._operator(scalar_value, self._value)
            operator_results = [val]

            if val is None:
                val = False
            if val != self._should_be:
                return False, operator_results
            return True, operator_results

        # Handle SUBOP operators (special case - don't need entity resolution)
        if isinstance(self._operator, SUBOP):
            val = self._operator(match.node_mappings, self._value)
            operator_results = [val]
            if val is None:
                val = False
            if val != self._should_be:
                return False, operator_results
            return True, operator_results

        # Use EntityAttributeGetter for all entity references (handles scope, nodes, edges)
        entity_value = self._entity_id.evaluate(match, host, return_edges, scope)

        # Apply comparison operator
        val = self._operator(entity_value, self._value)
        operator_results = [val]

        if val is None:
            val = False
        if val != self._should_be:
            return False, operator_results
        return True, operator_results


# ==================== List Expression Classes for all()/any() ====================

class ListExpression:
    """Base class for list expressions that can reference scope."""

    def evaluate(self, match: Match, host: nx.DiGraph, return_edges: list, scope: Optional[dict] = None) -> list:
        """Evaluate to get list, possibly using scope variables."""
        raise NotImplementedError


class ScopedListExpression(ListExpression):
    """
    List expression that can reference scope variables.

    Examples:
    - 'r' → get edge list from return_edges
    - 'e.related' → get 'related' attr from scope variable 'e'
    """
    def __init__(self, expr: str):
        """
        Initialize ScopedListExpression.

        Args:
            expr: Expression string (e.g., "r", "e.related")
        """
        self._expr = expr
        # Wrap expression in EntityAttributeGetter at init time
        self._getter = EntityAttributeGetter(expr)

    def evaluate(self, match: Match, host: nx.DiGraph, return_edges: list, scope: Optional[dict] = None):
        # Use EntityAttributeGetter to resolve the value
        value = self._getter.evaluate(match, host, return_edges, scope)

        # Normalize to list
        if value is None:
            return []
        elif isinstance(value, list):
            return value
        elif isinstance(value, dict):
            return [value]
        else:
            # Scalar value - wrap in list
            return [value]


class RelationshipsFunction(ListExpression):
    """Implements relationships() function."""
    def __init__(self, path_variable: str):
        self._path_variable = path_variable

    def evaluate(self, match: Match, host: nx.DiGraph, return_edges: list, scope: Optional[dict] = None):
        # Use ScopedListExpression to handle scope references
        return ScopedListExpression(self._path_variable).evaluate(match, host, return_edges, scope)


# ==================== ALL and ANY Condition Classes ====================

class ALL(Condition):
    """
    Implements all() predicate function.

    REUSES existing Condition classes (CompoundCondition, AND, OR)!
    """
    def __init__(self, name: str, list_expr: str, pred):
        self._name = name           # Loop variable name
        self._list_expr = list_expr  # String expr or ListExpression object
        self._pred = pred           # Regular Condition (CompoundCondition, AND, OR, etc.)

    def __call__(self, match, host: nx.DiGraph, return_edges: list,
                 scope: dict = None) -> tuple[bool, list]:
        # 1. Evaluate list expression (may reference scope)
        if isinstance(self._list_expr, str):
            list_obj = ScopedListExpression(self._list_expr)
        else:
            list_obj = self._list_expr

        elements = list_obj.evaluate(match, host, return_edges, scope)

        # 2. Handle empty/null lists (Neo4j semantics)
        if elements is None:
            return None, [None]
        if not elements:
            return True, [True]  # Vacuously true

        # 3. Iterate and evaluate predicate for each element
        for element in elements:
            # Create new scope with current element
            new_scope = {**scope} if scope else {}
            new_scope[self._name] = element

            # Evaluate predicate with scope (pred is a regular Condition!)
            result, _ = self._pred(match, host, return_edges, new_scope)

            # Short-circuit on False
            if result is False:
                return False, [False]
            elif result is None:
                # Track null for Neo4j semantics
                pass

        return True, [True]


class ANY(Condition):
    """Similar structure to ALL but returns True if any element satisfies."""
    def __init__(self, name: str, list_expr: str, pred):
        self._name = name
        self._list_expr = list_expr
        self._pred = pred  # Regular Condition!

    def __call__(self, match, host, return_edges, scope=None):
        # Evaluate list
        if isinstance(self._list_expr, str):
            list_obj = ScopedListExpression(self._list_expr)
        else:
            list_obj = self._list_expr

        elements = list_obj.evaluate(match, host, return_edges, scope)

        # Handle empty/null (Neo4j semantics)
        if elements is None:
            return None, [None]
        if not elements:
            return False, [False]  # False for empty list

        # Iterate
        for element in elements:
            new_scope = {**scope} if scope else {}
            new_scope[self._name] = element

            # Evaluate predicate with scope
            result, _ = self._pred(match, host, return_edges, new_scope)

            # Short-circuit on True
            if result is True:
                return True, [True]

        return False, [False]


class NONE(Condition):
    """
    Implements none() predicate function.
    Returns true when NO elements satisfy the predicate.

    Neo4j semantics:
    - Empty list [] → True (no elements violate)
    - Null list → None
    - Short-circuits on first True (element satisfies)
    """
    def __init__(self, name: str, list_expr, pred: Condition):
        self._name = name           # Loop variable name
        self._list_expr = list_expr # String expr or ListExpression
        self._pred = pred           # Regular Condition

    def __call__(self, match: Match, host: nx.DiGraph, return_edges: list,
                 scope: Optional[dict] = None):
        # Evaluate list expression
        if isinstance(self._list_expr, str):
            list_obj = ScopedListExpression(self._list_expr)
        else:
            list_obj = self._list_expr

        elements = list_obj.evaluate(match, host, return_edges, scope)

        # Handle empty/null (Neo4j semantics)
        if elements is None:
            return None, [None]
        if not elements:
            return True, [True]  # Vacuously true (no elements violate)

        # Iterate and check for violations
        for element in elements:
            # Create new scope with current element
            new_scope = {**scope} if scope else {}
            new_scope[self._name] = element

            # Evaluate predicate with scope
            result, _ = self._pred(match, host, return_edges, new_scope)

            # Short-circuit on True (found element that satisfies)
            if result is True:
                return False, [False]  # none() fails if any element satisfies

        return True, [True]  # No elements satisfied the predicate


class SINGLE(Condition):
    """
    Implements single() predicate function.
    Returns true when EXACTLY ONE element satisfies the predicate.

    Neo4j semantics:
    - Empty list [] → False (not exactly one)
    - Null list → None
    - Cannot short-circuit (must check all elements to count)
    """
    def __init__(self, name: str, list_expr, pred: Condition):
        self._name = name           # Loop variable name
        self._list_expr = list_expr # String expr or ListExpression
        self._pred = pred           # Regular Condition

    def __call__(self, match: Match, host: nx.DiGraph, return_edges: list,
                 scope: Optional[dict] = None):
        # Evaluate list expression
        if isinstance(self._list_expr, str):
            list_obj = ScopedListExpression(self._list_expr)
        else:
            list_obj = self._list_expr

        elements = list_obj.evaluate(match, host, return_edges, scope)

        # Handle empty/null (Neo4j semantics)
        if elements is None:
            return None, [None]
        if not elements:
            return False, [False]  # Empty doesn't have exactly one

        # Count satisfying elements
        count = 0
        has_null = False

        for element in elements:
            # Create new scope with current element
            new_scope = {**scope} if scope else {}
            new_scope[self._name] = element

            # Evaluate predicate with scope
            result, _ = self._pred(match, host, return_edges, new_scope)

            if result is True:
                count += 1
                # Early exit if count > 1
                if count > 1:
                    return False, [False]
            elif result is None:
                has_null = True

        # Return based on count
        if count == 1:
            return True, [True]
        elif count == 0 and has_null:
            return None, [None]  # Uncertain due to nulls
        else:
            return False, [False]


class SIZE(ScalarFunction):
    """
    Implements size() scalar function.
    Returns the length of a list as an integer.

    Can be used in:
    - WHERE clauses: WHERE size(r) > 2
    - RETURN clauses: RETURN size(r) AS pathLength

    Neo4j semantics:
    - Null list → None
    - Empty list [] → 0
    """
    def __init__(self, list_expr):
        self._list_expr = list_expr  # String expr or ListExpression

    def __call__(self, match: Match, host: nx.DiGraph, return_edges: list,
                 scope: Optional[dict] = None):
        # Evaluate list expression
        if isinstance(self._list_expr, str):
            list_obj = ScopedListExpression(self._list_expr)
        else:
            list_obj = self._list_expr

        elements = list_obj.evaluate(match, host, return_edges, scope)

        # Handle null
        if elements is None:
            return None

        # Return length
        return len(elements)

    def __str__(self) -> str:
        """Return string representation for result keys."""
        expr_str = self._list_expr if isinstance(self._list_expr, str) else "..."
        return f"size({expr_str})"


class ToLower(ScalarFunction):
    """
    Implements toLower() scalar function.
    Converts a string to lowercase.
    """

    def __init__(self, expression):
        """
        Initialize toLower with an expression.

        Args:
            expression: Either a ScalarFunction or string entity reference (e.g., "n.name")
        """
        if isinstance(expression, ScalarFunction):
            self._expression = expression
        else:
            # Wrap entity reference in EntityAttributeGetter at init time
            self._expression = EntityAttributeGetter(expression)

    def __call__(self, match: Match, host: nx.DiGraph, return_edges: list,
                 scope: Optional[dict] = None):
        # Evaluate expression (either ScalarFunction or EntityAttributeGetter)
        if isinstance(self._expression, ScalarFunction):
            value = self._expression(match, host, return_edges, scope)
        else:
            # It's an EntityAttributeGetter
            value = self._expression.evaluate(match, host, return_edges, scope)

        return value.lower() if isinstance(value, str) else value

    def __str__(self) -> str:
        return f"toLower({self._expression})"


class ToUpper(ScalarFunction):
    """
    Implements toUpper() scalar function.
    Converts a string to uppercase.
    """

    def __init__(self, expression):
        """
        Initialize toUpper with an expression.

        Args:
            expression: Either a ScalarFunction or string entity reference (e.g., "n.name")
        """
        if isinstance(expression, ScalarFunction):
            self._expression = expression
        else:
            # Wrap entity reference in EntityAttributeGetter at init time
            self._expression = EntityAttributeGetter(expression)

    def __call__(self, match: Match, host: nx.DiGraph, return_edges: list,
                 scope: Optional[dict] = None):
        # Evaluate expression (either ScalarFunction or EntityAttributeGetter)
        if isinstance(self._expression, ScalarFunction):
            value = self._expression(match, host, return_edges, scope)
        else:
            # It's an EntityAttributeGetter
            value = self._expression.evaluate(match, host, return_edges, scope)

        return value.upper() if isinstance(value, str) else value

    def __str__(self) -> str:
        return f"toUpper({self._expression})"


class Trim(ScalarFunction):
    """
    Implements trim() scalar function.
    Trims whitespace from a string.
    """

    def __init__(self, expression):
        """
        Initialize trim with an expression.

        Args:
            expression: Either a ScalarFunction or string entity reference (e.g., "n.name")
        """
        if isinstance(expression, ScalarFunction):
            self._expression = expression
        else:
            # Wrap entity reference in EntityAttributeGetter at init time
            self._expression = EntityAttributeGetter(expression)

    def __call__(self, match: Match, host: nx.DiGraph, return_edges: list,
                 scope: Optional[dict] = None):
        # Evaluate expression (either ScalarFunction or EntityAttributeGetter)
        if isinstance(self._expression, ScalarFunction):
            value = self._expression(match, host, return_edges, scope)
        else:
            # It's an EntityAttributeGetter
            value = self._expression.evaluate(match, host, return_edges, scope)

        return value.strip() if isinstance(value, str) else value

    def __str__(self) -> str:
        return f"trim({self._expression})"


class Type(ScalarFunction):
    """
    Implements type() scalar function.
    Returns the type/label of a relationship.
    """

    def __init__(self, expression: str):
        self._expression = expression  # e.g., "r"

    def __call__(self, match: Match, host: nx.DiGraph, return_edges: list,
                 scope: Optional[dict] = None):
        # Type works on relationships only
        # Use return_edges to find the edge
        if self._expression in return_edges:
            edge_mapping = return_edges[self._expression]
            host_edges = match.mth.edge(*edge_mapping).edges
            edge_data = get_edge_from_host(host, host_edges, None)

            # edge_data might be a dict or list
            if isinstance(edge_data, dict):
                # Single edge
                labels = edge_data.get('__labels__', set())
                if labels:
                    return list(labels)[0] if isinstance(labels, set) else labels
            elif isinstance(edge_data, list) and len(edge_data) > 0:
                # Multiple edges - return first label
                labels = edge_data[0].get('__labels__', set())
                if labels:
                    return list(labels)[0] if isinstance(labels, set) else labels

        return None

    def __str__(self) -> str:
        return f"type({self._expression})"


class Coalesce(ScalarFunction):
    """
    Implements coalesce() scalar function.
    Returns the first non-null value from the argument list.
    """

    def __init__(self, expressions: list):
        self._expressions = expressions  # List of expressions

    def __call__(self, match: Match, host: nx.DiGraph, return_edges: list,
                 scope: Optional[dict] = None):
        # Evaluate each expression and return first non-null
        for expr in self._expressions:
            # Check if it's an EntityAttributeGetter (entity reference)
            if isinstance(expr, EntityAttributeGetter):
                # It's an entity reference like n.name or n
                value = expr.evaluate(match, host)
                if value is not None:
                    return value
            else:
                # It's a literal value (string, number, bool, None, etc.)
                if expr is not None:
                    return expr
        return None

    def __str__(self) -> str:
        # Format expressions for display
        expr_strs = []
        for expr in self._expressions:
            if isinstance(expr, EntityAttributeGetter):
                # Entity reference: n.name or n
                expr_strs.append(str(expr))
            elif isinstance(expr, str):
                # String literal: show with quotes
                expr_strs.append(f'"{expr}"')
            else:
                # Other literals: numbers, booleans, None
                expr_strs.append(repr(expr))
        return f"coalesce({', '.join(expr_strs)})"


# ==================== End of List Predicate Classes ====================


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
    """
    Parse data path into entity name and attribute using EntityAttributeGetter.

    Args:
        data_path: String path (e.g., "n.name", "n") or Token containing the path

    Returns:
        tuple: (entity_name, entity_attribute)
    """
    if isinstance(data_path, Token):
        data_path = data_path.value

    # Use EntityAttributeGetter to parse the path
    getter = EntityAttributeGetter(data_path)
    return getter.entity, getter.attribute


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


def to_indexer_ast(condition: Condition, entity_id = None, value = None, should_be=True) -> IndexerConditionAST:
    """convert where condition to IndexerConditionAST which can be run with IndexerConditionRunner"""
    # for condition in condition:
    if isinstance(condition, CompoundCondition):
        return to_indexer_ast(condition=condition._operator,
                                entity_id=condition._entity_id,
                                value=condition._value,
                                should_be=condition._should_be)
    if (isinstance(condition, LambdaCompareCondition) and
        condition._operator in WHERE_OPERATORS_TO_INDEXER_OPERATORS):
        # Handle scalar functions
        if isinstance(entity_id, ID):
            # ID() can be optimized - extract entity name
            entity_id = entity_id._entity_name
        elif isinstance(entity_id, EntityAttributeGetter):
            # EntityAttributeGetter can be optimized - extract full expression
            if entity_id.attribute:
                entity_id = f"{entity_id.entity}.{entity_id.attribute}"
            else:
                entity_id = entity_id.entity
        elif not isinstance(entity_id, str):
            # Other scalar functions can't be optimized by indexer
            return IndexerUnsupportedOp(condition, entity_id, value)
        operator = condition._operator
        if should_be is True:
            operator = WHERE_OPERATORS_TO_INDEXER_OPERATORS[operator]
        else:
            operator = NOT_WHERE_OPERATORS_TO_INDEXER_OPERATORS[operator]
        return IndexerCompare(operator, entity_id, value)
    if isinstance(condition, OR):
        return IndexerOr(
            to_indexer_ast(condition._condition_a, entity_id, value),
            to_indexer_ast(condition._condition_b, entity_id, value),
        )
    if isinstance(condition, AND):
        return IndexerAnd(
            to_indexer_ast(condition._condition_a, entity_id, value),
            to_indexer_ast(condition._condition_b, entity_id, value),
        )
    return IndexerUnsupportedOp(condition, entity_id, value)


def motif_to_indexer_ast(motif: nx.DiGraph) -> IndexerConditionAST:
    # TODO: Test
    ast = None
    for cname, json_data in motif.nodes(data=True):
        for k, v in json_data.items():
            if k == "__labels__":
                continue
            k = cname + "." + k
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

        # Handle all scalar functions (ID, SIZE, future functions) - UNIFIED!
        for data_path in data_paths:
            if isinstance(data_path, ScalarFunction):
                # Evaluate scalar function for each match
                ret = []
                for match in true_matches:
                    result_value = data_path(
                        match,
                        self._target_graph,
                        self._return_edges,
                        scope=None
                    )
                    ret.append(result_value)

                # Use str(data_path) as key: "ID(A)", "size(r)", etc.
                result[str(data_path)] = ret[offset_limit]
                processed_paths.add(data_path)
                processed_paths.add(str(data_path))
                continue

        # Validate entity names for non-scalar-function data paths
        for data_path in data_paths:
            if isinstance(data_path, ScalarFunction):
                continue  # Skip scalar functions, already processed

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
                # Use EntityAttributeGetter for consistent entity access
                # If entity_attribute exists: returns specific attribute value
                # If entity_attribute is None: returns full node dictionary
                getter = EntityAttributeGetter(data_path)
                ret = (
                    getter.evaluate(match, self._target_graph, self._return_edges)
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
                # We are looking for an edge mapping in the target graph:
                # Use EntityAttributeGetter for consistent entity access
                getter = EntityAttributeGetter(data_path)
                ret = (
                    getter.evaluate(match, self._target_graph, self._return_edges)
                    for match in true_matches
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
            # Determine group keys: exclude keys that end with aggregated entity path
            # (matches old aggregate() logic)
            group_keys = [
                key
                for key in results.keys()
                if not any(
                    key.endswith(
                        agg_func._entity + ('.' + agg_func._entity_attribute if agg_func._entity_attribute else '')
                    )
                    for agg_func in self._aggregate_functions
                )
            ]

            aggregated_results = {}
            # Evaluate each aggregation function using scope-based architecture
            for agg_func in self._aggregate_functions:
                # Call evaluate() with scope (results dict from _lookup)
                aggregated_data = agg_func.evaluate(
                    self._get_true_matches(),
                    self._target_graph,
                    self._return_edges,
                    group_keys,
                    scope=results  # Pass results as scope
                )
                aggregated_values = list(aggregated_data.values())
                aggregated_keys = list(aggregated_data.keys())
                # Use str(agg_func) for result key: "COUNT(r)", "SUM(r.value)", etc.
                func_key = str(agg_func)
                aggregated_results[func_key] = aggregated_values
                self._return_requests.append(func_key)

            # Merge aggregated results with regular results
            results.update(aggregated_results)
            # Reconstruct grouped results
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
        # Convert all return_requests to strings (including scalar functions) for key matching
        # Use a local variable to avoid modifying self._return_requests (breaks reusability)
        return_requests_str = [str(item) for item in self._return_requests]

        # Only include keys that were asked for in `RETURN` in the final results
        results = {
            self._entity2alias.get(key, key): values
            for key, values in results.items()
            if key in return_requests_str
            or self._alias2entity.get(key, key) in return_requests_str
        }

        # TODO: remove this hack
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
                    # Parse to AggregationFunction object (not tuple)
                    agg_func = self._parse_aggregation_token(item)
                    if alias:
                        # Use str(agg_func) for alias key: "COUNT(r)", "SUM(r.value)", etc.
                        self._executors[-1]._entity2alias[str(agg_func)] = alias
                    # Add full entity path to aggregation_attributes for _lookup
                    entity_path = agg_func._entity + ('.' + agg_func._entity_attribute if agg_func._entity_attribute else '')
                    self._executors[-1]._aggregation_attributes.add(entity_path)
                    # Store AggregationFunction object, not tuple
                    self._executors[-1]._aggregate_functions.append(agg_func)
                else:
                    # Handle scalar functions (ID, SIZE, etc.) - keep object for evaluation
                    if isinstance(item, ScalarFunction):
                        # Keep scalar function object
                        self._executors[-1]._original_return_requests.add(item)
                        if alias:
                            # Use str(item) for alias key: "ID(A)", "size(r)", etc.
                            self._executors[-1]._entity2alias[str(item)] = alias
                        self._executors[-1]._return_requests.append(item)
                    elif not isinstance(item, str):
                        # Convert non-string, non-scalar-function items to string
                        item = str(item.value)
                        self._executors[-1]._original_return_requests.add(item)
                        if alias:
                            self._executors[-1]._entity2alias[item] = alias
                        self._executors[-1]._return_requests.append(item)
                    else:
                        # Already a string, use as-is
                        self._executors[-1]._original_return_requests.add(item)
                        if alias:
                            self._executors[-1]._entity2alias[item] = alias
                        self._executors[-1]._return_requests.append(item)

        self._executors[-1]._alias2entity.update({v: k for k, v in self._executors[-1]._entity2alias.items()})

    def _parse_aggregation_token(self, item: Tree) -> AggregationFunction:
        """
        Parse the aggregation function token and return an AggregationFunction object.
            input: Tree('aggregation_function', [Token('AGGREGATE_FUNC', 'SUM'), Token('CNAME', 'r'), Tree('attribute_id', [Token('CNAME', 'value')])])
            output: SUM('r', 'value') object
        """
        func_name = str(item.children[0].value).upper()  # COUNT, SUM, AVG, MAX, MIN
        entity = str(item.children[1].value)
        entity_attribute = None

        if len(item.children) > 2:
            entity_attribute = str(item.children[2].children[0].value)

        # Create appropriate AggregationFunction class instance
        func_class = {
            "COUNT": COUNT,
            "SUM": SUM,
            "AVG": AVG,
            "MAX": MAX,
            "MIN": MIN,
            "COLLECT": COLLECT,
        }[func_name]

        return func_class(entity, entity_attribute)

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
                # Parse to AggregationFunction object
                agg_func = self._parse_aggregation_token(item.children[0])
                # Use str(agg_func) for field name: "COUNT(r)", "SUM(r.value)", etc.
                field = str(agg_func)
                # Add full entity path to order_by_attributes for _lookup
                entity_path = agg_func._entity + ('.' + agg_func._entity_attribute if agg_func._entity_attribute else '')
                self._executors[-1]._order_by_attributes.add(entity_path)
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
            item = val[0]
            # Check if already a Condition object (ALL, ANY, or other)
            if isinstance(item, Condition):
                return item
            val = CompoundCondition(*item)
        else:  # len == 3
            compound_a, operator, compound_b = val
            val = operator(compound_a, compound_b)
        return val

    def where_and(self, val):
        return _BOOL_ARI["and"]

    def where_or(self, val):
        return _BOOL_ARI["or"]

    def condition(self, condition):
        if len(condition) == 1:  # sub query or list predicate or scalar function
            item = condition[0]
            # Check if it's already a Condition object (ALL, ANY, NONE, SINGLE, ScalarFunction)
            if isinstance(item, (ALL, ANY, NONE, SINGLE, ScalarFunction)):
                return item
            condition = item

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
        # Return ID object (class-based, not string-based)
        return ID(entity_name)

    def tolower_function(self, items):
        """
        Parse: toLower(n) or toLower(n.name) or toLower(trim(n.name))

        items: [scalar_func_arg] which is a Tree containing either a ScalarFunction or entity_id
        """
        arg = items[0]

        # arg is a Tree with 'scalar_func_arg'
        if hasattr(arg, 'children') and len(arg.children) > 0:
            first_child = arg.children[0]

            # Check if the first child is a ScalarFunction (nested)
            if isinstance(first_child, ScalarFunction):
                return ToLower(first_child)

            # Check if first child is a Token (entity name)
            if hasattr(first_child, 'value'):
                if len(arg.children) == 1:
                    # Just entity: n
                    expression = first_child.value
                else:
                    # Has attribute: n.name
                    entity_name = first_child.value
                    attribute_name = arg.children[1].children[0].value
                    expression = f"{entity_name}.{attribute_name}"
                return ToLower(expression)

        # Fallback
        return ToLower(str(arg))

    def toupper_function(self, items):
        """
        Parse: toUpper(n) or toUpper(n.name) or toUpper(trim(n.name))

        items: [scalar_func_arg] which is a Tree containing either a ScalarFunction or entity_id
        """
        arg = items[0]

        # arg is a Tree with 'scalar_func_arg'
        if hasattr(arg, 'children') and len(arg.children) > 0:
            first_child = arg.children[0]

            # Check if the first child is a ScalarFunction (nested)
            if isinstance(first_child, ScalarFunction):
                return ToUpper(first_child)

            # Check if first child is a Token (entity name)
            if hasattr(first_child, 'value'):
                if len(arg.children) == 1:
                    # Just entity: n
                    expression = first_child.value
                else:
                    # Has attribute: n.name
                    entity_name = first_child.value
                    attribute_name = arg.children[1].children[0].value
                    expression = f"{entity_name}.{attribute_name}"
                return ToUpper(expression)

        # Fallback
        return ToUpper(str(arg))

    def trim_function(self, items):
        """
        Parse: trim(n) or trim(n.name) or trim(toLower(n.name))

        items: [scalar_func_arg] which is a Tree containing either a ScalarFunction or entity_id
        """
        arg = items[0]

        # arg is a Tree with 'scalar_func_arg'
        if hasattr(arg, 'children') and len(arg.children) > 0:
            first_child = arg.children[0]

            # Check if the first child is a ScalarFunction (nested)
            if isinstance(first_child, ScalarFunction):
                return Trim(first_child)

            # Check if first child is a Token (entity name)
            if hasattr(first_child, 'value'):
                if len(arg.children) == 1:
                    # Just entity: n
                    expression = first_child.value
                else:
                    # Has attribute: n.name
                    entity_name = first_child.value
                    attribute_name = arg.children[1].children[0].value
                    expression = f"{entity_name}.{attribute_name}"
                return Trim(expression)

        # Fallback
        return Trim(str(arg))

    def type_function(self, items):
        """
        Parse: type(r)

        items: [entity_id]
        """
        entity_name = items[0].value
        return Type(entity_name)

    def coalesce_function(self, items):
        """
        Parse: coalesce(n.name, n.id, 'default')

        items: [coalesce_args Tree]
        """
        # items[0] is the coalesce_args tree
        args_tree = items[0]
        expressions = []

        # Process each coalesce_arg
        for arg in args_tree.children:
            # arg is a Tree with data='coalesce_arg'
            if hasattr(arg, 'data') and arg.data == 'coalesce_arg':
                # It's a Tree containing the argument
                if len(arg.children) == 1:
                    child = arg.children[0]
                    # Check if it's a value or entity_id (both are Tokens or Trees)
                    if hasattr(child, 'value'):
                        # It's a Token - need to determine if it's a literal or entity reference
                        if hasattr(child, 'type'):
                            # Check token type to distinguish literals from entity references
                            if child.type == 'ESTRING':
                                # String literal - parse it (remove quotes and handle escapes)
                                expressions.append(child.value.strip('"').encode().decode('unicode_escape'))
                            elif child.type == 'NUMBER':
                                # Number literal - parse it
                                try:
                                    # Try int first, then float
                                    expressions.append(int(child.value))
                                except ValueError:
                                    expressions.append(float(child.value))
                            elif child.type == 'CNAME':
                                # Entity reference without attribute: n
                                expressions.append(EntityAttributeGetter(child.value))
                            else:
                                # Other token types (shouldn't happen in coalesce)
                                expressions.append(child.value)
                        else:
                            # No type attribute - fallback
                            expressions.append(child.value)
                    elif hasattr(child, 'data'):
                        # It's a Tree (like entity_id or null/true/false)
                        if child.data == 'entity_id':
                            # Just entity name: n
                            entity_name = child.children[0].value
                            expressions.append(EntityAttributeGetter(entity_name))
                        elif child.data == 'null':
                            # NULL literal
                            expressions.append(None)
                        elif child.data == 'true':
                            # TRUE literal
                            expressions.append(True)
                        elif child.data == 'false':
                            # FALSE literal
                            expressions.append(False)
                        else:
                            # Some other tree - shouldn't happen
                            expressions.append(child)
                    else:
                        expressions.append(child)
                elif len(arg.children) >= 2:
                    # entity_id with attribute_id: n.name
                    # arg.children[0] is Token CNAME for entity
                    # arg.children[1] is Tree attribute_id
                    entity_name = arg.children[0].value
                    attribute_name = arg.children[1].children[0].value
                    expressions.append(EntityAttributeGetter(f"{entity_name}.{attribute_name}"))
            else:
                # Direct value (shouldn't happen with current grammar)
                expressions.append(arg)

        return Coalesce(expressions)

    def all_function(self, items):
        """
        Parse: all(edge IN r WHERE edge.weight > 5)

        items structure:
        [0]: CNAME (loop variable, e.g., "edge")
        [1]: list_expression (string or ListExpression)
        [2]: compound_condition (already transformed into CompoundCondition/AND/OR!)
        """
        loop_variable = items[0].value
        list_expression = items[1]  # Already a string or ListExpression
        inner_condition = items[2]  # Already a Condition - perfect!

        # Just pass it through! No conversion needed.
        return ALL(name=loop_variable, list_expr=list_expression, pred=inner_condition)

    def any_function(self, items):
        """Similar to all_function - trivial!"""
        loop_variable = items[0].value
        list_expression = items[1]
        inner_condition = items[2]  # Already a Condition

        return ANY(name=loop_variable, list_expr=list_expression, pred=inner_condition)

    def none_function(self, items):
        """
        Parse: none(edge IN r WHERE edge.weight > 5)

        items: [loop_var, list_expr, condition]
        """
        loop_variable = items[0].value
        list_expression = items[1]
        inner_condition = items[2]

        return NONE(name=loop_variable, list_expr=list_expression, pred=inner_condition)

    def single_function(self, items):
        """
        Parse: single(edge IN r WHERE edge.weight > 5)

        items: [loop_var, list_expr, condition]
        """
        loop_variable = items[0].value
        list_expression = items[1]
        inner_condition = items[2]

        return SINGLE(name=loop_variable, list_expr=list_expression, pred=inner_condition)

    def size_function(self, items):
        """
        Parse: size(r) or size(relationships(r))

        items: [list_expression]
        """
        list_expression = items[0]

        return SIZE(list_expr=list_expression)

    def relationships_function(self, items):
        """Parse: relationships(path_variable)"""
        path_variable = items[0].value if isinstance(items[0], Token) else items[0]
        return path_variable  # Return as string, will be wrapped in ScopedListExpression

    def entity_list(self, items):
        """Parse: direct entity reference as list"""
        entity_id = items[0]
        return entity_id.value if isinstance(entity_id, Token) else entity_id

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
