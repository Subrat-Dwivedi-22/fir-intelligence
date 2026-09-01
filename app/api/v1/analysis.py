from fastapi import APIRouter, HTTPException

from app.db.mongodb import db

from app.schemas.analysis import (
    InvestigationAnalysisResponse,
)
from app.services.case_context import (
    get_case_context,
)
from app.services.chat.investigation import (
    InvestigationAnalysisService,
)


router = APIRouter(
    prefix="/cases",
    tags=["Case Intelligence"],
)


analysis_service = InvestigationAnalysisService()


@router.post(
    "/{case_id}/analysis",
    response_model=InvestigationAnalysisResponse,
)
def analyze_case(
    case_id: str,
):
    context = get_case_context(case_id)

    if context is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    return analysis_service.analyze(
        case_id=case_id,
        case_context=context,
    )


@router.get(
    "/{case_id}/analysis",
    response_model=InvestigationAnalysisResponse,
)
def get_case_analysis(
    case_id: str,
):
    analysis = db.case_analyses.find_one(
        {
            "case_id": case_id,
        },
        {
            "_id": 0,
        },
    )

    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found. Run POST /analysis first.",
        )

    return InvestigationAnalysisResponse.model_validate(
        analysis
    )
