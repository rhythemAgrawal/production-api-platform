from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes

from backend.config import settings


def build_resource() -> Resource:
    """
    A Resource describes *the entity producing telemetry* — your service.
    Every span and every metric data point gets tagged with these attributes,
    which is how Grafana/Jaeger know "these traces and these metrics belong
    to the same service". Keep it identical across signals.
    """
    return Resource.create({
        ResourceAttributes.SERVICE_NAME: settings.app_name,
        ResourceAttributes.DEPLOYMENT_ENVIRONMENT: settings.environment,
        # Add SERVICE_VERSION when you start tagging releases — it's how
        # you'll diff metrics across deploys.
    })
