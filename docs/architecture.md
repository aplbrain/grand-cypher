# GrandCypher Architecture

> High-level architecture overview of the GrandCypher query engine

## Table of Contents
- [Query Lifecycle](#query-lifecycle)
- [AST Structure](#ast-structure)
- [Expression Types](#expression-types)
- [Execution Model](#execution-model)
- [Nesting & Composition](#nesting--composition)

---

## Query Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                        QUERY LIFECYCLE                          │
└─────────────────────────────────────────────────────────────────┘

Input Query String
      │
      ▼
┌─────────────────┐
│  LARK PARSER    │  Parse grammar → Parse Tree
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  TRANSFORMER    │  Parse Tree → AST (Abstract Syntax Tree)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  AST OBJECTS    │  • MatchClause
│  (Query Plan)   │  • WhereCondition
│                 │  • ReturnItems
│                 │  • OrderByClause
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  GRAPH MATCHING │  Find subgraph isomorphisms → Match objects
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  WHERE FILTER   │  Evaluate conditions → Filter matches
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  RETURN BUILD   │  • Evaluate scalar functions (per match)
│                 │  • Collect values for aggregations
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  AGGREGATION    │  Group and aggregate → Final values
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ORDER BY       │  Sort results
└────────┬────────┘
         │
         ▼
    Result Dict
```

---

## AST Structure

The AST is composed of **Condition** objects that form a tree structure.

### Condition Hierarchy

```
                    Condition (base)
                         │
        ┌────────────────┼────────────────┐
        │                │                │
   ScalarFunction   AggregationFunc   Comparison
   (per-match)      (grouped)         (boolean)
        │                │                │
   ┌────┴────┐      ┌────┴────┐      ┌────┴────┐
   │         │      │         │      │         │
  ID      toLower  COUNT    SUM   Compound   AND/OR
  Type    toUpper  AVG      MAX      │
  Size    trim     MIN    COLLECT    │
  coalesce                       EntityOp
```

### AST Node Types

| Node Type | Purpose | Evaluation Time | Returns |
|-----------|---------|----------------|---------|
| **ScalarFunction** | Transform single values | Per match | Single value |
| **AggregationFunction** | Aggregate multiple values | After all matches | Grouped dict |
| **CompoundCondition** | Entity comparison | During WHERE | Boolean |
| **BoolCondition** | Logical operators | During WHERE | Boolean |
| **EntityAttributeGetter** | Entity resolution | Runtime | Entity value |

---

## Expression Types

### 1. Scalar Expressions
**Used in:** WHERE, RETURN, ORDER BY
**Evaluated:** Once per match
**Examples:**
```cypher
ID(n)
toLower(n.name)
trim(n.description)
coalesce(n.nickname, n.name)
```

**AST:**
```
ScalarFunction
  ├─ function_name: "toLower"
  └─ argument: EntityAttributeGetter("n.name")
```

### 2. Aggregation Expressions
**Used in:** RETURN, ORDER BY (not WHERE!)
**Evaluated:** After all matches collected
**Examples:**
```cypher
COUNT(n)
SUM(n.value)
AVG(n.score)
MAX(n.timestamp)
COLLECT(n.tags)
```

**AST:**
```
AggregationFunction
  ├─ function_name: "COUNT"
  ├─ entity: "n"
  └─ attribute: "value"
```

### 3. Comparison Expressions
**Used in:** WHERE clause only
**Evaluated:** During match filtering
**Examples:**
```cypher
n.age > 20
n.name = "Alice"
n.score >= 100
```

**AST:**
```
CompoundCondition
  ├─ entity_id: EntityAttributeGetter("n.age")
  ├─ operator: LambdaCompareCondition(">")
  └─ value: 20
```

### 4. Boolean Expressions
**Used in:** WHERE clause
**Evaluated:** During match filtering
**Examples:**
```cypher
n.age > 20 AND n.age < 65
n.active = true OR n.verified = true
```

**AST:**
```
AND
  ├─ condition_a: CompoundCondition(n.age > 20)
  └─ condition_b: CompoundCondition(n.age < 65)
```

---

## Execution Model

### Phase 1: Parse Time (Static)
**What happens:** Build AST from query string

```
Query: MATCH (n) WHERE n.age > 20 RETURN toLower(n.name), COUNT(n)

Parse Tree → Transformer → AST:
  ├─ MatchClause(nodes=["n"])
  ├─ WhereCondition(
  │    CompoundCondition(
  │      entity="n.age",
  │      operator=">",
  │      value=20
  │    )
  │  )
  └─ ReturnItems([
       ScalarFunction(toLower, "n.name"),
       AggregationFunction(COUNT, "n")
     ])
```

**Key:** All function objects created at parse time, stored as AST nodes.

### Phase 2: Match Time (Graph Traversal)
**What happens:** Find subgraph patterns

```
Motif: (n)
Host Graph: A, B, C, D, E

grandiso.find_motifs() →
  Match(node_mappings={"n": "A"})
  Match(node_mappings={"n": "B"})
  Match(node_mappings={"n": "C"})
  ...
```

### Phase 3: Filter Time (WHERE Evaluation)
**What happens:** Evaluate conditions per match

```
For each match:
  ┌──────────────────────────────────┐
  │  WHERE CONDITION EVALUATION      │
  ├──────────────────────────────────┤
  │  CompoundCondition.__call__():   │
  │    1. Resolve entity_id          │
  │       n.age → host.nodes["A"]["age"] = 25
  │    2. Apply operator             │
  │       25 > 20 → True             │
  │    3. Return (bool, results)     │
  └──────────────────────────────────┘

  Keep match if True, discard if False
```

**Timing:** **Scalar functions in WHERE evaluated here** (per match)

### Phase 4: Return Time (Data Collection)
**What happens:** Evaluate RETURN expressions

```
For each passing match:
  ┌──────────────────────────────────────┐
  │  SCALAR FUNCTION EVALUATION          │
  ├──────────────────────────────────────┤
  │  toLower(n.name).__call__():         │
  │    1. Get entity value               │
  │       n.name → "Alice"               │
  │    2. Apply function                 │
  │       toLower("Alice") → "alice"     │
  │    3. Store result                   │
  │       results["toLower(n.name)"] = "alice"
  └──────────────────────────────────────┘

  Also collect values for aggregations:
    scope["n"] = ["A", "B", "C", ...]
```

**Timing:** **Scalar functions in RETURN evaluated here** (per match)

### Phase 5: Aggregation Time (After All Matches)
**What happens:** Compute aggregated values

```
After ALL matches collected:
  ┌──────────────────────────────────────┐
  │  AGGREGATION FUNCTION EVALUATION     │
  ├──────────────────────────────────────┤
  │  COUNT(n).evaluate():                │
  │    1. Get scope values               │
  │       scope["n"] = ["A", "B", "C"]   │
  │    2. Group by group_keys            │
  │       No grouping → {(): ["A","B","C"]}
  │    3. Compute aggregation            │
  │       Count non-null → 3             │
  │    4. Return {(): 3}                 │
  └──────────────────────────────────────┘
```

**Timing:** **Aggregations evaluated here** (after all matches)

### Phase 6: Order & Format Time
**What happens:** Sort and finalize results

```
ORDER BY applied
Results formatted as dict
Return to user
```

---

## Nesting & Composition

### Scalar Function Nesting

Scalar functions can be nested arbitrarily deep:

```cypher
RETURN toLower(trim(n.name))
```

**AST:**
```
ToLower
  └─ argument: Trim
       └─ argument: EntityAttributeGetter("n.name")
```

**Execution (inside-out):**
```
1. EntityAttributeGetter("n.name").evaluate() → "  Alice  "
2. Trim.__call__("  Alice  ") → "Alice"
3. ToLower.__call__("Alice") → "alice"
```

**Call Stack:**
```
toLower.__call__():
  │
  ├─ Evaluate argument (Trim object)
  │    └─ trim.__call__():
  │         │
  │         ├─ Evaluate argument (EntityAttributeGetter)
  │         │    └─ get("  Alice  ")
  │         │
  │         └─ return "Alice"
  │
  └─ return "alice"
```

### Composition in WHERE

```cypher
WHERE toLower(n.name) = "alice" AND n.age > 20
```

**AST:**
```
AND
  ├─ CompoundCondition
  │    ├─ entity_id: ToLower(EntityAttributeGetter("n.name"))
  │    ├─ operator: "="
  │    └─ value: "alice"
  └─ CompoundCondition
       ├─ entity_id: EntityAttributeGetter("n.age")
       ├─ operator: ">"
       └─ value: 20
```

**Execution:**
```
AND.__call__():
  ├─ Evaluate condition_a:
  │    └─ ToLower(n.name) → "alice"
  │    └─ "alice" = "alice" → True
  │
  ├─ Evaluate condition_b:
  │    └─ n.age → 25
  │    └─ 25 > 20 → True
  │
  └─ True AND True → True
```

### Mixed Scalar + Aggregation

```cypher
RETURN toLower(n.name), COUNT(n), SUM(n.value)
```

**AST:**
```
ReturnItems: [
  ScalarFunction(toLower),    ← Evaluated per match
  AggregationFunction(COUNT), ← Evaluated after all matches
  AggregationFunction(SUM)    ← Evaluated after all matches
]
```

**Execution Timeline:**
```
Time →
├─ Match phase: Find all matches
│
├─ RETURN phase (per match):
│   └─ Evaluate toLower(n.name) for each match
│       Results: ["alice", "bob", "charlie"]
│
└─ Aggregation phase (all matches):
    ├─ COUNT(n): 3
    └─ SUM(n.value): 150
```

---

## Key Architectural Patterns

### 1. Wrap at Parse, Evaluate at Runtime
```
Parse Time: Create ScalarFunction objects (AST nodes)
Run Time:   Call __call__() to get actual values
```

### 2. Two-Phase Return Processing
```
Phase 1 (per match):  Evaluate scalar expressions
Phase 2 (after all):  Evaluate aggregation expressions
```

### 3. Scope-Based Communication
```
Scalar phase → Collect values → Store in scope dict
                                       ↓
Aggregation phase ← Read from scope ← Group & compute
```

### 4. AST Optimization
```
WHERE conditions → to_indexer_ast() → IndexerAST
                                         ↓
                                    Binary search
                                    on indexed attrs
```

### 5. Entity vs Literal Distinction
```
EntityAttributeGetter("n.name") ← Entity reference (resolve at runtime)
"Unknown"                       ← Literal value (use as-is)
```

---

## Summary: When Things Are Called

| Expression Type | Created (Parse) | Called (Runtime) | Context |
|----------------|----------------|------------------|---------|
| **Scalar in WHERE** | ✓ AST node | During filtering | Per match |
| **Scalar in RETURN** | ✓ AST node | During collection | Per match |
| **Aggregation in RETURN** | ✓ AST node | After all matches | Grouped |
| **Comparison in WHERE** | ✓ AST node | During filtering | Per match |
| **Boolean (AND/OR)** | ✓ AST node | During filtering | Per match |

**Rule of Thumb:**
- **Scalar:** Called for each match individually
- **Aggregation:** Called once with all matches
- **WHERE:** Evaluated during filtering (short-circuits)
- **RETURN:** Evaluated during collection & aggregation

---

## Architecture Decisions

### Why Two Function Types?

**Scalars:**
- Operate on single values
- Can be used anywhere (WHERE, RETURN, ORDER BY)
- Example: `toLower("Alice")` → `"alice"`

**Aggregations:**
- Require full dataset to compute
- Only in RETURN/ORDER BY (not WHERE)
- Example: `COUNT(["A", "B", "C"])` → `3`

### Why EntityAttributeGetter?

Without wrapping, parser can't distinguish:
```cypher
coalesce(n.name, "Unknown")
         ^^^^^^^  ^^^^^^^^^
       entity ref   literal
```

With wrapping:
```python
coalesce([
  EntityAttributeGetter("n.name"),  # Resolve at runtime
  "Unknown"                          # Use as-is
])
```

### Why Scope Dictionary?

Aggregations need pre-computed values:
```python
# Can't evaluate COUNT during match iteration
# Need all values first, then count

matches = [match1, match2, match3]

# Phase 1: Collect
scope = {"n": ["A", "B", "C"]}

# Phase 2: Aggregate
COUNT.evaluate(scope) → 3
```

---

## Example: Full Query Trace

**Query:**
```cypher
MATCH (n:Person)
WHERE n.age > 20 AND toLower(n.name) STARTS WITH "a"
RETURN n.name, COUNT(n) AS total
ORDER BY total DESC
```

**AST:**
```
Match: (n:Person)
Where: AND(
  CompoundCondition(n.age > 20),
  CompoundCondition(toLower(n.name) STARTS WITH "a")
)
Return: [
  EntityAttributeGetter("n.name"),
  COUNT("n")
]
OrderBy: "total" DESC
```

**Execution:**
```
1. PARSE:    Query → AST (functions created, not called)
2. MATCH:    Find all (n:Person) → 100 matches
3. WHERE:    Filter each match:
             - n.age > 20? (50 pass)
             - toLower(n.name) starts with "a"? (10 pass)
             Final: 10 matches
4. RETURN:   For each 10 matches:
             - Evaluate n.name → ["Alice", "Aaron", ...]
             - Store scope["n"] = ["A", "B", ...]
5. AGGREGATE: COUNT(scope["n"]) → {(): 10}
6. ORDER:    Sort by total DESC
7. RESULT:   {"n.name": [...], "total": [10]}
```

---

**Last Updated:** 2025-12-06
**Version:** 1.0
