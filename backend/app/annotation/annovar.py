"""ANNOVAR provider (reserved)."""
from app.annotation.registry import register
from app.annotation.stub import ExternalProviderStub


@register
class AnnovarAnnotator(ExternalProviderStub):
    name = "annovar"
    display_name = "ANNOVAR"
    provider_version = "not-installed"
    annotation_version = "unconfigured"
    transcript_source = "unconfigured"
    description = "Reserved ANNOVAR provider."
    unavailable_reason = (
        "ANNOVAR is not installed. Configure an ANNOVAR runtime to enable this provider."
    )
