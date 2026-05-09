# JayDeBeApiArrow

[![Test Status](https://github.com/HenryNebula/jaydebeapiarrow/actions/workflows/tests.yml/badge.svg)](https://github.com/HenryNebula/jaydebeapiarrow/actions/workflows/tests.yml)
[![PyPI version](https://img.shields.io/pypi/v/JayDeBeApiArrow.svg)](https://pypi.python.org/pypi/JayDeBeApiArrow/)

A high-performance Python [DB-API 2.0](http://www.python.org/dev/peps/pep-0249/) bridge to databases using Java [JDBC](http://java.sun.com/products/jdbc/overview.html) drivers, accelerated with **Apache Arrow**.

JayDeBeApiArrow converts JDBC result sets to Arrow record batches directly within the JVM, then streams them to Python via the Arrow C Data Interface - achieving up to **24x speedup** over the original jaydebeapi for large datasets.

> This is a fork of [JayDeBeApi](https://github.com/baztian/jaydebeapi).

## Quick Start

```bash
pip install JayDeBeApiArrow
```

```python
import jaydebeapiarrow

conn = jaydebeapiarrow.connect(
    "org.postgresql.Driver",
    "jdbc:postgresql://localhost:5432/mydb",
    ["user", "password"],
    "/path/to/pgjdbc.jar"
)

with conn.cursor() as curs:
    curs.execute("SELECT * FROM large_table")
    table = curs.fetch_arrow_table()  # zero-copy Arrow table
    df = table.to_pandas()            # or convert to pandas

conn.close()
```

## Key Features

- **DB-API 2.0 compliant** - drop-in replacement for any jaydebeapi-based code
- **Apache Arrow fast path** - `fetch_arrow_table()`, `fetch_arrow_batches()`, `fetch_df()`
- **Native Python types** - `datetime`, `Decimal`, `bytes` instead of strings
- **Works with any JDBC driver** - PostgreSQL, MySQL, Oracle, SQL Server, SQLite, DB2, Teradata, and more

## Sections

- **[Design](design.md)** - architecture and data flow
- **[Usage](usage.md)** - connection, cursors, Arrow API, parameter binding
- **[Data Mapping](data-mapping.md)** - JDBC type mappings and known limitations
- **[Benchmarks](benchmarks.md)** - performance results and methodology
- **[Differences](differences.md)** - changes from the parent JayDeBeApi project
