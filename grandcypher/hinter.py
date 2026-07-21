"""
Group of classes and functions to deal with hint-related features
"""
from typing import Hashable, Optional
import networkx as nx

from .indexer import IndexDomainType


HintType = dict[Hashable, Hashable]


class Hinter:
    def __init__(self, is_node_attr_match, is_edge_attr_match):
        self._is_node_attr_match = is_node_attr_match
        self._is_edge_attr_match = is_edge_attr_match

    def doublecheck(self, host: nx.DiGraph, motif: nx.DiGraph, match: dict, hints: list[HintType]) -> bool:
        """doublecheck if attr matched for hinted nodes and related edges
        """
        if not hints:
            return True
        hints_keys = set(k for h in hints for k in h.keys())

        hint_motif = motif.subgraph(hints_keys)
        for motif_node_id in hint_motif.nodes():
            host_node_id = match[motif_node_id]
            if not self._is_node_attr_match(motif_node_id, host_node_id, motif, host):
                return False

        for motif_edge in hint_motif.edges():
            host_edge = match[motif_edge[0]], match[motif_edge[1]]
            if host_edge not in host.edges:
                return False
            if not self._is_edge_attr_match(motif_edge, host_edge, motif, host):
                return False

        return True

    def _is_subsumed(self, small: HintType, big: HintType):
        # small ⊆ big
        for k, v in small.items():
            if k not in big or big[k] != v:
                return False
        return True

    def eliminate_supersets(self, hints: list[HintType]) -> list[HintType]:
        """check and keep only subsumed hint.

        For example:
            - This is a full set [{A:1}, {B:2}, {A:1,B:2}, {A:1,B:2,C:3}]
            - This is the result [{A:1}, {B:2}]

        """
        hints = sorted(hints, key=lambda h: len(h))
        result = []
        for hint in hints:
            # If there already exists a more general binding, skip
            subsumed = False
            for res in result:
                # res is always <= b in size
                if self._is_subsumed(res, hint):
                    subsumed = True
                    break
            if not subsumed:
                result.append(hint)

        return result

    def index_domain_to_hints(self, result: IndexDomainType) -> list[HintType]:
        """cartesian products variables' values for possible combination"""
        if not result:
            return []
        keys = list(result.keys())
        ret = [{}]
        for k in keys:
            current = [{k: v} for v in result[k]]
            ret = [{**r, **c} for r in ret for c in current]
        return ret

    def take_hints_with_keys(self, hints: Optional[list[HintType]], keys: set[str]) -> list[HintType]:
        """return only hints having keys
        """
        hints = [{k: h[k] for k in set(keys).intersection(h.keys())} for h in (hints or [])]
        return hints
