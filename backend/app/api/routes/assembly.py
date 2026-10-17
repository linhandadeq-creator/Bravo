from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.blueprint.assembly import LINKERS, STRATEGIES, assemble

router = APIRouter(tags=["assembly"])


class AssemblyEpitope(BaseModel):
    peptide: str = Field(..., min_length=8, max_length=14)
    hla: str | None = None
    score: float | None = None


class AssemblyRequest(BaseModel):
    epitopes: list[AssemblyEpitope] = Field(..., min_length=1, max_length=60)
    linker: str = "GPGPG"
    strategy: str = "junction"
    predict_binding: bool = False
    hla: list[str] | None = None
    design: bool = False


@router.get("/blueprint/assembly/options")
def assembly_options() -> dict:
    return {"linkers": sorted(LINKERS), "strategies": list(STRATEGIES)}


@router.post("/blueprint/assembly")
def post_assembly(payload: AssemblyRequest) -> dict:
    try:
        return assemble(
            [item.model_dump() for item in payload.epitopes],
            linker=payload.linker,
            strategy=payload.strategy,
            predict_binding=payload.predict_binding,
            hla=payload.hla,
            design=payload.design,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
