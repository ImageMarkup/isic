#!/usr/bin/env bash
#
# Build a sanitized local database from production.
#
# Pulls the read-only credential's URL from Heroku, dumps production through
# greenmask (which anonymizes info and subsets the data per config.yml), then
# restores it into the local postgres.
#
# If DATABASE_URL is already set in the environment, it's used as-is and the
# Heroku lookup is skipped. This is what the CI test relies on to dump against a
# throwaway local database instead of production.
#
# Usage:
#   dev/greenmask-dump.sh                          dump from prod, then restore
#   dev/greenmask-dump.sh -r|--reuse-existing-dump restore the latest local dump
#                                                  only (skips Heroku + dump)
#   dev/greenmask-dump.sh -d|--dump-only           dump only, skip the restore
set -exuo pipefail

REUSE_EXISTING_DUMP=0
DUMP_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
  -r | --reuse-existing-dump)
    REUSE_EXISTING_DUMP=1
    shift
    ;;
  -d | --dump-only)
    DUMP_ONLY=1
    shift
    ;;
  *)
    echo "unknown argument: $1" >&2
    exit 1
    ;;
  esac
done

if [[ "$REUSE_EXISTING_DUMP" -eq 1 && "$DUMP_ONLY" -eq 1 ]]; then
  echo "-r/--reuse-existing-dump and -d/--dump-only are mutually exclusive" >&2
  exit 1
fi

declare -rx HEROKU_APP=isic
declare -rx HEROKU_PG_CREDENTIAL=readonly
# Lowering this barely speeds up the dump: ~75s of the runtime is fixed
# server-side full scans (ingest_metadataversion, ingest_unstructuredmetadata,
# ingest_accession) from non-sargable modulo subset predicates, plus ~22s of
# pg_dump --schema-only startup -- none of which shrink with the percentage.
# Raising it does cost more, though: the download-bound tables (mainly the
# core_imageembedding halfvecs) scale ~linearly with the percentage.
declare -rx ACCESSION_SUBSET_PERCENT=10

readonly LOG_LEVEL=info

# greenmask's directory storage won't create the path for you, so make sure it
# exists before dumping.
mkdir -p ./.greenmask/dumps

if [[ "$REUSE_EXISTING_DUMP" -eq 0 ]]; then
  if [[ -z "${DATABASE_URL:-}" ]]; then
    DATABASE_URL=$(heroku pg:credentials:url --name "$HEROKU_PG_CREDENTIAL" |
      grep -Eo 'postgres://[^[:space:]]+')
    export DATABASE_URL
  fi
  greenmask --config .greenmask/config.yml dump --jobs 2 --pgzip --log-level "$LOG_LEVEL"
fi

if [[ "$DUMP_ONLY" -eq 1 ]]; then
  exit 0
fi

# Filter out greenmask's expected-but-noisy phased-restoration warnings without
# swallowing greenmask's exit code (process substitution, not a pipe, so
# pipefail can't mask a real greenmask failure).
readonly NOISE='could not find where to insert IF EXISTS|using neutralized TOC for phased restoration'

greenmask --config .greenmask/config.yml --log-level "$LOG_LEVEL" restore latest --pgzip \
  2> >(grep -v -E "$NOISE" >&2)
