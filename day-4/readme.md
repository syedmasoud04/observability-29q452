# Day 4 — Application instrumentation and alerting

Instrumentation adds measurements and context to application behavior. Keep the
four Prometheus metric types in view: a **counter** accumulates events, a **gauge**
can rise or fall, a **histogram** tracks observations in buckets, and a **summary**
tracks observations with configured quantiles.

The Node.js examples preserve the original custom metrics, structured logs,
error/crash routes, and distributed tracing instrumentation. Service A exposes
`http_requests_total`, `http_request_duration_seconds`,
`http_request_duration_summary_seconds` and `node_gauge_example` using prom-client.
Inspect `application/service-a/index.js` and the instrumentation analysis documents.

![Application architecture](images/architecture.gif)

## Build and deploy locally

From the repository root, after [Day 2](../day-2/readme.md):

```bash
bash local/lab.sh node-app
kubectl --context kind-observability -n dev get pods,svc
kubectl --context kind-observability -n dev port-forward --address 127.0.0.1 svc/a-service 3001:80
```

The installer builds **separate** service A and B images, loads them into kind, and
applies the deployments with `imagePullPolicy: Never`. It does not push to a registry.
Service B now uses its own image and listens on 3002. Service names, labels and
ServiceMonitor port names remain consistent. Re-run the stage after editing code.

## Generate metrics and logs

In another terminal:

```bash
curl http://127.0.0.1:3001/healthy
curl http://127.0.0.1:3001/serverError
curl http://127.0.0.1:3001/notFound
curl http://127.0.0.1:3001/logs
curl http://127.0.0.1:3001/example
curl http://127.0.0.1:3001/metrics
curl http://127.0.0.1:3001/call-service-b
bash day-4/test.sh 127.0.0.1:3001
```

The test script expects `HOST:PORT`, not a URL with another `http://` prefix.
The 500/404 responses above are intentional. Jaeger export errors are expected until
[Day 6](../day-6/readme.md) installs the tracing backend; they are not cloud dependencies.

## Alertmanager

The installer applies the existing ServiceMonitor and PrometheusRule without applying
SMTP secrets. Check that the custom metrics are being scraped in Prometheus.
`HighCpuUsage` fires after sustained CPU usage above 50%; `PodRestart` detects a
container restart count above two. Inspect alerts in Prometheus and Alertmanager.

The `/crash` endpoint deliberately terminates this demo service. Exercise it only in
this local lab; wait for readiness and restart the port-forward after each restart.
Crash it three times to exercise the restart rule. Do not use this as a production
readiness/liveness check.

### Optional real email delivery

Email is not required to learn alert evaluation, grouping or routing. To send mail,
use an SMTP account you already control, replace the example addresses in
`alerts-alertmanager-servicemonitor-manifest/alertmangerconfig.yml`, and create the
`mail-pass` Secret with key `gmail-pass` from your own app password without
committing it. These names match the existing AlertmanagerConfig. Apply that
configuration only after replacing the email addresses and creating the Secret. Never apply the committed
example password as a real credential. See your mail provider's app-password rules.

Continue to [Day 5](../day-5/readme.md) for centralized logs and
[Day 6](../day-6/readme.md) for cross-service traces. Keep monitoring installed.
