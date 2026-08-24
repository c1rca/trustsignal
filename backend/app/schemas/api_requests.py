from pydantic import BaseModel, Field


class AnalyzeReportRequest(BaseModel):
    report_id: str = Field(min_length=1)
