# Day 6 — Distributed tracing with Jaeger

A **trace** follows a request across services; each **span** describes one operation,
its timing and attributes. Parent/child relationships and context propagation connect
spans across process boundaries. Use traces to locate slow dependencies and explain
failed requests instead of examining isolated log lines only.

![Tracing architecture](images/architecture.gif)

The Node services are instrumented in `day-4/application/*/tracing.js`. They send
traces to Jaeger's collector. Jaeger's query service reads stored traces and serves
the UI. Elasticsearch from Day 5 remains the persistent backing store.

## Install

After `logging` and `node-app`, run from the repository root:

```bash
bash local/lab.sh tracing
kubectl --context kind-observability -n tracing get pods,svc
kubectl --context kind-observability -n tracing port-forward --address 127.0.0.1 svc/jaeger-query 16686:80
```

The installer copies the Elasticsearch CA and credential to Kubernetes Secrets in
`tracing`; no password needs to be pasted into Git. `jaeger-values.yaml` refers to
those Secrets. It disables provisioning additional datastores and retains HTTP
Thrift input for the existing Node instrumentation plus OTLP for Day 7.

## Inspect a distributed request

With the Day 4 service port-forward running:

```bash
curl --fail http://127.0.0.1:3001/call-service-b
```

Open `http://127.0.0.1:16686`, select `service-a`, choose a recent time window and
find the request. Expand the trace and inspect the service B span, duration and
HTTP attributes. Pod readiness alone does not establish successful trace delivery.
For missing traces, check the exporter endpoint, collector logs and Elasticsearch
credentials. Re-run `tracing` after changing the datastore password/certificate.

## Compatibility and cleanup

This migration pins the existing Jaeger v1 Helm integration rather than changing the
application's tracing APIs. That legacy dependency needs a separate upgrade/security
review before non-lab use. Storage is persistent within the disposable kind cluster,
not a backup or highly available service. Day 7 reuses this same Jaeger instance.

Uninstall only tracing with:

```bash
helm --kube-context kind-observability uninstall jaeger -n tracing
```

Do not delete the shared Elasticsearch datastore while later exercises still use it.
