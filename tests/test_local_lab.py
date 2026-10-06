"""Offline configuration and mocked-command tests; not a live Kubernetes test."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "local/lab.sh"


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate keys that would silently replace a configuration block."""


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def load(path):
    return yaml.load((ROOT / path).read_text(), Loader=UniqueLoader)


def container(deployment):
    return deployment["spec"]["template"]["spec"]["containers"][0]


class ConfigurationTests(unittest.TestCase):
    def test_yaml_parses_without_duplicate_keys(self):
        paths = list((ROOT / "local").glob("*.yaml"))
        paths += list((ROOT / "day-4/kubernetes-manifest").glob("*.yml"))
        paths += list((ROOT / "day-7/k8s-manifests").glob("*.yml"))
        paths += [ROOT / p for p in (
            "day-2/custom_kube_prometheus_stack.yml", "day-5/fluentbit-values.yaml",
            "day-6/jaeger-values.yaml", "day-7/jaeger-values.yaml",
            "day-7/otel-collector-values.yaml", "day-7/prometheus-values.yaml")]
        for path in paths:
            with self.subTest(path=path):
                self.assertIsInstance(yaml.load(path.read_text(), Loader=UniqueLoader), dict)

    def test_kustomization_references_and_namespace_isolation(self):
        for directory, namespace in (("day-4/kubernetes-manifest", "dev"),
                                     ("day-7/k8s-manifests", "otel-demo")):
            config = load(f"{directory}/kustomization.yml")
            self.assertEqual(config["namespace"], namespace)
            for resource in config["resources"]:
                self.assertTrue((ROOT / directory / resource).is_file(), resource)
        self.assertEqual(load("day-7/k8s-manifests/namespace.yml")["metadata"]["name"], "otel-demo")

    def test_images_services_ports_and_probes_match(self):
        for day, directory, prefix, ports in (
            (4, "day-4/kubernetes-manifest", "service", {"a": 3001, "b": 3002}),
            (7, "day-7/k8s-manifests", "go-service", {"a": 80, "b": 80}),
        ):
            for letter in ("a", "b"):
                with self.subTest(day=day, service=letter):
                    dname = f"deployment-svc-{letter}.yml" if day == 4 else f"deployment-{letter}.yml"
                    sname = f"service-svc-{letter}.yml" if day == 4 else f"svc-{letter}.yml"
                    d, s = load(f"{directory}/{dname}"), load(f"{directory}/{sname}")
                    c = container(d)
                    self.assertEqual(c["image"], f"observability/{prefix}-{letter}:local")
                    self.assertEqual(c["imagePullPolicy"], "Never")
                    self.assertEqual(s["spec"]["type"], "ClusterIP")
                    self.assertEqual(s["spec"]["selector"], d["spec"]["template"]["metadata"]["labels"])
                    self.assertEqual(s["spec"]["ports"][0]["targetPort"], ports[letter])
                    self.assertEqual(c["ports"][0]["containerPort"], ports[letter])
                    self.assertEqual(c["readinessProbe"]["httpGet"]["port"], ports[letter])
                    self.assertIn("limits", c["resources"])

    def test_node_servicemonitor_matches_service(self):
        sm = load("day-4/alerts-alertmanager-servicemonitor-manifest/serviceMonitor.yml")
        svc = load("day-4/kubernetes-manifest/service-svc-a.yml")
        self.assertEqual(sm["metadata"]["labels"]["release"], "monitoring")
        self.assertEqual(sm["spec"]["namespaceSelector"]["matchNames"], ["dev"])
        self.assertEqual(sm["spec"]["endpoints"][0]["port"], svc["spec"]["ports"][0]["name"])
        for k, v in sm["spec"]["selector"]["matchLabels"].items():
            self.assertEqual(svc["metadata"]["labels"][k], v)

    def test_otel_and_go_connections_match(self):
        otel = load("day-7/otel-collector-values.yaml")
        self.assertEqual(otel["fullnameOverride"], "otel-collector")
        for letter, peer in (("a", "b"), ("b", "a")):
            d = load(f"day-7/k8s-manifests/deployment-{letter}.yml")
            env = {v["name"]: v["value"] for v in container(d)["env"]}
            self.assertEqual(env["OTEL_COLLECTOR_ENDPOINT"], "otel-collector.olly.svc:4318")
            self.assertEqual(env[f"SVC_{peer.upper()}_URI"], f"http://{peer}-service.otel-demo")
        for name, port in (("otlp", 4317), ("otlp-http", 4318), ("prometheus", 8889)):
            self.assertTrue(otel["ports"][name]["enabled"])
            self.assertEqual(otel["ports"][name]["servicePort"], port)
            self.assertNotIn("hostPort", otel["ports"][name])
        exports = otel["config"]["exporters"]
        self.assertEqual(exports["otlp/jaeger"]["endpoint"], "jaeger-collector.tracing.svc:4317")
        prom = load("day-7/prometheus-values.yaml")
        targets = prom["serverFiles"]["prometheus.yml"]["scrape_configs"][0]["static_configs"][0]["targets"]
        self.assertEqual(targets, ["otel-collector.olly.svc:8889"])
        for pipeline in otel["config"]["service"]["pipelines"].values():
            self.assertIn("memory_limiter", pipeline["processors"])

    def test_shared_elasticsearch_uses_secrets_and_tls(self):
        for day in (6, 7):
            jaeger = load(f"day-{day}/jaeger-values.yaml")
            es = jaeger["storage"]["elasticsearch"]
            self.assertEqual(es["host"], "elasticsearch-master.logging.svc")
            self.assertEqual(es["existingSecret"], "jaeger-es-credentials")
            self.assertNotIn("password", es)
            self.assertTrue(es["tls"]["enabled"])
            self.assertFalse(any(jaeger["provisionDataStore"].values()))
        fluent = load("day-5/fluentbit-values.yaml")
        self.assertEqual(fluent["env"][0]["valueFrom"]["secretKeyRef"]["name"], "elasticsearch-master-credentials")
        self.assertIn("tls.verify On", fluent["config"]["outputs"])
        self.assertIn("${ES_PASSWORD}", fluent["config"]["outputs"])
        self.assertIn("cri", fluent["config"]["inputs"])

    def test_local_storage_and_no_cloud_provisioning(self):
        kind = load("local/kind.yaml")
        self.assertEqual(kind["networking"]["apiServerAddress"], "127.0.0.1")
        self.assertEqual(len(kind["nodes"]), 1)
        es = load("local/elasticsearch-values.yaml")
        self.assertEqual(es["volumeClaimTemplate"]["storageClassName"], "standard")
        self.assertEqual(es["replicas"], 1)
        self.assertFalse((ROOT / "day-3/ingress_kube_prom_stack.yaml").exists())
        for path in (ROOT / "local").glob("*.yaml"):
            self.assertNotIn("type: LoadBalancer", path.read_text())
            self.assertNotIn("storageClassName: gp2", path.read_text())
        script = SCRIPT.read_text()
        self.assertNotIn("eksctl ", script)
        self.assertNotIn("aws ", script)
        self.assertNotIn("docker push", script)
        self.assertNotIn("prune", script)

    def test_shell_syntax(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


class CommandSafetyTests(unittest.TestCase):
    def run_mock(self, *args, runtime_failure=False, clusters="observability"):
        # Execute the real shell script with fake tools; never contact a real cluster.
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            log = directory / "calls.jsonl"
            body = r"""#!/usr/bin/env python3
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
with open(os.environ['CALL_LOG'], 'a') as out:
    out.write(json.dumps([name] + sys.argv[1:]) + '\n')
if name == 'docker' and os.environ.get('FAIL_RUNTIME') == '1':
    sys.exit(1)
if name == 'kind' and sys.argv[1:] == ['get', 'clusters']:
    print(os.environ.get('MOCK_CLUSTERS', 'observability'))
"""
            for name in ("docker", "kind", "kubectl", "helm"):
                tool = directory / name
                tool.write_text(body)
                tool.chmod(0o755)
            env = dict(os.environ, PATH=str(directory) + os.pathsep + os.environ["PATH"],
                       CALL_LOG=str(log), FAIL_RUNTIME=str(int(runtime_failure)), MOCK_CLUSTERS=clusters)
            result = subprocess.run(["bash", str(SCRIPT), *args], env=env, text=True, capture_output=True)
            calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            return result, calls

    def test_help_unknown_and_unconfirmed_delete_do_not_touch_tools(self):
        for args, expected in ((["--help"], 0), (["typo"], 2), (["delete"], 2)):
            with self.subTest(args=args):
                result, calls = self.run_mock(*args)
                self.assertEqual(result.returncode, expected)
                self.assertEqual(calls, [])

    def test_confirmed_delete_only_deletes_named_kind_cluster(self):
        result, calls = self.run_mock("delete", "--confirm-delete")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, [["kind", "delete", "cluster", "--name", "observability"]])

    def test_missing_runtime_stops_before_cluster_mutation(self):
        result, calls = self.run_mock("monitoring", runtime_failure=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [["docker", "info"]])

    def test_missing_local_cluster_does_not_use_current_context(self):
        result, calls = self.run_mock("monitoring", clusters="unrelated")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[0] in {"helm", "kubectl"} for c in calls))

    def test_status_and_monitoring_explicitly_scope_cluster_commands(self):
        for stage in ("status", "monitoring"):
            with self.subTest(stage=stage):
                result, calls = self.run_mock(stage)
                self.assertEqual(result.returncode, 0, result.stderr)
                for call in calls:
                    if call[0] == "kubectl":
                        self.assertEqual(call[1:3], ["--context", "kind-observability"])
                    if call[0] == "helm" and call[1] != "repo":
                        self.assertEqual(call[1:3], ["--kube-context", "kind-observability"])


if __name__ == "__main__":
    unittest.main()
