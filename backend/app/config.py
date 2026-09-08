import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / '.env')

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://deven@localhost/kneeai')
API_URL = os.getenv('API_URL', 'http://localhost:8000')
UPLOAD_LIMIT_MB = int(os.getenv('UPLOAD_LIMIT_MB', '10'))

# Gemini API (primary inference provider — no local training needed)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

# Roboflow (optional fallback)
ROBOFLOW_API_KEY = os.getenv('ROBOFLOW_API_KEY', '')
ROBOFLOW_WORKSPACE = os.getenv('ROBOFLOW_WORKSPACE', '')
ROBOFLOW_WORKFLOW_ID = os.getenv('ROBOFLOW_WORKFLOW_ID', '')
