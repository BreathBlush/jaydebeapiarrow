## Ways of Working
Use `uv run` to run Python scripts and tests — it automatically manages the virtual environment.
- `uv sync` to install/sync dependencies
- `uv run bash test/build.sh` to build JARs
- `uv run pytest test/ -v` to run all tests via pytest
- `uv run pytest test/test_postgres.py -v` to run a specific driver's tests
- `uv run pytest test/ -k "test_execute_and_fetch" -v` to run specific tests by name
- `CLASSPATH` is set automatically by tox; for local runs set it to `test/jars/*:test/mock-jars/*`


## Speical Requirements in YOLO Mode

When in YOLO mode, i.e., when all user approvals are skipped, you should not execute any commands outside of the current working directory. Also please follow the agile development practice:

1. When tests are available, always run tests before calling a task done
2. After all development for a task is finished, use `gh` (GitHub CLI) to create a pull request for this feature branch with a concise summary of what you've done
