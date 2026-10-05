# Free local Kubernetes setup

## Scope and requirements

The goal remains an end-to-end observability lab, not a cloud-provider tutorial.
Use an existing Linux/macOS computer or Windows with WSL2 and Linux containers.
Install Docker Engine, kind, kubectl, Helm 3, Bash and a base64 utility. Docker Desktop
is an alternative subject to its licensing terms; it is not mandatory.
Use a current stable kind release (the upstream guide currently documents v0.33.0).

**Planning estimates, not measured benchmarks:** allocate 4 CPUs and 8 GiB RAM to
Docker for the sequential labs; 12 GiB RAM is more comfortable with all components
running. Allow at least 30 GiB free disk for images, builds and telemetry. An 8 GiB
physical machine may be too small for the full EFK stack plus the host OS. Free
software does not provide free additional hardware. Do not replace persistence
with emptyDir merely to make a Pending PVC disappear.

Official references: [kind setup](https://kind.sigs.k8s.io/docs/user/quick-start/),
[kind on WSL2](https://kind.sigs.k8s.io/docs/user/using-wsl2/),
[Kubernetes port-forwarding](https://kubernetes.io/docs/tasks/access-application-cluster/port-forward-access-application-cluster/).

## Deploy in lesson order

From the repository root:

```bash
bash local/lab.sh cluster
bash local/lab.sh monitoring    # Days 2–3
bash local/lab.sh node-app      # Day 4; monitoring must already exist
bash local/lab.sh logging       # Day 5
bash local/lab.sh tracing       # Day 6; reuses Elasticsearch in logging
bash local/lab.sh otel          # Day 7; reuses Jaeger in tracing
bash local/lab.sh status
```

The cluster has one schedulable control-plane node. `standard` uses kind's local-path
provisioner. Each command targets `kind-observability` explicitly and fails if that
cluster is missing. The scripts never run against your currently selected cloud context.
On repeated application builds, the new image is loaded and deployments are restarted.

Do not install both the old and new instructions into an existing EKS cluster.
Create this separate cluster first. No script migrates existing telemetry or deletes
existing cloud resources. Export anything needed before a separately reviewed cloud
cleanup; otherwise existing infrastructure can continue to incur charges.

## Access from your own computer

Keep each port-forward command running in its own terminal. All listeners explicitly
bind to localhost. Stop them with Ctrl+C; rerun after a selected pod is restarted.

```bash
kubectl --context kind-observability -n monitoring port-forward --address 127.0.0.1 svc/monitoring-grafana 3000:80
kubectl --context kind-observability -n monitoring port-forward --address 127.0.0.1 svc/prometheus-operated 9090:9090
kubectl --context kind-observability -n monitoring port-forward --address 127.0.0.1 svc/alertmanager-operated 9093:9093
kubectl --context kind-observability -n dev port-forward --address 127.0.0.1 svc/a-service 3001:80
kubectl --context kind-observability -n logging port-forward --address 127.0.0.1 svc/kibana-kibana 5601:5601
kubectl --context kind-observability -n tracing port-forward --address 127.0.0.1 svc/jaeger-query 16686:80
kubectl --context kind-observability -n olly port-forward --address 127.0.0.1 svc/prometheus-server 9091:80
kubectl --context kind-observability -n otel-demo port-forward --address 127.0.0.1 svc/a-service 8081:80
kubectl --context kind-observability -n otel-demo port-forward --address 127.0.0.1 svc/b-service 8082:80
```

Open the corresponding `http://127.0.0.1:PORT` address. Grafana uses username `admin`;
retrieve its generated password rather than relying on a committed default:

```bash
kubectl --context kind-observability -n monitoring get secret monitoring-grafana -o jsonpath='{.data.admin-password}' | base64 -d; echo
# Kibana: username elastic; password comes from the Elasticsearch Secret.
kubectl --context kind-observability -n logging get secret elasticsearch-master-credentials -o jsonpath='{.data.password}' | base64 -d; echo
```

Never commit the displayed passwords. Fluent Bit reads a Secret, and the tracing
installer copies the Elasticsearch credential/CA to the tracing namespace using
restricted temporary files. Re-run `tracing` after rotating Elasticsearch credentials.

## Verify the learning objectives

After starting the relevant port-forwards:

```bash
curl --fail http://127.0.0.1:3001/healthy
curl --fail http://127.0.0.1:3001/call-service-b
curl --fail http://127.0.0.1:3001/logs
curl --fail http://127.0.0.1:3001/metrics
bash day-4/test.sh 127.0.0.1:3001
curl --fail http://127.0.0.1:8081/call-b
curl --fail http://127.0.0.1:8082/call-a
bash day-7/test.sh http://127.0.0.1:8081 http://127.0.0.1:8082
```

In Prometheus on port 9090, verify the Node ServiceMonitor target is UP and query
`http_requests_total` and `kube_pod_container_status_restarts_total`. In Grafana,
open Kubernetes dashboards. In Alertmanager on 9093, inspect the custom rule alerts;
external email is optional and needs your own SMTP configuration.

In Kibana, create a data view `kubernetes-*` using `@timestamp` and find logs from
`dev` and `otel-demo`. Logging-system logs are excluded to avoid a feedback loop.
Fluent Bit tails CRI container logs under `/var/log`; kind is not a full host-journal lab.

In Jaeger, select `service-a` or `microservice-a`, use a recent time window, and inspect
a cross-service request. On port 9091, verify the `otel-collector` target is UP and
search for the Go application's `request_count`, `request_duration_ms` and
`active_requests` metric families (exported names may include suffixes).
Do not treat Ready pods alone as proof that telemetry is flowing.

The Go examples emit traces/metrics using OTLP and application logs using stdout.
Fluent Bit sends those logs to Elasticsearch. An optional Collector OTLP logs pipeline
is present, but this does not claim the Go application uses an OTLP Logs SDK.

## Cost, persistence and limitations

There are no cloud credentials, public load balancers, registry pushes or subscription
sign-ups in the default setup. Downloads and existing machine operating costs remain.
Local PVCs survive ordinary pod restarts, not cluster deletion or loss of the node's
disk. Backups are separate; this is not a migration of existing AWS data.

Single replicas, short metrics retention and resource limits deliberately replace
production high availability. Elasticsearch indices still grow: monitor disk usage,
remove old lab indices deliberately, and export anything valuable first. Single-node
Elasticsearch may be yellow because replica shards cannot be placed; that is different
from red/unavailable primary shards. Core Kubernetes metrics remain; inaccessible
kind control-plane metrics targets are disabled to avoid misleading alerts.

Charts are pinned in `versions.env`. The original Elastic 8.5.1 and Jaeger v1 chart
3.4.0 compatibility is retained; these legacy dependencies require a separate upgrade
and security review before any real deployment. This change is not a production
hardening exercise. Helm hooks and upgrades, resource sizing and telemetry delivery
must be checked on the target machine. Keep dashboards private even in a lab.

## Checks and cleanup

Static regression checks (Python 3 and PyYAML required):

```bash
python -m pip install -r local/requirements-test.txt
python -m unittest discover -s tests -v
bash -n local/lab.sh
```

These checks do not create a Kubernetes cluster or assert live Helm compatibility.
For a Pending pod/PVC, inspect `kubectl --context kind-observability describe pod ...`
and `get pvc -A`, then check available memory/disk and the `standard` StorageClass.
For `ErrImageNeverPull`, rerun the relevant image build/load stage. For export errors,
check the Jaeger/Collector Service, namespace and receiver port before changing code.

To remove the entire disposable lab **including its stored data**:

```bash
bash local/lab.sh delete --confirm-delete
```

This deletes only the named local kind cluster, never AWS infrastructure or unrelated
Docker volumes. To retain data, leave the cluster in place; do not run global prune commands.
