# The `__labels__` magic attribute

In NetworkX and Grand graph objects, there is no canonical way to "type" a vertex or edge. In Cypher, this is done with labels. For example, a node may have the label `:Person` or `:Book`, and an edge may have the label `[:AUTHORED]`.

By convention, this repository uses the `__labels__` attribute on a vertex to store the labels of a node. This is an iterable of strings. The `__labels__` attribute is not required, but if it is present, it can be used in queries:

```python
from grandcypher import GrandCypher
import networkx as nx

G = nx.Graph()
G.add_node(1, name="Douglas Adams", __labels__=["Person"])
G.add_node(2, name="The Hitchhiker's Guide to the Galaxy", __labels__=["Book"])
G.add_edge(1, 2, __labels__=["AUTHORED"])

GrandCypher(G).run("""
MATCH (a:Person)-[e]->(b:Book)
RETURN a.name, b.name
""")
```

## Data IO

The [`grand-cypher-io`](https://github.com/aplbrain/grand-cypher-io) repository provides a set of tools for reading and writing graphs in OpenCypher format.

The `__labels__` attribute on nodes and edges will be automatically used to populate the "labels" attribute of the node for the purposes of writing to an OpenCypher file.

Likewise, the `__labels__` attribute is used to populate the labels attribute of a node when _reading_ from an OpenCypher file.
