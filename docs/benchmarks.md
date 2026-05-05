# Benchmarks

## Overview

JayDeBeApiArrow's Arrow fast path avoids the row-by-row JPype serialization overhead that plagues the original jaydebeapi. Instead, JDBC data is converted to Arrow record batches in-JVM and streamed to Python in bulk.

## Methodology

- **Database**: PostgreSQL (local, same machine)
- **Default workload**: 5 million rows, 4 columns (INTEGER, VARCHAR, DOUBLE, TIMESTAMP)
- **Variants tested**:
  - Variable rows: 1M, 5M, 10M rows (4 columns fixed)
  - Variable columns: 4, 20, 40 columns (1M rows fixed)
- **Baseline**: Original jaydebeapi (row-by-row JPype iteration)
- **Reference**: psycopg2 native PostgreSQL driver

All measurements include connection setup and query execution. Each method was run multiple times; median times are reported.

## Results

### Variable Rows (4 columns)

| Method | 1M rows | 5M rows | 10M rows |
|---|---|---|---|
| jaydebeapi (baseline) | ~43s | ~199s | ~418s |
| Drop-in (`fetchall()`) | ~5.2s | ~26s | ~54s |
| Native Arrow API | ~2.2s | ~9.4s | ~19s |
| psycopg2 (native) | ~1.5s | ~7.3s | ~15s |

### 5M Rows Detail

| Method | Time | Throughput | vs jaydebeapi |
|---|---|---|---|
| jaydebeapi (baseline) | 198.66s | 25K rows/s | — |
| Drop-in replacement | 25.82s | 194K rows/s | 7.7x |
| Native Arrow API | 9.38s | 542K rows/s | **21.2x** |
| Psycopg2 (native driver) | 7.34s | 682K rows/s | 27x |

### Key Takeaways

- **Native Arrow API is ~21x faster** than jaydebeapi for 5M rows
- **Drop-in replacement** (using `fetchall()` after connecting via jaydebeapiarrow) still gives a 7.7x speedup, because the Arrow conversion happens in-JVM before JPype transfers the data
- **Arrow throughput approaches native driver performance** — psycopg2 is only 1.3x faster than the Arrow path, despite psycopg2 being a C extension communicating directly to PostgreSQL
- The **speedup increases with row count** — the fixed overhead of Arrow setup is amortized over larger datasets

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

- **[Uwe Korn — Fast JDBC access in Python using PyArrow.jvm](https://uwekorn.com/2019/11/17/fast-jdbc-access-in-python-using-pyarrow-jvm.html)** (2019) — Demonstrated 100x+ speedup using Arrow with Apache Drill
- **[Razvi Noorul — Trino JDBC access in Python using PyArrow.jvm](https://medium.com/@noorulrazvi/trino-jdbc-access-in-python-using-pyarrow-jvm-d1b75fe039ee)** — Similar approach with Trino

Both posts tested against distributed query engines (Drill, Trino) over network connections, which have much higher per-row JDBC overhead. PostgreSQL's JDBC driver is significantly faster at row retrieval, so the baseline is lower and the speedup multiplier is smaller (~21x vs 100x+). However, the absolute Arrow throughput is comparable across all three approaches.
