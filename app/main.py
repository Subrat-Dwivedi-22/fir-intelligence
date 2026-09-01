from fastapi import FastAPI

from app.api.v1.health import router as health_router
from app.api.v1.cases import router as case_router
from app.db.indexes import create_indexes
from app.api.v1.case_graph import router as case_graph_router
from app.api.v1.chat import router as chat_router
from app.api.v1.analysis import router as analysis_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.case_documents import (
    router as case_documents_router,
)

app = FastAPI(
    title="FIR Intelligence Ingestion API",
    version="0.1.0",
)


@app.on_event("startup")
def startup():
    create_indexes()


app.include_router(
    health_router,
    prefix="/api/v1",
)

app.include_router(
    case_router,
    prefix="/api/v1",
)

app.include_router(
    case_documents_router,
    prefix="/api/v1",
)

app.include_router(
    case_graph_router,
    prefix="/api/v1",
)

app.include_router(
    chat_router,
    prefix="/api/v1",
)

app.include_router(
    analysis_router,
    prefix="/api/v1",
)

app.include_router(
    jobs_router,
    prefix="/api/v1",
)

