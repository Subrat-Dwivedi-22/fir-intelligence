from pydantic import BaseModel


class FIRUploadResponse(BaseModel):
    case_id: str
    document_id: str
    job_id: str
    status: str
    message: str