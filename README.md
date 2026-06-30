<h1 align=center>Grand-Cypher</h1>
<div align=center><img src="https://img.shields.io/pypi/v/grand-cypher?style=for-the-badge" /> <img alt="GitHub Workflow Status (branch)" src="https://img.shields.io/github/actions/workflow/status/aplbrain/grand-cypher/python-package.yml?branch=master&style=for-the-badge"></div>

```shell
pip install grand-cypher
```

Grand-Cypher is a partial (and growing!) implementation of the Cypher graph query language written in Python, for Python data structures.

You likely already know Cypher from the Neo4j Graph Database. Use it with your favorite graph libraries in Python!

## Usage

### Example Usage with NetworkX:

```python
from grandcypher import GrandCypher
import networkx as nx

GrandCypher(nx.karate_club_graph()).run("""
MATCH (A)-[]->(B)
MATCH (B)-[]->(C)
WHERE A.club == "Mr. Hi"
RETURN A.club, B.club
""")
```

See [examples.md](docs/examples.md) for more!

### Example Usage with SQL

Create your own "Sqlite for Neo4j"! This example uses [grand-graph](https://github.com/aplbrain/grand) to run queries in SQL:

```python
import grand
from grandcypher import GrandCypher

G = grand.Graph(
    backend=grand.backends.SQLBackend(
        db_url="my_persisted_graph.db",
        directed=True
    )
)

# use the networkx-style API for the Grand library:
G.nx.add_node("A", foo="bar")
G.nx.add_edge("A", "B")
G.nx.add_edge("B", "C")
G.nx.add_edge("C", "A")

GrandCypher(G.nx).run("""
MATCH (A)-[]->(B)-[]->(C)
MATCH (C)-[]->(A)
WHERE
    A.foo == "bar"
RETURN
    A, B, C
""")
```

# Feature Parity

| Feature                                                     | Support                    |
| ----------------------------------------------------------- | -------------------------- |
| Multiple `MATCH` clauses                                    | ✅                         |
| `WHERE`-clause filtering on nodes                           | ✅                         |
| Anonymous `-[]-` edges                                      | ✅                         |
| `LIMIT`                                                     | ✅                         |
| `SKIP`                                                      | ✅                         |
| Node/edge attributes with `{}` syntax                       | ✅                         |
| `WHERE`-clause filtering on edges                           | ✅                         |
| Named `-[]-` edges                                          | ✅                         |
| Chained `()-[]->()-[]->()` edges                            | ✅ Thanks @khoale88!       |
| Backwards `()<-[]-()` edges                                 | ✅ Thanks @khoale88!       |
| Anonymous `()` nodes                                        | ✅ Thanks @khoale88!       |
| Undirected `()-[]-()` edges                                 | ✅ Thanks @khoale88!       |
| Boolean Arithmetic (`AND`/`OR`)                             | ✅ Thanks @khoale88!       |
| `(:Type)` node-labels                                       | ✅ Thanks @khoale88!       |
| `[:Type]` edge-labels                                       | ✅ Thanks @khoale88!       |
| `DISTINCT`                                                  | ✅ Thanks @jackboyla!      |
| `ORDER BY`                                                  | ✅ Thanks @jackboyla!      |
| `IN`                                                        | ✅ Thanks @davidmezzetti!  |
| Aggregation functions (`COUNT`, `SUM`, `MIN`, `MAX`, `AVG`) | ✅ Thanks @jackboyla!      |
| Aliasing of returned entities (`return X as Y`)             | ✅ Thanks @jackboyla!      |
| `WHERE` clause arithmetic support for math / numbers        | ✅ Thanks @q-rosiebloxsom! |
| Negated edges (`where not (a)-->(b)`)                       | 🥺                         |
| `OPTIONAL MATCH`                                            | 🥺                         |
| Graph mutations (e.g. `DELETE`, `SET`,...)                  | 🥺                         |

|                |                |                   |                  |
| -------------- | -------------- | ----------------- | ---------------- |
| ✅ = Supported | 🛣 = On Roadmap | 🥺 = Help Welcome | 🔴 = Not Planned |

Plus several quality-of-life features for Python users, such as:

| Feature                                                                 | Support                                      |
| ----------------------------------------------------------------------- | -------------------------------------------- |
| Interoperability with NetworkX, Grand, and other Python graph libraries | ✅                                           |
| Support for node and edge Labels                                        | ✅ ([[Read More]](docs/Label-Convention.md)) |
| Pickleable results                                                      | ✅ Thanks @q-rosiebloxsom!                   |

## Citing

If this tool is helpful to your research, please consider citing it with:

```bibtex
# https://doi.org/10.1038/s41598-021-91025-5
@article{Matelsky_Motifs_2021,
    title={{DotMotif: an open-source tool for connectome subgraph isomorphism search and graph queries}},
    volume={11},
    ISSN={2045-2322},
    url={http://dx.doi.org/10.1038/s41598-021-91025-5},
    DOI={10.1038/s41598-021-91025-5},
    number={1},
    journal={Scientific Reports},
    publisher={Springer Science and Business Media LLC},
    author={Matelsky, Jordan K. and Reilly, Elizabeth P. and Johnson, Erik C. and Stiso, Jennifer and Bassett, Danielle S. and Wester, Brock A. and Gray-Roncal, William},
    year={2021},
    month={Jun}
}
```
