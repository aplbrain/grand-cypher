# CHANGELOG

### **0.5.0** (Unreleased)

> Lots of language support for new query operators.

#### Features

-   Support for C-style comments in queries with `//` (#31)
-   Support for string operators, like `CONTAINS`, `STARTS WITH`, and `ENDS WITH` (#33)
-   Support for negation of clauses with `NOT` (#33)

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
