#!/usr/bin/env bash
# Zero-downtime check: keeps requesting the Service from inside the cluster, through
# kube-proxy like real traffic, while a rolling update replaces every pod. A single
# failed request fails the test. (kubectl port-forward cannot do this: it pins one
# pod and breaks when that pod goes away.)
# Usage: scripts/rollout-test.sh [release] [chart]
set -euo pipefail

RELEASE="${1:-kurz}"
CHART="${2:-deploy/helm/kurz}"
DURATION="${DURATION:-90}"
POD=rollout-load

kubectl delete pod "$POD" --ignore-not-found >/dev/null
kubectl run "$POD" --image=curlimages/curl:8.11.1 --restart=Never \
  --env="BASE=http://$RELEASE" --env="DURATION=$DURATION" \
  --command -- sh -c "$(cat "$(dirname "$0")/rollout-load.sh")"

for _ in $(seq 1 60); do
  kubectl logs "$POD" 2>/dev/null | grep -q "load running" && break
  sleep 1
done
kubectl logs "$POD" | grep -q "load running" || { kubectl logs "$POD" || true; echo "FAIL: load did not start"; exit 1; }

start=$(date +%s)
# A changed pod annotation makes Kubernetes replace every pod.
helm upgrade "$RELEASE" "$CHART" --reuse-values \
  --set-string "podAnnotations.rolloutTest=$start" --wait --timeout 3m
kubectl rollout status "deployment/$RELEASE" --timeout=2m
took=$(( $(date +%s) - start ))
echo "rollout took ${took}s"
if [ "$took" -ge $((DURATION - 10)) ]; then
  echo "FAIL: the rollout outlasted the load window; raise DURATION"
  exit 1
fi

phase=""
for _ in $(seq 1 $((DURATION + 30))); do
  phase=$(kubectl get pod "$POD" -o jsonpath='{.status.phase}')
  [ "$phase" = Succeeded ] || [ "$phase" = Failed ] && break
  sleep 1
done
kubectl logs "$POD" | tail -n 25
kubectl delete pod "$POD" --wait=false >/dev/null

[ "$phase" = Succeeded ] || { echo "FAIL: requests failed during the rollout"; exit 1; }
echo "zero-downtime rollout passed"
