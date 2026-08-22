#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GOCACHE=/tmp/gocache GO111MODULE=off GOPATH=/tmp/gopath

# --- Step 1: rebuild the authoritative inventory positions (#MRP-4170) ------
# The rollout left /app/data/inventory_positions.json holding a truncated prefix.
# Replay the movement journal onto the pre-rollout snapshot and write the result
# back to that path; nothing the planner emits is correct until this is done.

cp "${SCRIPT_DIR}/recover_positions.go" /app/workflow/recover_positions.go
go run /app/workflow/recover_positions.go

# --- Step 2: restore the planner and produce the plan artifacts -------------

cp "${SCRIPT_DIR}/plan_requirements_fixed.go" /app/workflow/plan_requirements.go
go run /app/workflow/plan_requirements.go --output-dir /app/output
