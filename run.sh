#!/usr/bin/env bash
# run.sh — OPERA water-mask (DPS)
set -euo pipefail

basedir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PY='conda run --live-stream -p /opt/conda/envs/subset_watermask_cog python'

# Always write products into ./output (relative to DPS working dir)
mkdir -p output

# ---- DPS positional inputs --------------------------------------------------
# 1 SHORT_NAME, 2 TEMPORAL, 3 BBOX, 4 LIMIT, 5 GRANULE_UR, 6 IDX_WINDOW, 7 S3_URL
SHORT_NAME="${1:-}"
TEMPORAL="${2:-}"
BBOX="${3:-}"
LIMIT="${4:-}"
GRANULE_UR="${5:-}"
IDX_WINDOW="${6:-}"
S3_URL="${7:-}"

# ---- Build CLI for Python ---------------------------------------------------
ARGS=()
[[ -n "${SHORT_NAME}" ]] || SHORT_NAME="OPERA_L3_DISP-S1_V1"
ARGS+=("--short-name" "${SHORT_NAME}")

[[ -n "${TEMPORAL}"   ]] && ARGS+=("--temporal" "${TEMPORAL}")
[[ -n "${BBOX}"       ]] && ARGS+=("--bbox" "${BBOX}")
[[ -n "${LIMIT}"      ]] && ARGS+=("--limit" "${LIMIT}")
[[ -n "${GRANULE_UR}" ]] && ARGS+=("--granule-ur" "${GRANULE_UR}")
[[ -n "${IDX_WINDOW}" ]] && ARGS+=("--idx-window" "${IDX_WINDOW}")
[[ -n "${S3_URL}"     ]] && ARGS+=("--s3-url" "${S3_URL}")


ARGS+=("--dest" "output")

# ---- Run & capture stderr to triage -----------------------------------------
logfile="_opera-watermask.log"
set -x
${PY} "${basedir}/water_mask_to_cog.py" "${ARGS[@]}" 2>"${logfile}"
# Include stdio + log in products
cp -v _stderr.txt _stdout.txt output/ 2>/dev/null || true
mv -v "${logfile}" output/
set +x
