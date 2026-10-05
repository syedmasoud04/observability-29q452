# Day 5 — Logging with Elasticsearch, Fluent Bit and Kibana

Logs explain application events and support debugging, auditing and performance
investigation. The EFK pipeline remains: **container stdout/stderr → Fluent Bit →
Elasticsearch → Kibana**. Elasticsearch indexes and stores log records; Fluent Bit
collects and enriches them with Kubernetes metadata; Kibana makes them searchable.

![Logging architecture](images/architecture.gif)

## Deploy

After creating the local cluster, run from the repository root:

```bash
bash local/lab.sh logging
kubectl --context kind-observability -n logging get pods,pvc,svc
kubectl --context kind-observability -n logging port-forward --address 127.0.0.1 svc/kibana-kibana 5601:5601
```

This uses the free local `standard` StorageClass, one Elasticsearch replica, a
5 GiB PVC and memory-limited single-node settings. No IAM role or EBS driver is
needed. Memory-mapped storage and its privileged sysctl setup are disabled for this
lab. Authentication and certificate validation remain enabled.

`fluentbit-values.yaml` tails CRI/containerd logs under `/var/log/containers` rather
than assuming Docker's node filesystem layout. It reads the Elasticsearch password
from a Secret and trusts its CA. Logging-namespace logs are excluded to prevent
feedback. Host journald ingestion from the older cloud setup is not assumed in kind.

## Verify ingestion

Log in to Kibana at `http://127.0.0.1:5601` with username `elastic`; retrieve the
password using the [local guide](../local/README.md#access-from-your-own-computer).
Create a data view `kubernetes-*` with time field `@timestamp`. Generate requests to
the Day 4 `/logs` endpoint and find `dev` namespace records in Discover.

Single-node Elasticsearch may be yellow because replicas have no second node.
A red cluster or missing documents still needs investigation. Check Fluent Bit logs,
Elasticsearch health, Secret references and available disk rather than disabling TLS.

## Storage and next steps

Logs survive ordinary pod restarts, not cluster deletion. Monitor the finite local
disk and deliberately remove/export old lab indices when necessary. The version-pinned
Elastic chart is a legacy tutorial dependency, not a production deployment template.
Keep Elasticsearch running for [Day 6](../day-6/readme.md): Jaeger reuses this datastore,
so installing or cleaning up tracing does not require a second Elasticsearch cluster.
