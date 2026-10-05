# Day 7 — OpenTelemetry on local Kubernetes

OpenTelemetry standardizes how applications generate and transport telemetry. The
Collector separates application instrumentation from backend-specific exporters.
The Go examples use Gin and OpenTelemetry instrumentation, including context
propagation on outgoing HTTP calls. Inspect each `microservice-*/main.go` file.

## Architecture

```text
Go service A <----HTTP + trace context----> Go service B   [otel-demo]
          | OTLP HTTP traces and metrics
          v
    OpenTelemetry Collector                            [olly]
          | metrics :8889       | OTLP traces
          v                     v
       Prometheus          shared Jaeger               [tracing]
                                  |
container stdout --> Fluent Bit --+--> Elasticsearch    [logging]
                                             |
                                           Kibana
```

The application logs go through stdout and Fluent Bit; the Go code does not implement
an OTLP Logs SDK. The Collector also accepts optional OTLP logs and emits them to
stdout for the same logging pipeline. This distinction avoids claiming telemetry
instrumentation the application does not contain.

## Deploy

From the repository root, after creating the local cluster:

```bash
# Skip stages already installed; do not create another cloud or local cluster.
bash local/lab.sh logging
bash local/lab.sh tracing
bash local/lab.sh otel
kubectl --context kind-observability -n olly get pods,pvc,svc
kubectl --context kind-observability -n otel-demo get pods,svc
```

`otel` builds both Go images using their lowercase `dockerfile`, loads them into kind,
installs the pinned Collector and Prometheus charts, and deploys the examples.
The Go applications use `otel-demo`, so their `a-service` and `b-service` names do not
overwrite the Node Services in `dev`. The Collector has no hostPort reservations;
all traffic uses ClusterIP Services and Kubernetes DNS.

Tracing reuses `jaeger-collector.tracing.svc:4317` and Elasticsearch in `logging`.
`jaeger-values.yaml` is a compatibility copy for that shared tracing release, not an
instruction to create a second Jaeger or Elasticsearch deployment in `olly`.

## Exercise cross-service calls

Use separate terminals:

```bash
kubectl --context kind-observability -n otel-demo port-forward --address 127.0.0.1 svc/a-service 8081:80
kubectl --context kind-observability -n otel-demo port-forward --address 127.0.0.1 svc/b-service 8082:80
kubectl --context kind-observability -n olly port-forward --address 127.0.0.1 svc/prometheus-server 9091:80
kubectl --context kind-observability -n tracing port-forward --address 127.0.0.1 svc/jaeger-query 16686:80
```

Then:

```bash
curl --fail http://127.0.0.1:8081/hello-a
curl --fail http://127.0.0.1:8081/call-b
curl --fail http://127.0.0.1:8082/call-a
bash day-7/test.sh http://127.0.0.1:8081 http://127.0.0.1:8082
```

The existing load script also calls `/getme-coffee`, which uses an external API;
that API is optional and can fail independently of the local lab. The hello/call
routes are sufficient for local validation. Stop the continuous script with Ctrl+C.

In Prometheus on 9091, verify `up{job="otel-collector"}` is 1 and find request count,
request duration and active request metrics. In Jaeger, select `microservice-a` or
`microservice-b` and inspect a cross-service trace. In Kibana, find `otel-demo` logs.
Metrics can have unit/type suffixes added by the Prometheus exporter.

## Cleanup

Remove just the Go applications and their dedicated metrics collection:

```bash
kubectl --context kind-observability delete -k day-7/k8s-manifests
helm --kube-context kind-observability uninstall otel-collector prometheus -n olly
```

Do not delete the shared logging/tracing backends while the Node lab uses them.
Review retained PVCs before deleting data. See the [local guide](../local/README.md)
for resource limits, credentials, legacy-version caveats and full cluster cleanup.
