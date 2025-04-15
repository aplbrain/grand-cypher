# Hints in GrandCypher

Hints are a powerful feature in GrandCypher that allow you to provide additional guidance to the query engine about which nodes should match specific parts of your query pattern. This can be particularly useful for improving query performance or ensuring specific nodes are included in your results.

## Basic Usage

You can provide hints when running a Cypher query by passing a list of dictionaries to the `run()` method:

```python
gc = GrandCypher(graph)
result = gc.run(query, hints=[{"A": 1}, {"B": 2}])
```

Each dictionary in the hints list maps variable names from your Cypher query to specific node IDs in your graph.

## Why Use Hints?

There are several scenarios where hints are particularly valuable:

1. **Performance Optimization**: When you know exactly which nodes should match certain parts of your pattern, hints can significantly reduce the search space.

2. **Ensuring Specific Matches**: When you want to guarantee that certain nodes are included in your results.

3. **Complex Pattern Matching**: In cases where you want to find patterns that involve specific known nodes along with more general pattern matching.

## How Hints Work

1. When you provide hints, GrandCypher filters the pattern matches based on the node IDs you specify.
2. Each hint dictionary maps variable names from your Cypher query to specific node IDs in your graph.
3. The query engine ensures that the specified variables match only the nodes with the given IDs.
4. Other parts of the pattern that aren't specified in hints are matched normally.

## Best Practices

1. **Use Hints When Possible**: Hints can greatly improve performance, especially in large graphs.
2. **Variable Names Must Match**: The keys in your hint dictionaries must match variable names in your Cypher query.
3. **Valid Node IDs**: Make sure the node IDs you specify in hints actually exist in your graph.
4. **Multiple Hints**: You can provide multiple hints for different variables in the same query.

## Performance Considerations

-   Hints can significantly improve query performance by reducing the search space.
-   However, overly restrictive hints might cause valid matches to be excluded.
-   The performance benefit is most noticeable in large graphs where broad pattern matching would be expensive.

## Common Pitfalls

1. **Missing Nodes**: If you provide a hint for a node ID that doesn't exist, you'll get empty results.
2. **Incompatible Constraints**: If your hints conflict with WHERE clauses or other pattern constraints, you might get unexpected empty results.
3. **Case Sensitivity**: Make sure variable names in hints exactly match those in your query.
