#!/bin/sh
# Runs inside the cluster (curlimages/curl), started by rollout-test.sh.
# Creates a link, then follows it in a loop for $DURATION seconds and counts
# every response that is not the expected redirect.
set -u

code=$(curl -fsS -X POST "$BASE/api/links" -H 'content-type: application/json' \
  -d '{"url": "https://example.com/rollout"}' | sed -E 's/.*"code":"([^"]+)".*/\1/')
[ -n "$code" ] || { echo "could not create a link"; exit 2; }
echo "load running against $BASE/$code"

end=$(( $(date +%s) + DURATION ))
ok=0
fail=0
while [ "$(date +%s)" -lt "$end" ]; do
  # curl exit codes tell failures apart: 7 refused (no pod listening), 28 timeout,
  # 6 name not resolved, 52/56 connection dropped mid-request.
  out=$(curl -s -o /dev/null --max-time 2 \
    -w '%{http_code} dns=%{time_namelookup}s connect=%{time_connect}s' "$BASE/$code")
  rc=$?
  if [ "$rc" -eq 0 ] && [ "${out%% *}" = "307" ]; then
    ok=$((ok + 1))
  else
    fail=$((fail + 1))
    echo "$(date +%T) failed: curl_exit=$rc status=$out"
  fi
  sleep 0.05
done

echo "requests ok=$ok failed=$fail"
[ "$fail" -eq 0 ]
