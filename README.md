# 7-Day Kubernetes Observability Lab — no cloud account required

Learn metrics, PromQL, dashboards, application instrumentation, alerting, centralized
logging, distributed tracing, and OpenTelemetry on a **local kind Kubernetes cluster**.
The AWS infrastructure has been replaced; the observability learning objectives remain.

## Start here

Read [the local setup, requirements and acceptance checks](local/README.md).
Install Docker Engine (or a suitable Docker Desktop installation), kind, kubectl,
Helm 3 and Bash. On Windows, run the commands inside WSL2 with Linux containers.
Run these commands from the repository root, in order:

```bash
bash local/lab.sh cluster
bash local/lab.sh monitoring
bash local/lab.sh node-app
bash local/lab.sh logging
bash local/lab.sh tracing
bash local/lab.sh otel
bash local/lab.sh status
```

Install one lesson at a time rather than deploying everything immediately on a small machine.
The scripts target **kind-observability explicitly**, not your current Kubernetes context.
Application images are built locally and loaded into kind; no image-registry account is needed.

## The seven days

| Day | Goal | Tools and exercises |
| --- | --- | --- |
| [1](day-1/readme.md) | Observability fundamentals | Monitoring versus observability; metrics, logs and traces |
| [2](day-2/readme.md) | Kubernetes monitoring | Prometheus, Grafana, kube-prometheus-stack |
| [3](day-3/readme.md) | Query metrics | PromQL selectors, aggregation, rates and quantiles |
| [4](day-4/readme.md) | Instrument applications and alert | Node.js, prom-client, ServiceMonitor, PrometheusRule, Alertmanager |
| [5](day-5/readme.md) | Centralize logs | Elasticsearch, Fluent Bit, Kibana |
| [6](day-6/readme.md) | Trace distributed requests | OpenTelemetry-instrumented Node.js services and Jaeger |
| [7](day-7/README.md) | Collect telemetry through OpenTelemetry | Go microservices, OTLP Collector, Prometheus, shared Jaeger and logging |

## What changed

EKS/EC2 → kind nodes; EBS → the local `standard` StorageClass; cloud load balancers
and ALB → ClusterIP Services plus localhost port-forwarding; registry pushes →
`kind load docker-image`. No IAM roles, AWS CLI, paid Kubernetes control plane, or
public dashboard endpoint is part of the default path.

**Free here means no cloud infrastructure bill on hardware you already own.**
CPU, RAM, disk, power and internet are still required. This is not free hosted or
highly available Kubernetes. PVCs survive pod restarts, but deleting kind deletes
its local data. Existing AWS infrastructure is not decommissioned by these changes.

This migration preserves the original Elastic and Jaeger v1 lesson compatibility;
those are legacy dependencies, not a production/security baseline. Version pins,
resource estimates, limitations and validation instructions are in [local/README.md](local/README.md).
The optional `opensearch-stack/` examples are separate from the seven-day path;
no hosted OpenSearch service is required. eBPF tooling is not required by this lab.
