from fastapi import FastAPI
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

from backend.app.observability.resource import build_resource
from backend.config import settings


def setup_metrics() -> None:
    """
    Wire up the OTel metrics SDK. The MeterProvider is the global registry;
    a PeriodicExportingMetricReader wakes up every `export_interval_millis`
    and pushes accumulated measurements through the OTLP exporter to the
    Collector. The Collector then re-exposes them in Prometheus format.
    """
    reader = PeriodicExportingMetricReader(
        exporter=OTLPMetricExporter(
            endpoint=settings.otel_exporter_endpoint,
            insecure=True
        ),
        export_interval_millis=15000
    )

    provider = MeterProvider(
        resource=build_resource(),
        metric_readers=[reader]
    )

    metrics.set_meter_provider(provider)