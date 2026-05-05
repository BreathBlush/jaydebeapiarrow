# Data Mapping

JayDeBeApiArrow converts JDBC data types through two stages: **JDBC to Arrow** (in the JVM) and **Arrow to Python** (on the Python side). This page documents the mapping and known limitations.

## Type Mapping Table

### Numeric Types

| JDBC Type | Arrow Type | Python Type | Notes |
|---|---|---|---|
| `INTEGER` | `Int32` | `int` | |
| `BIGINT` | `Int64` | `int` | |
| `SMALLINT` | `Int16` | `int` | |
| `TINYINT` | `Int8` | `int` | |
| `BOOLEAN` / `BIT` | `Boolean` | `bool` | |
| `FLOAT` / `REAL` | `Float32` | `float` | |
| `DOUBLE` | `Float64` | `float` | |
| `DECIMAL` / `NUMERIC` | `Decimal128` | `decimal.Decimal` | Full precision preserved |

### String Types

| JDBC Type | Arrow Type | Python Type | Notes |
|---|---|---|---|
| `VARCHAR` | `Utf8` | `str` | |
| `CHAR` / `NCHAR` | `Utf8` | `str` | |
| `NVARCHAR` | `Utf8` | `str` | |
| `LONGVARCHAR` / `LONGNVARCHAR` | `Utf8` | `str` | |
| `CLOB` / `NCLOB` | `Utf8` | `str` | |
| `OTHER` | `Utf8` | `str` | Fallback |

### Temporal Types

| JDBC Type | Arrow Type | Python Type | Notes |
|---|---|---|---|
| `DATE` | `Date32` | `datetime.date` | |
| `TIME` | `Time32` | `datetime.time` | |
| `TIME_WITH_TIMEZONE` | `Utf8` | `str` | Fallback — not natively supported by Arrow |
| `TIMESTAMP` | `Timestamp` | `datetime.datetime` | Naive (no timezone) |
| `TIMESTAMP_WITH_TIMEZONE` | `Timestamp(tz=UTC)` | `datetime.datetime` | Timezone-aware, UTC |

### Binary Types

| JDBC Type | Arrow Type | Python Type | Notes |
|---|---|---|---|
| `BINARY` | `Binary` | `bytes` / `memoryview` | |
| `VARBINARY` | `Binary` | `bytes` / `memoryview` | |
| `BLOB` | `Binary` | `bytes` / `memoryview` | |
| `LONGVARBINARY` | `Binary` | `bytes` / `memoryview` | |

### Special Types

| JDBC Type | Arrow Type | Python Type | Notes |
|---|---|---|---|
| `ARRAY` | `Utf8` | `str` | Fallback via `toString()` |
| `SQLXML` | `Utf8` | `str` | Fallback via `getString()` |
| `ROWID` | `Utf8` | `str` | Fallback |
| `JSON` / `JSONB` / `UUID` / `XML` | `Utf8` | `str` | Detected from type name when reported as `OTHER` |

## How Type Detection Works

The `ExplicitTypeMapper` in `arrow-jdbc-extension.jar` inspects `ResultSetMetaData` to build a per-column type mapping. It handles driver-specific quirks:

1. **Standard types** — JDBC type codes like `Types.INTEGER`, `Types.VARCHAR` are mapped directly
2. **Unknown type codes** — Some drivers use non-standard codes (e.g., Oracle `BINARY_DOUBLE` = 101). The mapper falls back to matching the column type *name* against known patterns
3. **Misreported types** — Some drivers misreport types (e.g., SQLite reports `TIME` as `VARCHAR`). The mapper detects these by comparing type code against type name

## Known Limitations

### Arrow-Unsupported Types

These types are **not natively supported** by the Arrow JDBC adapter. They are converted to `VARCHAR` as a degraded fallback:

- **`ARRAY`** — Returned as `toString()` representation. No native Arrow array type support. Parameter binding for lists raises `NotSupportedError`.
- **`SQLXML`** — Returned as string via `getString()`.
- **`ROWID`** — Returned as string.
- **`OTHER`** — Returned as string. Columns with type names containing `JSON`, `UUID`, or `XML` are auto-detected and mapped to `VARCHAR`.
- **`TIME_WITH_TIMEZONE`** — Not natively supported. Falls back to string representation.

### Driver-Specific Quirks

#### SQLite

- **TIME type**: SQLite JDBC reports `TIME` columns as `VARCHAR`. This is auto-detected and corrected.
- **NUMERIC/DECIMAL precision**: SQLite stores all numeric values as doubles internally, so precision information from `ResultSetMetaData` is unreliable.

#### Oracle

- **BINARY_DOUBLE**: Oracle JDBC reports this with type code 101 (non-standard). Auto-detected by type name matching.
- **TIMESTAMP WITH TIME ZONE**: Type code varies between `ojdbc8` (101) and `ojdbc11` (2013). Auto-detected by type name matching.
- **BIGINT**: Not supported natively by some Oracle JDBC driver versions.

#### PostgreSQL

- **TIMESTAMPTZ**: Reported as `Types.TIMESTAMP` by the PostgreSQL JDBC driver. Auto-detected by checking if the type name is `"timestamptz"` and overriding to `TIMESTAMP_WITH_TIMEZONE`.

### Fork Constraint

JPype does not support `fork()` after the JVM has started. This means:

- Processes that fork after importing jaydebeapiarrow (e.g., gunicorn without `--preload`) will crash
- The workaround is to use `gunicorn --preload` with lazy connections, or enable `experimental={'dynamic_classpath': True}`

### Parameter Binding

| Python Type | Supported | Notes |
|---|---|---|
| `str`, `int`, `float`, `bool` | Yes | Standard JDBC types |
| `decimal.Decimal` | Yes | Preserved as Java `BigDecimal` |
| `datetime.datetime` | Yes | Converted to `java.sql.Timestamp` |
| `datetime.date` | Yes | Converted to `java.sql.Date` |
| `datetime.time` | Yes | Converted to `java.sql.Time` |
| `bytes`, `bytearray` | Yes | Converted to Java `byte[]` |
| `None` | Yes | Passed as SQL `NULL` |
| `list` | No | Raises `NotSupportedError` |

## Comparison with Parent JayDeBeApi

| Column Type | Parent (jaydebeapi) | Fork (jaydebeapiarrow) |
|---|---|---|
| `TIMESTAMP` | `str` | `datetime.datetime` (naive) |
| `TIME` | `str` | `datetime.time` |
| `DATE` | `str` | `datetime.date` |
| `DECIMAL` / `NUMERIC` | `float` / `int` | `decimal.Decimal` (full precision) |
| `BINARY` | `str` | `bytes` / `memoryview` |
| `TIMESTAMP_WITH_TIMEZONE` | Raw Java object | `datetime.datetime` (timezone-aware) |

See [Differences](differences.md) for the full list of changes from the parent project.
