# Usage

## Installation

```bash
pip install JayDeBeApiArrow
```

Requires Python 3.9+ and a JDK (8+). JPype and PyArrow are installed automatically as dependencies.

## Drop-In Replacement

JayDeBeApiArrow is a **drop-in replacement** for the original [jaydebeapi](https://github.com/baztian/jaydebeapi). If your code uses jaydebeapi today, simply change the import:

```python
# Before
import jaydebeapi

# After
import jaydebeapiarrow
```

Everything else — `connect()`, `execute()`, `fetchall()`, `fetchone()`, `fetchmany()`, `executemany()`, parameter binding, transactions — works identically. No code changes needed.

The drop-in path still benefits from the Arrow fast path under the hood: data is converted to Arrow record batches in-JVM (bypassing the slow row-by-row JPype serialization), then converted to Python tuples for DB-API 2.0 compatibility. This alone gives a **~7.7x speedup** over the original jaydebeapi at 5M rows.

```python
import jaydebeapiarrow

conn = jaydebeapiarrow.connect(
    "org.postgresql.Driver",
    "jdbc:postgresql://host:5432/db",
    ["user", "password"],
    "/path/to/pgjdbc.jar"
)

curs = conn.cursor()
curs.execute("SELECT * FROM large_table")
rows = curs.fetchall()  # standard DB-API — but ~8x faster than jaydebeapi
curs.close()
conn.close()
```

## Native Arrow API

For maximum performance, use the Arrow-native methods to skip the tuple conversion entirely:

```python
with conn.cursor() as curs:
    curs.execute("SELECT * FROM large_table")

    # Streaming — yields pyarrow.RecordBatch objects (memory-efficient for huge results)
    for batch in curs.fetch_arrow_batches():
        print(batch.num_rows)

    # All-at-once — returns a single pyarrow.Table
    table = curs.fetch_arrow_table()

    # Direct to pandas
    df = curs.fetch_df()
```

| Method | Returns | Speedup vs jaydebeapi | Use Case |
|---|---|---|---|
| `fetchall()` / `fetchone()` / `fetchmany()` | `tuple` / `list[tuple]` | ~7.7x | Drop-in replacement, DB-API compatibility |
| `fetch_arrow_batches()` | `Iterator[pyarrow.RecordBatch]` | ~21x | Streaming large results |
| `fetch_arrow_table()` | `pyarrow.Table` | ~21x | All data at once |
| `fetch_df()` | `pandas.DataFrame` | ~21x | Quick path to pandas |

The performance gap between Drop-in and Native grows with column count, because the tuple conversion cost scales linearly with the number of cells. See [Benchmarks](benchmarks.md) for details.

## Connecting

### Basic Connection

```python
conn = jaydebeapiarrow.connect(
    "org.postgresql.Driver",          # JDBC driver class name
    "jdbc:postgresql://host:5432/db", # JDBC connection URL
    ["user", "password"],             # credentials (list or dict)
    "/path/to/pgjdbc.jar"             # driver JAR path(s)
)
```

### Connection Properties (Dict)

```python
conn = jaydebeapiarrow.connect(
    "org.postgresql.Driver",
    "jdbc:postgresql://host:5432/db",
    {
        "user": "user",
        "password": "password",
        "ssl": "true",
        "loginTimeout": "10"
    },
    "/path/to/pgjdbc.jar"
)
```

### Context Manager

```python
with jaydebeapiarrow.connect(
    "org.hsqldb.jdbcDriver",
    "jdbc:hsqldb:mem:.",
    ["SA", ""],
    "/path/to/hsqldb.jar"
) as conn:
    with conn.cursor() as curs:
        curs.execute("SELECT * FROM customers")
        print(curs.fetchall())
```

### `connect()` Parameters

| Parameter | Type | Description |
|---|---|---|
| `jclassname` | `str` | Fully-qualified Java driver class name |
| `url` | `str` | JDBC connection URL |
| `driver_args` | `list` or `dict` or `None` | `[user, password]` or connection properties dict |
| `jars` | `str` or `list[str]` or `None` | Path(s) to JDBC driver JAR(s) |
| `libs` | `str` or `list[str]` or `None` | Path(s) to native libraries |

## Cursor Methods

### Standard DB-API 2.0

```python
curs = conn.cursor()

# Execute queries
curs.execute("SELECT * FROM users WHERE age > %s", (25,))
curs.execute("INSERT INTO users (name, age) VALUES (?, ?)", ("Alice", 30))

# Batch inserts
curs.executemany(
    "INSERT INTO users (name, age) VALUES (?, ?)",
    [("Bob", 25), ("Carol", 28), ("Dave", 32)]
)

# Fetch results
row = curs.fetchone()          # single tuple or None
rows = curs.fetchmany(100)     # list of tuples
all_rows = curs.fetchall()     # all remaining rows
```

### Arrow-Specific Methods

```python
# Zero-copy Arrow record batches
for batch in curs.fetch_arrow_batches():
    print(batch.num_rows)
    # batch is a pyarrow.RecordBatch

# Single Arrow table (concatenates all batches)
table = curs.fetch_arrow_table()
# table is a pyarrow.Table

# Direct to pandas DataFrame
df = curs.fetch_df()
# df is a pandas.DataFrame
```

## Parameter Binding

Supported Python types for query parameters:

| Python Type | JDBC Type | Example |
|---|---|---|
| `str` | `VARCHAR` | `"hello"` |
| `int` | `INTEGER` | `42` |
| `float` | `DOUBLE` | `3.14` |
| `bool` | `BOOLEAN` | `True` |
| `decimal.Decimal` | `DECIMAL` | `Decimal("10.50")` |
| `datetime.datetime` | `TIMESTAMP` | `datetime(2024, 1, 15, 10, 30)` |
| `datetime.date` | `DATE` | `date(2024, 1, 15)` |
| `datetime.time` | `TIME` | `time(10, 30, 0)` |
| `bytes` | `BINARY` | `b"\x00\x01\x02"` |
| `None` | `NULL` | `None` |

!!! warning "Unsupported: list/array parameters"
    Passing a `list` as a parameter raises `NotSupportedError`. Use database-specific array functions (e.g., `UNNEST(ARRAY[...])` for PostgreSQL) instead.

## Connection Management

```python
# Transactions (autocommit is off by default)
conn.commit()
conn.rollback()

# Close connection
conn.close()

# Connection info
print(conn.jconn)           # underlying Java Connection object
```

## Experimental Features

### Dynamic Classpath Loading

By default, JPype's classpath is immutable after the JVM starts — you can only load JDBC drivers that were available at JVM startup time. This is a problem for forked processes (e.g., gunicorn workers) that need to connect to different databases.

The `experimental={'dynamic_classpath': True}` flag works around this using the **DriverShim pattern**: new JARs are loaded via Java's `URLClassLoader`, and a shim proxy is registered with `DriverManager` to delegate to the dynamically loaded driver.

```python
conn = jaydebeapiarrow.connect(
    "org.postgresql.Driver",
    "jdbc:postgresql://host:5432/db",
    ["user", "password"],
    "/path/to/pgjdbc.jar",
    experimental={"dynamic_classpath": True}
)
```

This also bypasses the fork-after-JVM-start guard, allowing connections in forked workers.

!!! warning "Experimental"
    This feature is experimental and may change in future versions.

## Debugging

Enable Java-level debug logging from the JDBC bridge:

```python
import jaydebeapiarrow
jaydebeapiarrow.set_debug(True)

# Now connect and run queries — Java JUL debug messages will appear in stderr
```

## Supported Databases

Any database with a JDBC driver should work. Confirmed compatibility:

| Database | Driver Class |
|---|---|
| PostgreSQL | `org.postgresql.Driver` |
| MySQL | `com.mysql.cj.jdbc.Driver` |
| SQLite (Xerial) | `org.sqlite.JDBC` |
| Oracle | `oracle.jdbc.OracleDriver` |
| SQL Server | `com.microsoft.sqlserver.jdbc.SQLServerDriver` |
| DB2 | `com.ibm.db2.jcc.DB2Driver` |
| HSQLDB | `org.hsqldb.jdbcDriver` |
| Teradata | `com.teradata.jdbc.TeraDriver` |
| Netezza | `org.netezza.Driver` |
| Mimer SQL | `com.mimer.jdbc.Driver` |

## Troubleshooting

### JAVA_HOME not set

```
RuntimeError: Unable to start JVM
```

Set the `JAVA_HOME` environment variable:

```bash
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk
```

### JVM already started (fork issue)

```
RuntimeError: JVM cannot be restarted after fork
```

Use `gunicorn --preload` with lazy connections, or enable dynamic classpath:

```python
conn = jaydebeapiarrow.connect(
    "org.postgresql.Driver",
    "jdbc:postgresql://host:5432/db",
    ["user", "password"],
    "/path/to/pgjdbc.jar",
    experimental={"dynamic_classpath": True}
)
```

### Non-ASCII characters garbled

Add JVM encoding argument or set environment variable:

```bash
JAVA_TOOL_OPTIONS="-Dfile.encoding=UTF-8" python your_script.py
```
