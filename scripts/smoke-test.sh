#!/usr/bin/env bash
# End-to-end check against a running instance: create a link, follow it, read its stats.
# Usage: scripts/smoke-test.sh [base-url]
set -euo pipefail

BASE="${1:-http://localhost:8000}"
fail() { echo "FAIL: $*" >&2; exit 1; }

echo "waiting for $BASE ..."
for _ in $(seq 1 30); do
  curl -fsS "$BASE/readyz" >/dev/null 2>&1 && break
  sleep 2
done
curl -fsS "$BASE/readyz" >/dev/null || fail "not ready"

target="https://example.com/smoke-$RANDOM"
code=$(curl -fsS -X POST "$BASE/api/links" \
  -H 'content-type: application/json' \
  -d "{\"url\": \"$target\"}" | jq -r .code)
[ -n "$code" ] && [ "$code" != "null" ] || fail "no code returned"
echo "created /$code -> $target"

location=$(curl -sS -o /dev/null -w '%{redirect_url}' "$BASE/$code")
[ "$location" = "$target" ] || fail "redirect went to '$location'"

clicks=$(curl -fsS "$BASE/api/links/$code" | jq .clicks)
[ "$clicks" = "1" ] || fail "expected 1 click, got $clicks"

curl -fsS "$BASE/metrics" | grep -q '^kurz_links_created_total' || fail "metric missing"

echo "smoke test passed"
