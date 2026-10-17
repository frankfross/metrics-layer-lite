"""Load and validate metric definitions from a YAML file."""

import yaml


class MetricError(ValueError):
    """Raised when a metric definition is malformed or unsupported."""


def load_metrics(path):
    """Load a YAML file and return the list of metric definitions.

    The file must contain a top-level ``metrics:`` list. Duplicate metric
    names are rejected — two definitions with the same name would make
    ``run <name>`` ambiguous.
    """
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    if not isinstance(doc, dict) or not isinstance(doc.get("metrics"), list):
        raise MetricError(f"{path}: expected a top-level 'metrics:' list")
    metrics = doc["metrics"]
    seen = set()
    for metric in metrics:
        name = metric.get("name") if isinstance(metric, dict) else None
        if not name:
            raise MetricError(f"{path}: every metric needs a 'name'")
        if name in seen:
            raise MetricError(f"{path}: duplicate metric name {name!r}")
        seen.add(name)
    return metrics


def get_metric(metrics, name):
    """Return the metric definition with ``name`` or raise MetricError."""
    for metric in metrics:
        if metric.get("name") == name:
            return metric
    raise MetricError(f"No metric named {name!r} (have: {', '.join(sorted(m.get('name', '?') for m in metrics))})")
