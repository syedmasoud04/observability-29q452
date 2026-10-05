# Dashboard access without a cloud ingress controller

The local lab does not install an ALB controller or create public load balancers.
The previous cloud-specific ingress manifest has been removed.

Use ClusterIP Services with the [localhost port-forward commands](../local/README.md#access-from-your-own-computer).
Prometheus, Grafana and Alertmanager do not require ingress to complete the PromQL
exercises in [Day 3](readme.md). Do not expose their unauthenticated interfaces publicly.
