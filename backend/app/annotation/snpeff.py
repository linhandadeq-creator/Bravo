"""SnpEff provider (reserved)."""
from app.annotation.registry import register
from app.annotation.stub import ExternalProviderStub


@register
class SnpEffAnnotator(ExternalProviderStub):
    name = "snpeff"
    display_name = "SnpEff"
    provider_version = "not-installed"
    annotation_version = "unconfigured"
    transcript_source = "unconfigured"
    description = "Reserved SnpEff provider."
    unavailable_reason = (
        "SnpEff is not installed. Configure a SnpEff runtime to enable this provider."
    )
