#!/usr/bin/env bash
# Download the latest Firestore study data, aggregate it, and write report.md.
# Replaces study-exports/ and study-results/ so they always hold the latest data;
# a failed download or aggregation leaves the previous folders untouched.
# Usage: scripts/study-report.sh [PROJECT_ID]   (requires `gcloud auth login` first)
set -euo pipefail
project="${1:-intentional-1c8bd}"
cd "$(dirname "$0")/.."
exports=study-exports.new
results=study-results.new
trap 'rm -rf "$exports" "$results"' EXIT
rm -rf "$exports" "$results"
python3 scripts/download-study.py --project "$project" --output "$exports"
python3 scripts/aggregate-study.py "$exports" --output "$results"
rm -rf study-exports study-results
mv "$exports" study-exports
mv "$results" study-results
python3 scripts/report-study.py study-results
