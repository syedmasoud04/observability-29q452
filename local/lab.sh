#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# All cluster operations are explicitly scoped; never deploy to the current context.
CLUSTER=observability
CONTEXT=kind-observability
export KIND_EXPERIMENTAL_PROVIDER=docker
source "$ROOT/local/versions.env"
k() { kubectl --context "$CONTEXT" "$@"; }
h() { helm --kube-context "$CONTEXT" "$@"; }
need() { command -v "$1" >/dev/null || { echo "Missing prerequisite: $1" >&2; exit 1; }; }
ns() { k create namespace "$1" --dry-run=client -o yaml | k apply -f -; }
repo() { helm repo add "$1" "$2" --force-update; helm repo update "$1"; }
usage() {
  echo "Usage: bash local/lab.sh {cluster|monitoring|node-app|logging|tracing|otel|status|delete --confirm-delete}"
}
command="${1:-help}"
case "$command" in
  help|-h|--help) usage; exit 0 ;;
  cluster|monitoring|node-app|logging|tracing|otel|status) ;;
  delete)
    if [[ "${2:-}" != --confirm-delete ]]; then
      echo "Deletion erases this kind cluster and its local volumes. Add --confirm-delete." >&2
      exit 2
    fi
    need kind; need docker
    kind delete cluster --name "$CLUSTER"
    exit 0 ;;
  *) usage >&2; exit 2 ;;
esac
need docker; need kind; need kubectl
# Fail before changing resources when the container runtime is unavailable.
docker info >/dev/null
if [[ "$command" == cluster ]]; then
  if ! kind get clusters | grep -Fxq "$CLUSTER"; then
    kind create cluster --name "$CLUSTER" --config "$ROOT/local/kind.yaml" --wait 180s
  else
    kind export kubeconfig --name "$CLUSTER"
  fi
  k wait --for=condition=Ready nodes --all --timeout=180s
  k rollout status deployment/local-path-provisioner -n local-path-storage --timeout=180s
  provisioner="$(k get storageclass standard -o jsonpath='{.provisioner}')"
  [[ "$provisioner" == rancher.io/local-path ]] || {
    echo "Expected kind's standard local-path StorageClass, found: $provisioner" >&2; exit 1;
  }
  k get nodes
  exit 0
fi
kind get clusters | grep -Fxq "$CLUSTER" || {
  echo "Create the local cluster first: bash local/lab.sh cluster" >&2; exit 1;
}
k cluster-info >/dev/null
if [[ "$command" == status ]]; then
  k get pods -A
  k get pvc -A
  exit 0
fi
need helm
case "$command" in
  monitoring)
    repo prometheus-community https://prometheus-community.github.io/helm-charts
    h upgrade --install monitoring prometheus-community/kube-prometheus-stack \
      --version "$MONITORING_CHART_VERSION" -n monitoring --create-namespace \
      -f "$ROOT/day-2/custom_kube_prometheus_stack.yml" --wait --timeout 15m
    ;;
  node-app)
    k get crd servicemonitors.monitoring.coreos.com >/dev/null
    for service in a b; do
      docker build -t "observability/service-$service:local" "$ROOT/day-4/application/service-$service"
      kind load docker-image "observability/service-$service:local" --name "$CLUSTER"
    done
    ns dev
    k apply -k "$ROOT/day-4/kubernetes-manifest"
    for service in a b; do
      k rollout restart "deployment/service-$service-deployment" -n dev
      k rollout status "deployment/service-$service-deployment" -n dev --timeout=300s
    done
    # Alerts and scraping work without any SMTP credentials.
    k apply -f "$ROOT/day-4/alerts-alertmanager-servicemonitor-manifest/serviceMonitor.yml" \
      -f "$ROOT/day-4/alerts-alertmanager-servicemonitor-manifest/alerts.yml"
    ;;
  logging)
    repo elastic https://helm.elastic.co
    repo fluent https://fluent.github.io/helm-charts
    h upgrade --install elasticsearch elastic/elasticsearch --version "$ELASTIC_CHART_VERSION" \
      -n logging --create-namespace -f "$ROOT/local/elasticsearch-values.yaml" --wait --timeout 15m
    h upgrade --install kibana elastic/kibana --version "$ELASTIC_CHART_VERSION" \
      -n logging -f "$ROOT/local/kibana-values.yaml" --wait --timeout 15m
    h upgrade --install fluent-bit fluent/fluent-bit --version "$FLUENT_BIT_CHART_VERSION" \
      -n logging -f "$ROOT/day-5/fluentbit-values.yaml" --wait --timeout 10m
    ;;
  tracing)
    # Reuse the logging datastore: do not provision a second Elasticsearch cluster.
    need base64
    ns tracing
    umask 077
    TMP="$(mktemp -d)"
    trap 'rm -rf "$TMP"' EXIT
    k get secret elasticsearch-master-certs -n logging -o jsonpath='{.data.ca\.crt}' \
      | base64 -d > "$TMP/ca-cert.pem"
    k get secret elasticsearch-master-credentials -n logging -o jsonpath='{.data.password}' \
      | base64 -d > "$TMP/password"
    test -s "$TMP/ca-cert.pem" && test -s "$TMP/password"
    k create secret generic es-tls-secret -n tracing --from-file="ca-cert.pem=$TMP/ca-cert.pem" \
      --dry-run=client -o yaml | k apply -f -
    k create secret generic jaeger-es-credentials -n tracing --from-file="password=$TMP/password" \
      --dry-run=client -o yaml | k apply -f -
    repo jaegertracing https://jaegertracing.github.io/helm-charts
    h upgrade --install jaeger jaegertracing/jaeger --version "$JAEGER_CHART_VERSION" \
      -n tracing -f "$ROOT/day-6/jaeger-values.yaml" --wait --timeout 10m
    # Pick up copied credentials even when their Secret name has not changed.
    k rollout restart deployment -n tracing -l app.kubernetes.io/instance=jaeger
    k rollout status deployment -n tracing -l app.kubernetes.io/instance=jaeger --timeout=300s
    ;;
  otel)
    k get service jaeger-collector -n tracing >/dev/null
    repo open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
    repo prometheus-community https://prometheus-community.github.io/helm-charts
    h upgrade --install otel-collector open-telemetry/opentelemetry-collector \
      --version "$OTEL_CHART_VERSION" -n olly --create-namespace \
      -f "$ROOT/day-7/otel-collector-values.yaml" --wait --timeout 10m
    h upgrade --install prometheus prometheus-community/prometheus --version "$PROMETHEUS_CHART_VERSION" \
      -n olly -f "$ROOT/day-7/prometheus-values.yaml" --wait --timeout 10m
    for service in a b; do
      docker build -f "$ROOT/day-7/microservice-$service/dockerfile" \
        -t "observability/go-service-$service:local" "$ROOT/day-7/microservice-$service"
      kind load docker-image "observability/go-service-$service:local" --name "$CLUSTER"
    done
    k apply -k "$ROOT/day-7/k8s-manifests"
    for service in a b; do
      k rollout restart "deployment/go-service-$service-deployment" -n otel-demo
      k rollout status "deployment/go-service-$service-deployment" -n otel-demo --timeout=300s
    done
    ;;
esac
echo "Completed $command on $CONTEXT. See local/README.md for localhost access and checks."
