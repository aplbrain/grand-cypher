## Multigraph

```python
from grandcypher import GrandCypher
import networkx as nx

host = nx.MultiDiGraph()
host.add_node("a", name="Alice", age=25)
host.add_node("b", name="Bob", age=30)
host.add_edge("a", "b", __labels__={"paid"}, amount=12, date="12th June")
host.add_edge("b", "a", __labels__={"paid"}, amount=6)
host.add_edge("b", "a", __labels__={"paid"}, value=14)
host.add_edge("a", "b", __labels__={"friends"}, years=9)
host.add_edge("a", "b", __labels__={"paid"}, amount=40)

qry = """
MATCH (n)-[r:paid]->(m)
RETURN n.name, m.name, r.amount
"""
res = GrandCypher(host).run(qry)
print(res)

```

```python
{
    "n.name": ["Alice", "Bob"],
    "m.name": ["Bob", "Alice"],
    "r.amount": [
        {(0, "paid"): 12, (1, "paid"): 40},
        {(0, "paid"): 6, (1, "paid"): None},
    ],
}
```

## Aggregation Functions

```python
from grandcypher import GrandCypher
import networkx as nx

host = nx.MultiDiGraph()
host.add_node("a", name="Alice", age=25)
host.add_node("b", name="Bob", age=30)
host.add_edge("a", "b", __labels__={"paid"}, amount=12, date="12th June")
host.add_edge("b", "a", __labels__={"paid"}, amount=6)
host.add_edge("b", "a", __labels__={"paid"}, value=14)
host.add_edge("a", "b", __labels__={"friends"}, years=9)
host.add_edge("a", "b", __labels__={"paid"}, amount=40)

qry = """
MATCH (n)-[r:paid]->(m)
RETURN n.name, m.name, SUM(r.amount)
"""
res = GrandCypher(host).run(qry)
print(res)
```

```python
{
    "n.name": ["Alice", "Bob"],
    "m.name": ["Bob", "Alice"],
    "SUM(r.amount)": [{"paid": 52}, {"paid": 6}],
}
```
