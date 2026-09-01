from fastapi import APIRouter, HTTPException

from app.db.mongodb import db
from app.repositories.chat_repository import ChatRepository
from app.schemas.chat import (
    CaseChatRequest,
    CaseChatResponse,
)
from app.services.chat.case_chat import (
    CaseChatService,
)


router = APIRouter(
    prefix="/cases",
    tags=["Case Intelligence"],
)


chat_service = CaseChatService()
chat_repository = ChatRepository()


def _get_case_context(case_id: str) -> dict:

    case = db.cases.find_one(
        {"case_id": case_id},
        {"_id": 0},
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    persons = list(
        db.case_persons.aggregate([
            {
                "$match": {
                    "case_id": case_id,
                }
            },
            {
                "$lookup": {
                    "from": "persons",
                    "localField": "person_id",
                    "foreignField": "person_id",
                    "as": "person",
                }
            },
            {
                "$unwind": "$person",
            },
            {
                "$project": {
                    "_id": 0,
                    "person": "$person",
                    "roles": 1,
                    "confidence": 1,
                }
            },
        ])
    )

    unknowns = list(
        db.unknown_identities.find(
            {"case_id": case_id},
            {"_id": 0},
        )
    )

    incidents = list(
        db.incidents.find(
            {"case_id": case_id},
            {"_id": 0},
        )
    )

    entities = list(
        db.entities.find(
            {"case_ids": case_id},
            {"_id": 0},
        )
    )

    relationships = list(
        db.relationships.find(
            {"context.case_id": case_id},
            {"_id": 0},
        )
    )

    return {
        "case": case,
        "persons": persons,
        "unknown_identities": unknowns,
        "incidents": incidents,
        "entities": entities,
        "relationships": relationships,
    }


@router.post(
    "/{case_id}/chat",
    response_model=CaseChatResponse,
)
def chat_with_case(
    case_id: str,
    request: CaseChatRequest,
):

    context = _get_case_context(
        case_id
    )

    # -----------------------------------------
    # Get previous conversation
    # -----------------------------------------

    chat_history = chat_repository.get_history(
        case_id=case_id,
    )

    # -----------------------------------------
    # Store user message
    # -----------------------------------------

    chat_repository.create(
        case_id=case_id,
        role="user",
        content=request.message,
    )

    # -----------------------------------------
    # Ask Gemini
    # -----------------------------------------

    answer = chat_service.answer(
        question=request.message,
        case_context=context,
        chat_history=chat_history,
    )

    # -----------------------------------------
    # Store assistant message
    # -----------------------------------------

    chat_repository.create(
        case_id=case_id,
        role="assistant",
        content=answer,
    )

    return CaseChatResponse(
        case_id=case_id,
        answer=answer,
    )


@router.get(
    "/{case_id}/chat/history",
)
def get_chat_history(
    case_id: str,
):

    # Make sure the case exists
    case = db.cases.find_one(
        {"case_id": case_id},
        {"_id": 1},
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    messages = chat_repository.get_history(
        case_id=case_id,
    )

    return {
        "case_id": case_id,
        "messages": messages,
    }
