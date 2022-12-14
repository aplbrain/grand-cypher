# CHANGELOG

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
