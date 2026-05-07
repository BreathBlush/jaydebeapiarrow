#!/bin/bash
# Configure Drill dfs.tmp workspace with parquet as default format.
# Without this, CTAS fails on empty directories with
# "No default format is set on the queried workspace".
set -e

DRILL_URL="${DRILL_URL:-http://localhost:18047}"

# Wait for Drill REST API to be ready
for i in $(seq 1 30); do
    if curl -sf "$DRILL_URL/storage.json" >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

# Get current dfs config, patch defaultInputFormat, and post back
curl -sf "$DRILL_URL/storage/dfs.json" | \
  python3 -c "
import json, sys
config = json.load(sys.stdin)
config['config']['workspaces']['tmp']['defaultInputFormat'] = 'parquet'
json.dump(config, sys.stdout)
" | curl -sf -X POST -H 'Content-Type: application/json' -d @- "$DRILL_URL/storage/dfs.json" >/dev/null
