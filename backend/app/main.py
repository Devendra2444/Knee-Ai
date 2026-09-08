from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import API_URL, UPLOAD_LIMIT_MB
from app.database.database import Base, SessionLocal, db_status, engine
from app.database.db_models import AnalysisEventRow, PredictionRow, ReportRow, StudyRow
from app.ml.inference import MRIInferenceService, get_inference_provider
from app.services.report_service import build_top_findings, confidence_label, generate_report
from app.utils.priority import calculate_priority


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Create all tables on first run (safe if they already exist)."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title='KneeAI API', version='0.2.0', lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

UPLOAD_DIR = Path(__file__).resolve().parents[1] / 'uploads'
UPLOAD_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_db():
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get('/api/health')
def health():
    provider = get_inference_provider()
    provider_name = type(provider).__name__
    return {
        'status': 'ok',
        'service': 'KneeAI API',
        'database': db_status(),
        'modelMode': provider_name,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


@app.get('/api/model/status')
def model_status():
    provider = get_inference_provider()
    provider_name = type(provider).__name__
    return {
        'modelMode': f'{provider_name} active',
        'modelVersion': 'roboflow-v1' if 'Roboflow' in provider_name else 'prototype-v1',
        'status': 'ready',
        'realModelAvailable': 'Roboflow' in provider_name,
        'provider': provider_name,
    }


@app.get('/api/studies')
def list_studies():
    db = _get_db()
    try:
        rows = db.query(StudyRow).order_by(StudyRow.created_at.desc()).all()
        return [_study_to_dict(row) for row in rows]
    finally:
        db.close()


@app.post('/api/studies/upload')
async def upload_study(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail='At least one image is required.')

    valid_exts = {'.png', '.jpg', '.jpeg'}
    uploaded_files = []
    for file in files:
        if not file.filename:
            raise HTTPException(status_code=400, detail='A file without a name was provided.')

        suffix = os.path.splitext(file.filename)[1].lower()
        if suffix not in valid_exts:
            raise HTTPException(status_code=400, detail=f'Unsupported file type: {file.filename}')

        content = await file.read()
        if len(content) > UPLOAD_LIMIT_MB * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f'File exceeds {UPLOAD_LIMIT_MB} MB limit.')

        safe_name = ''.join(ch for ch in file.filename if ch.isalnum() or ch in ('.', '-', '_'))
        file_path = UPLOAD_DIR / safe_name
        file_path.write_bytes(content)
        uploaded_files.append({'filename': safe_name, 'path': str(file_path)})

    db = _get_db()
    try:
        count = db.query(StudyRow).count()
        study_id = f'KNEE-{count + 1:04d}'

        study = StudyRow(
            study_id=study_id,
            status='uploaded',
            image_count=len(uploaded_files),
            analysis_status='pending',
            priority='LOW',
            overall_risk=0.0,
            files_json=json.dumps(uploaded_files),
        )
        db.add(study)
        db.commit()

        return {
            'studyId': study_id,
            'imageCount': len(uploaded_files),
            'status': 'uploaded',
        }
    finally:
        db.close()


@app.post('/api/studies/{study_id}/analyze')
async def analyze_study(study_id: str):
    db = _get_db()
    try:
        study = db.query(StudyRow).filter(StudyRow.study_id == study_id).first()
        if study is None:
            raise HTTPException(status_code=404, detail='Study not found.')

        file_list = json.loads(study.files_json or '[]')
        if not file_list:
            raise HTTPException(status_code=400, detail='No uploaded images found for this study.')

        # Run inference via whichever provider is configured
        provider = get_inference_provider()
        service = MRIInferenceService(provider=provider)
        predictions = service.predict([f['path'] for f in file_list])

        study.analysis_status = 'completed'
        study.status = 'completed'
        study.priority = calculate_priority(predictions)
        study.overall_risk = round(sum(predictions.values()) / len(predictions), 4)

        # Remove old predictions for re-analysis
        db.query(PredictionRow).filter(PredictionRow.study_id == study_id).delete()

        prediction_rows = []
        for name, probability in sorted(predictions.items(), key=lambda item: item[1], reverse=True):
            row = PredictionRow(
                study_id=study_id,
                abnormality=name,
                probability=probability,
                confidence_level='High' if probability >= 0.75 else 'Moderate' if probability > 0.4 else 'Low',
            )
            db.add(row)
            prediction_rows.append(row)

        # Generate report
        report_data = generate_report(study_id, predictions)
        existing_report = db.query(ReportRow).filter(ReportRow.study_id == study_id).first()
        if existing_report:
            existing_report.findings = report_data['findings']
            existing_report.impression = report_data['impression']
            existing_report.recommendation = report_data['recommendation']
            existing_report.generated_at = datetime.now(timezone.utc)
            existing_report.review_status = 'pending'
        else:
            report_row = ReportRow(
                study_id=study_id,
                findings=report_data['findings'],
                impression=report_data['impression'],
                recommendation=report_data['recommendation'],
                review_status='pending',
            )
            db.add(report_row)

        # Log event
        event = AnalysisEventRow(
            study_id=study_id,
            event='analysis_completed',
        )
        db.add(event)
        db.commit()

        return {
            'studyId': study_id,
            'analysisStatus': 'completed',
            'priority': study.priority,
            'overallRisk': study.overall_risk,
            'predictions': [
                {
                    'abnormality': r.abnormality,
                    'probability': r.probability,
                    'confidenceLevel': r.confidence_level,
                }
                for r in prediction_rows
            ],
            'topFindings': build_top_findings(predictions),
            'report': report_data,
            'inferenceMode': type(provider).__name__,
        }
    finally:
        db.close()


@app.get('/api/studies/{study_id}')
def get_study(study_id: str):
    db = _get_db()
    try:
        study = db.query(StudyRow).filter(StudyRow.study_id == study_id).first()
        if study is None:
            raise HTTPException(status_code=404, detail='Study not found.')
        return _study_to_dict(study)
    finally:
        db.close()


@app.get('/api/studies/{study_id}/predictions')
def get_predictions(study_id: str):
    db = _get_db()
    try:
        rows = (
            db.query(PredictionRow)
            .filter(PredictionRow.study_id == study_id)
            .order_by(PredictionRow.probability.desc())
            .all()
        )
        if not rows:
            raise HTTPException(status_code=404, detail='Predictions not found for study.')
        return {
            'studyId': study_id,
            'predictions': [
                {
                    'abnormality': r.abnormality,
                    'probability': r.probability,
                    'confidenceLevel': r.confidence_level,
                }
                for r in rows
            ],
        }
    finally:
        db.close()


@app.get('/api/studies/{study_id}/report')
def get_report(study_id: str):
    db = _get_db()
    try:
        report = db.query(ReportRow).filter(ReportRow.study_id == study_id).first()
        if report is None:
            raise HTTPException(status_code=404, detail='Report not found.')
        return _report_to_dict(report)
    finally:
        db.close()


@app.put('/api/studies/{study_id}/report')
def update_report(study_id: str, payload: dict):
    db = _get_db()
    try:
        report = db.query(ReportRow).filter(ReportRow.study_id == study_id).first()
        if report is None:
            raise HTTPException(status_code=404, detail='Report not found.')

        if 'findings' in payload:
            report.findings = payload['findings']
        if 'impression' in payload:
            report.impression = payload['impression']
        if 'recommendation' in payload:
            report.recommendation = payload['recommendation']
        report.review_status = payload.get('reviewStatus', report.review_status)

        db.commit()
        db.refresh(report)
        return _report_to_dict(report)
    finally:
        db.close()


@app.post('/api/studies/{study_id}/review')
def mark_reviewed(study_id: str):
    db = _get_db()
    try:
        report = db.query(ReportRow).filter(ReportRow.study_id == study_id).first()
        if report is None:
            raise HTTPException(status_code=404, detail='Report not found.')
        report.review_status = 'REVIEWED'

        study = db.query(StudyRow).filter(StudyRow.study_id == study_id).first()
        if study:
            study.status = 'Reviewed'

        db.commit()
        return {'studyId': study_id, 'status': 'REVIEWED'}
    finally:
        db.close()


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(status_code=500, content={'detail': 'Unexpected server error.'})


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _study_to_dict(row: StudyRow) -> dict:
    return {
        'studyId': row.study_id,
        'createdAt': row.created_at.isoformat() if row.created_at else '',
        'status': row.status,
        'imageCount': row.image_count,
        'analysisStatus': row.analysis_status,
        'priority': row.priority,
        'overallRisk': row.overall_risk,
        'files': json.loads(row.files_json or '[]'),
    }


def _report_to_dict(row: ReportRow) -> dict:
    return {
        'studyId': row.study_id,
        'findings': row.findings,
        'impression': row.impression,
        'recommendation': row.recommendation,
        'generatedAt': row.generated_at.isoformat() if row.generated_at else '',
        'reviewStatus': row.review_status,
    }


# Serve built frontend static assets if available
FRONTEND_DIST = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
if FRONTEND_DIST.exists():
    app.mount('/', StaticFiles(directory=str(FRONTEND_DIST), html=True), name='frontend')

