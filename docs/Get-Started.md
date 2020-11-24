# Getting Started

GrandCypher is a Python implementation of the [Cypher](<https://en.wikipedia.org/wiki/Cypher_(query_language)>) graph query language. It enables you to easily convert queries written for Neo4j into queries for NetworkX graphs. In fact, with [Grand](https://github.com/aplbrain/grand), this tool also enables you to query other graph libraries like [Networkit](https://github.com/networkit/networkit/) or [IGraph](https://igraph.org/).

## Installation

```shell
git clone https://github.com/aplbrain/grandcypher
cd grandcypher
pip3 install -e .
```

## First Steps

```python
from grandcypher import GrandCypher
import networkx as nx

my_graph = nx.read_graphml("my-fun-graph.graphml")

# Get a list of all edges in the graph:
results = GrandCypher(my_graph).run("""
MATCH (A)-[]->(B)
RETURN A, B
""")
```
