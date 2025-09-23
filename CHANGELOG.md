# CHANGELOG

### **1.0.1** (September 23, 2025)

### Features

-   Support for `|` operator in node labels (#79, thanks @ericnwrites!)

### **1.0.0** (May 23, 2025)

#### Breaking Changes

-   The `RETURN` clause on nodes now returns a list of dictionaries instead of a list of IDs. This is compatible with the actual Cypher spec, but breaks compatibility with the previous version. For more information, see #73 and #57.
-   Migrate to `uv` for package management (#74)

### **0.14.0** (March 18 2025)

#### Features

-   Support for `hints` in the `run` method (#67)

### **0.13.0** (February 17 2025)

#### Housekeeping

-   Remove EOL Python 3.7 and 3.8 from CI, and adds 3.12 and 3.13 (#66, thanks @davidmezzetti!)

#### Features

-   Support for `IN` clause (#66, thanks @davidmezzetti!)

#### Fixes

-   Fix regression in `null` / `true` / `false` (#66, thanks @davidmezzetti!)

### **0.12.0** (January 10 2025)

#### Housekeeping

-   Switch to maintained `lark` parser (#60, thanks @ntjess!)

### **0.11.0** (December 4 2024)

#### Features

-   Support multidigraph/digraph without up-conversion (#55, thanks @jackboyla!)

### **0.10.0** (October 18 2024)

> Bugfix for searching multigraphs, and other improvements for multigraphs.

#### Features

-   Aliasing (`RETURN SUM(r.value) AS myvalue`) (#46, thanks @jackboyla!)

#### Fixes

-   Fix bug in searching multigraphs where unwanted edges between returned nodes were returned (#48, thanks @jackboyla!)
-   Unify digraph and multigraph implementations (#46, thanks @jackboyla!)

### **0.9.0** (June 11 2024)

> Support for aggregate functions like `COUNT`, `SUM`, `MIN`, `MAX`, and `AVG`.

#### Features

-   Support for aggregate functions like `COUNT`, `SUM`, `MIN`, `MAX`, and `AVG` (#45, thanks @jackboyla!)
-   Logical `OR` support in relationship matches (#44, thanks @jackboyla!)

#### Testing

-   Combine tests for digraphs and multidigraphs (#43, thanks @jackboyla!)

### **0.8.0** (May 14 2024)

> Support for MultiDiGraphs.

#### Features

-   Support for MultiDiGraphs (#42, thanks @jackboyla!)

### **0.7.0** (May 4 2024)

> Support for `ORDER BY` and `DISTINCT`

#### Features

-   Support for `ORDER BY` in queries, including `ASC` and `DESC`, and chaining multiple sorts (#41, thanks @jackboyla!)
-   Support for `DISTINCT` in queries (#40, thanks @jackboyla!)

#### Housekeeping

-   Refactor `return` for readability (#41, thanks @jackboyla!)

### **0.6.0** (February 15 2024)

> New path group operator

#### Features

-   Support for path group operators (#37)

### **0.5.0** (February 13 2024)

> Lots of language support for new query operators.

#### Features

-   Support for C-style comments in queries with `//` (#31)
-   Support for string operators, like `CONTAINS`, `STARTS WITH`, and `ENDS WITH` (#33)
-   Support for negation of clauses with `NOT` (#33)

#### Performance

-   Huge performance boost for nonexhaustive queries via streaming matches (#34, thanks @davidmezzetti!)

#### Housekeeping

-   Added more recent version of Python (3.9 through 3.11) to CI (#33)

### **0.4.0** (October 17 2023)

> Many performance updates, language features, and label support.

#### Features

-   Support for multi-hop queries in `MATCH` statements (#24, thanks @khoale88!)
-   Support for single edge and node labels using the `__labels__` magic property (#25, thanks @khoale88!)

#### Performance

-   Performance improvements by @khoale88 that eliminate duplicated entity lookups (#28)

### **0.3.0** (December 14 2022)

> This version adds support for boolean arithmetic with AND/OR, and other language features.

#### Features

-   Support for boolean arithmetic with AND/OR (#20, thanks @khoale88!)
-   Support for undirected edges (`(A)-[]-(B)`)

#### Housekeeping

-   Add install dependencies to `setup.py`

### **0.2.0** (December 12 2022)

> Lots of great new language support by @khoale88, thank you!!

#### Performance

-   Improves performance of the `limit` argument by offloading the result-limiting behavior to `grandiso`.

#### Features

-   Add behavior for disconnected matches of multiple graph components (#17, thanks @khoale88!)
-   Add support for anonymous nodes (#16, thanks @khoale88!)
-   Support chained edges like `(A)-[]->(B)-[]-(C)` (#15, thanks @khoale88!)
-   Support backwards edges (#14, thanks @khoale88!)
-   Support `NULL` and the `is` operator in queriy `WHERE` and property queries (#13, thanks @khoale88!)

### **0.1.1** (October 1 2021)

> This version adds support for node-only matches.

### **0.1.0** (March 23 2021)

> This version adds initial support for querying networkx-flavored graphs with the Cypher query language.
