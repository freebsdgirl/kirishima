from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


from shared.config import OTLP_API_KEY, OTLP_URL

def setup_tracing(app, service_name: str):
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    trace.set_tracer_provider(
        TracerProvider(
            resource=Resource.create({SERVICE_NAME: service_name})
        )
    )
    otlp_exporter = OTLPSpanExporter(endpoint="http://tempo:4317", insecure=True)

    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(otlp_exporter)
    )


    FastAPIInstrumentor.instrument_app(app)


def setup_remote_tracing(app, service_name: str):
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    trace.set_tracer_provider(
        TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    )

    headers = {"Authorization": f"Bearer {OTLP_API_KEY}"}

    exporter = OTLPSpanExporter(
        endpoint=OTLP_URL.rstrip("/") + "/v1/traces",
        headers=headers,
    )

    span_processor = BatchSpanProcessor(exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)

    FastAPIInstrumentor.instrument_app(app)