from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class StudyRow(Base):
    __tablename__ = 'studies'

    study_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    status: Mapped[str] = mapped_column(String(32), default='uploaded')
    image_count: Mapped[int] = mapped_column(Integer, default=0)
    analysis_status: Mapped[str] = mapped_column(String(32), default='pending')
    priority: Mapped[str] = mapped_column(String(16), default='LOW')
    overall_risk: Mapped[float] = mapped_column(Float, default=0.0)
    files_json: Mapped[str] = mapped_column(Text, default='[]')

    predictions: Mapped[list['PredictionRow']] = relationship(
        back_populates='study', cascade='all, delete-orphan'
    )
    report: Mapped['ReportRow | None'] = relationship(
        back_populates='study', uselist=False, cascade='all, delete-orphan'
    )
    events: Mapped[list['AnalysisEventRow']] = relationship(
        back_populates='study', cascade='all, delete-orphan'
    )


class PredictionRow(Base):
    __tablename__ = 'predictions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    study_id: Mapped[str] = mapped_column(
        String(32), ForeignKey('studies.study_id', ondelete='CASCADE')
    )
    abnormality: Mapped[str] = mapped_column(String(64))
    probability: Mapped[float] = mapped_column(Float)
    confidence_level: Mapped[str] = mapped_column(String(16))

    study: Mapped['StudyRow'] = relationship(back_populates='predictions')


class ReportRow(Base):
    __tablename__ = 'reports'

    study_id: Mapped[str] = mapped_column(
        String(32), ForeignKey('studies.study_id', ondelete='CASCADE'), primary_key=True
    )
    findings: Mapped[str] = mapped_column(Text, default='')
    impression: Mapped[str] = mapped_column(Text, default='')
    recommendation: Mapped[str] = mapped_column(Text, default='')
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    review_status: Mapped[str] = mapped_column(String(32), default='pending')

    study: Mapped['StudyRow'] = relationship(back_populates='report')


class AnalysisEventRow(Base):
    __tablename__ = 'analysis_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    study_id: Mapped[str] = mapped_column(
        String(32), ForeignKey('studies.study_id', ondelete='CASCADE')
    )
    event: Mapped[str] = mapped_column(String(64))
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    study: Mapped['StudyRow'] = relationship(back_populates='events')
