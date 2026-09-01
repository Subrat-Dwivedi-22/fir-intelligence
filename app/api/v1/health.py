from fastapi import APIRouter

from app.db.mongodb import check_connection


router = APIRouter()


@router.get("/health")
def health():
    check_connection()

    return {
        "status": "ok",
        "database": "connected",
    }