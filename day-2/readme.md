# Day 2 — Monitoring with Prometheus and Grafana

Metrics are measurements; monitoring observes those measurements over time to detect
changes and problems. Prometheus discovers targets, scrapes their HTTP metrics,
stores time series in its TSDB, and exposes PromQL queries. Exporters provide metrics
for systems that do not expose them themselves. Alerting rules send active alerts to
Alertmanager, which groups, deduplicates and routes notifications. Grafana visualizes
Prometheus data. A Pushgateway can support suitable short-lived batch-job use cases.

![Prometheus architecture](images/prometheus-architecture.gif)

## Install on free local Kubernetes

Follow [local prerequisites](../local/README.md), then run from the repository root:

```bash
bash local/lab.sh cluster
bash local/lab.sh monitoring
kubectl --context kind-observability get pods,pvc -n monitoring
```

This installs the pinned kube-prometheus-stack chart with
`custom_kube_prometheus_stack.yml`: Prometheus, Grafana, Alertmanager, the operator,
node exporter and kube-state-metrics. Kubernetes discovery, kubelet/cAdvisor and API
server monitoring remain. No cloud-provider identity, node group or public endpoint
is needed. Local-only inaccessible control-plane scrape targets are disabled.

## Explore

Use the [localhost access commands](../local/README.md#access-from-your-own-computer):
Prometheus on 9090, Grafana on 3000 and Alertmanager on 9093. Retrieve Grafana's
generated password from the `monitoring-grafana` Secret. Inspect Targets, query `up`,
then compare pod/node dashboards in Grafana. Continue to [Day 3](../day-3/readme.md)
for PromQL selectors, rates, aggregation and quantiles.

The lab uses one replica per main component and local PVCs; this is not an HA setup.
Keep monitoring installed for Day 4's ServiceMonitor and PrometheusRule resources.

## Cleanup

Uninstall just monitoring only after finishing dependent exercises:

```bash
helm --kube-context kind-observability uninstall monitoring -n monitoring
```

PVCs may remain after Helm uninstall. Inspect them before deleting anything.
Full destructive lab cleanup is documented in [local/README.md](../local/README.md#checks-and-cleanup).
