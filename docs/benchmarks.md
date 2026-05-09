# Benchmarks

## Overview

JayDeBeApiArrow's Arrow fast path avoids the row-by-row JPype serialization overhead that plagues the original jaydebeapi. Instead, JDBC data is converted to Arrow record batches in-JVM and exported to Python via the Arrow **C Data Interface**, bypassing `pyarrow.jvm` entirely.

## Methodology

- **Database**: PostgreSQL (local, same machine)
- **Default workload**: 5 million rows, 4 columns (INTEGER, VARCHAR, DOUBLE, TIMESTAMP)
- **Baseline**: Original jaydebeapi (row-by-row JPype iteration)
- **Reference**: psycopg2 native PostgreSQL driver

All measurements include connection setup and query execution. Each method was run multiple times; median times are reported.

## Results

### 5M Rows, 4 Columns

| Method | Time | Throughput | vs jaydebeapi |
|---|---|---|---|
| jaydebeapi (baseline) | 180.1s | 28K rows/s | - |
| Drop-in replacement | 26.5s | 189K rows/s | 6.8x |
| Native Arrow API (C Data Interface) | 7.6s | 658K rows/s | **23.7x** |
| Psycopg2 (native driver) | 7.2s | 694K rows/s | 25.0x |

### Key Takeaways

- **Native Arrow API is ~23.7x faster** than jaydebeapi for 5M rows using the C Data Interface
- **Drop-in replacement** (using `fetchall()`) still gives a 6.8x speedup, because the Arrow conversion happens in-JVM before JPype transfers the data
- **Arrow throughput is within 6% of a native C driver** - psycopg2 is only marginally faster despite being a C extension communicating directly to PostgreSQL
- The **speedup increases with row count** - the fixed overhead of Arrow setup is amortized over larger datasets

## How to Reproduce

The benchmark suite is in the `benchmark/` directory:

```bash
# Prepare test data (creates a PostgreSQL table with N rows)
uv run python benchmark/prepare_data.py --rows 5000000

# Run the comparison benchmark
uv run python benchmark/compare_performance.py --rows 5000000

# Analyze results
uv run python benchmark/analyze_results.py
```

### Prerequisites

- PostgreSQL instance with the `pgjdbc` driver
- The `jaydebeapi` package installed (for baseline comparison)
- `psycopg2` installed (for native driver reference)

## Prior Art

This approach was inspired by:

- **[Uwe Korn - Fast JDBC access in Python using PyArrow.jvm](https://uwekorn.com/2019/11/17/fast-jdbc-access-in-python-using-pyarrow-jvm.html)** (2019) - Demonstrated 100x+ speedup using Arrow with Apache Drill
- **[Razvi Noorul - Trino JDBC access in Python using PyArrow.jvm](https://medium.com/@noorulrazvi/trino-jdbc-access-in-python-using-pyarrow-jvm-d1b75fe039ee)** - Similar approach with Trino

Both posts tested against distributed query engines (Drill, Trino) over network connections, which have much higher per-row JDBC overhead. PostgreSQL's JDBC driver is significantly faster at row retrieval, so the baseline is lower and the speedup multiplier is smaller (~24x vs 100x+). However, the absolute Arrow throughput is comparable across all three approaches.
