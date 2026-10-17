from pydantic import BaseModel

from app.schemas.expression import ExpressionStatusRead
from app.schemas.hla import HlaStatusRead


class IntegrationStatusRead(BaseModel):
    analysis_run_id: str
    status: str
    hla: HlaStatusRead
    expression: ExpressionStatusRead
    annotated_genes: list[str]
    expressed_genes: list[str]
    linked_genes: list[str]
    genes_without_expression: list[str]
    checks: list[dict]


class SyntheticIntegrationRead(BaseModel):
    analysis_run_id: str
    status: str
    hla_status: str
    expression_status: str
    linked_genes: list[str]
