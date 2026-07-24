# Expressions and functions

Grand Cypher supports composable expressions in `WHERE` and `RETURN` clauses.

## Scalar functions

The following scalar functions are supported:

| Function | Result |
| --- | --- |
| `ID(n)` | Graph identifier for a matched node |
| `toLower(value)` | Lowercase string |
| `toUpper(value)` | Uppercase string |
| `trim(value)` | String with surrounding whitespace removed |
| `coalesce(a, b, ...)` | First non-null argument |
| `size(value)` | Length of a string or relationship list |
| `type(r)` | One relationship label for a matched relationship |

Functions can be nested and used on either side of a comparison:

```cypher
MATCH (n)
WHERE toLower(trim(n.name)) = toLower(n.canonical_name)
RETURN ID(n), toUpper(n.name)
```

Scalar functions also compose with arithmetic expressions:

```cypher
MATCH (n)
WHERE size(n.name) + 1 > 8
RETURN n.name
```

## Aggregations

Supported aggregation functions are `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`, and
`COLLECT`. Aggregations can group by other returned values:

```cypher
MATCH (n)
RETURN n.team, COLLECT(n.name), AVG(n.score)
ORDER BY AVG(n.score) DESC
```

Aggregation arguments can be scalar expressions:

```cypher
MATCH (n)
RETURN n.team, AVG(size(n.name)) AS average_name_length
ORDER BY AVG(size(n.name)) DESC
```

Direct arithmetic expressions inside aggregation arguments are not currently
supported.

`COLLECT` excludes null values.

## Relationship lists

For a named relationship binding, `relationships(r)` returns the selected
relationship sequence for that match. This is especially useful with
variable-length paths:

```cypher
MATCH (a)-[r*1..3]->(b)
WHERE size(relationships(r)) = 2
RETURN ID(a), ID(b)
```

Each item in the relationship list is an attribute dictionary for one selected
relationship.

If a relationship has multiple labels, `type(r)` returns one of them; label
selection order is not defined.

## List predicates

`ALL`, `ANY`, `NONE`, and `SINGLE` evaluate a condition for each item in a
relationship list:

```cypher
MATCH (a)-[r*2]->(b)
WHERE ALL(edge IN relationships(r) WHERE edge.weight > 5)
RETURN ID(a), ID(b)
```

The loop variable is scoped to the predicate and supports compound conditions:

```cypher
MATCH (a)-[r*2]->(b)
WHERE ALL(
    edge IN relationships(r)
    WHERE edge.weight > 5 AND edge.kind = "friend"
)
RETURN ID(a), ID(b)
```

List predicates use Cypher's three-valued null behavior. A null predicate
result propagates when the known values do not otherwise determine the answer.
