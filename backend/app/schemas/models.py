from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PredictionRecord(BaseModel):
    abnormality: str
    probability: float
    confidenceLevel: str


class StudyRecord(BaseModel):
    studyId: str
    createdAt: str
    status: str = 'pending'
    imageCount: int = 0
    analysisStatus: str = 'pending'
    priority: str = 'LOW'
    overallRisk: float = 0.0


class ReportRecord(BaseModel):
    studyId: str
    findings: str
    impression: str
    recommendation: str
    generatedAt: str
    reviewStatus: str = 'pending'


class AnalysisEvent(BaseModel):
    studyId: str
    event: str
    timestamp: str
