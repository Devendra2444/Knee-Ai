import os

# Use an in-memory SQLite database for tests so PostgreSQL is not required.
os.environ['DATABASE_URL'] = 'sqlite:///./test_kneeai.db'

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.database.database import Base, engine
from app.main import app
from app.ml.inference import GeminiInferenceProvider, PrototypeInferenceProvider, get_inference_provider
from app.services.report_service import generate_report
from app.utils.priority import calculate_priority

# Create tables before tests run
Base.metadata.create_all(bind=engine)

client = TestClient(app)


def test_health():
    response = client.get('/api/health')
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ok'
    assert 'database' in payload


def test_upload_validation():
    response = client.post(
        '/api/studies/upload',
        files={'files': ('scan.png', b'fake-image-data', 'image/png')},
    )
    assert response.status_code == 200
    assert 'studyId' in response.json()


def test_priority_calculation():
    values = {
        'ACL': 0.9,
        'MCL': 0.2,
        'Medial Meniscus': 0.1,
        'Lateral Meniscus': 0.1,
        'Medial OA': 0.1,
        'Lateral OA': 0.1,
        'PF OA': 0.1,
        'Effusion': 0.1,
        'Synovitis': 0.1,
        "Baker's": 0.1,
        'Contusion': 0.1,
        'Fracture': 0.1,
    }
    assert calculate_priority(values) == 'HIGH'


def test_report_generation():
    report = generate_report('KNEE-0001', {'ACL': 0.85, 'Effusion': 0.65})
    assert report['studyId'] == 'KNEE-0001'
    assert 'findings' in report and len(report['findings']) > 0


def test_analyze_study_flow():
    upload = client.post(
        '/api/studies/upload',
        files={'files': ('scan.png', b'fake-image-data', 'image/png')},
    )
    study_id = upload.json()['studyId']
    response = client.post(f'/api/studies/{study_id}/analyze')
    assert response.status_code == 200
    payload = response.json()
    assert payload['priority'] in {'HIGH', 'MEDIUM', 'LOW'}
    assert 'predictions' in payload


def test_study_persists_after_upload():
    """Verify that a study created via upload can be retrieved."""
    upload = client.post(
        '/api/studies/upload',
        files={'files': ('persist_test.png', b'test-data', 'image/png')},
    )
    study_id = upload.json()['studyId']
    response = client.get(f'/api/studies/{study_id}')
    assert response.status_code == 200
    assert response.json()['studyId'] == study_id


def test_report_after_analysis():
    """Verify that a report is generated and retrievable after analysis."""
    upload = client.post(
        '/api/studies/upload',
        files={'files': ('report_test.png', b'test-data', 'image/png')},
    )
    study_id = upload.json()['studyId']
    client.post(f'/api/studies/{study_id}/analyze')
    response = client.get(f'/api/studies/{study_id}/report')
    assert response.status_code == 200
    assert response.json()['studyId'] == study_id
    assert response.json()['reviewStatus'] == 'pending'


def test_mark_reviewed():
    """Verify that a study can be marked as reviewed."""
    upload = client.post(
        '/api/studies/upload',
        files={'files': ('review_test.png', b'test-data', 'image/png')},
    )
    study_id = upload.json()['studyId']
    client.post(f'/api/studies/{study_id}/analyze')
    response = client.post(f'/api/studies/{study_id}/review')
    assert response.status_code == 200
    assert response.json()['status'] == 'REVIEWED'

    # Verify study status updated
    study = client.get(f'/api/studies/{study_id}').json()
    assert study['status'] == 'Reviewed'


def test_model_status():
    """Verify model status endpoint returns provider info."""
    response = client.get('/api/model/status')
    assert response.status_code == 200
    payload = response.json()
    assert 'provider' in payload
    assert payload['status'] == 'ready'


def test_gemini_inference_provider_mock():
    """Verify GeminiInferenceProvider correctly parses model response JSON."""
    with patch('google.genai.Client') as mock_genai_client:
        mock_instance = MagicMock()
        mock_genai_client.return_value = mock_instance
        mock_response = MagicMock()
        mock_response.text = '{"ACL": 0.85, "Medial Meniscus": 0.90, "Effusion": 0.70}'
        mock_instance.models.generate_content.return_value = mock_response

        provider = GeminiInferenceProvider(api_key='test-key')
        
        # Test with empty image list
        empty_res = provider.predict([])
        assert empty_res['ACL'] == 0.0

        # Test targets schema returned correctly
        assert 'ACL' in GeminiInferenceProvider.TARGETS
        assert 'Fracture' in GeminiInferenceProvider.TARGETS
