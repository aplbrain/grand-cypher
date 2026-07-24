# Query expression architecture

Grand Cypher parses a query with Lark and transforms the parse tree into typed
runtime objects. Matching and expression evaluation are intentionally separate:

1. `GrandCypherTransformer` builds the motif and expression objects.
2. `GrandCypherExecutor` finds graph matches.
3. Expressions evaluate against one `Match`, the host graph, relationship
   bindings, and an optional temporary scope.
4. Aggregation expressions group per-match values after lookup.

## Expression protocol

Runtime expressions implement:

```python
evaluate(match, host, return_edges, scope=None)
```

Built-in typed references and arithmetic expressions use the same contract.
`ExpressionBase` provides inexpensive runtime dispatch; the structural
`Expression` protocol remains available for typing.

Typed references have distinct behavior:

- `EntityRef` represents a bare node or relationship name.
- `AttributeRef` resolves node and relationship attributes.
- `IDRef` resolves a matched node identifier.

## Scalar composition

Scalar expression objects contain argument expressions. Evaluation recursively
resolves their arguments, allowing function nesting, scalar-to-scalar
comparisons, and arithmetic composition without adding function-specific paths
to the executor.

## Scoped evaluation

The optional `scope` maps temporary names to values. Scoped names take priority
over graph bindings. List predicates create a child scope for each relationship
item, binding the predicate variable to that relationship's attribute mapping.

Scope propagates through scalar functions, arithmetic expressions, boolean
conditions, and comparisons.

## Aggregation

`AggregationExpression` owns shared grouping mechanics. Concrete classes
implement `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`, and `COLLECT`.

Simple node and relationship references use the existing lookup columns.
Supported computed arguments, such as scalar functions and relationship-list
expressions, evaluate once per match before grouping. Direct arithmetic
aggregation arguments are not currently part of the grammar. Aggregations in
the same query must produce identical group keys.

## Relationship lists

`RelationshipsExpression` materializes the concrete edge path selected for a
relationship binding. It respects multigraph edge keys, so predicates evaluate
the specific matched relationship rather than another parallel edge.

## Index hints

The indexer optimizes supported simple attribute comparisons. Computed scalar,
arithmetic, relationship-list, and list-predicate expressions fall back to the
normal full evaluation path when they cannot be represented safely as an index
condition.
