from __future__ import annotations

from datetime import datetime, timezone
import logging
from app.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)


def confidence_label(probability: float) -> str:
    if probability >= 0.75:
        return 'High'
    if probability > 0.4:
        return 'Moderate'
    return 'Low'


def build_top_findings(predictions: dict[str, float], limit: int = 3):
    ranked = sorted(predictions.items(), key=lambda item: item[1], reverse=True)
    return [
        {'abnormality': name, 'probability': prob, 'confidence': confidence_label(prob)}
        for name, prob in ranked[:limit]
    ]


def generate_report(study_id: str, predictions: dict[str, float]) -> dict:
    # Try Gemini report generation if key is present
    if GEMINI_API_KEY:
        try:
            import json
            from google import genai

            client = genai.Client(api_key=GEMINI_API_KEY)
            prompt = (
                f"You are a senior musculoskeletal radiologist writing a clinical report for study {study_id}.\n"
                f"The AI vision analysis evaluated 12 knee abnormalities with the following probabilities:\n"
                f"{json.dumps(predictions, indent=2)}\n\n"
                "Generate a concise, professional radiology report with 3 fields:\n"
                "1. 'findings': Detailed breakdown of significant findings.\n"
                "2. 'impression': Diagnostic summary / conclusion.\n"
                "3. 'recommendation': Next clinical or diagnostic steps.\n\n"
                "Return ONLY a JSON object with keys 'findings', 'impression', and 'recommendation'."
            )
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            raw_text = (response.text or '').strip()
            if raw_text.startswith('```'):
                lines = raw_text.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                raw_text = '\n'.join(lines).strip()

            report_data = json.loads(raw_text)
            if 'findings' in report_data and 'impression' in report_data and 'recommendation' in report_data:
                return {
                    'studyId': study_id,
                    'findings': report_data['findings'],
                    'impression': report_data['impression'],
                    'recommendation': report_data['recommendation'],
                    'generatedAt': datetime.now(timezone.utc).isoformat(),
                    'reviewStatus': 'pending',
                }
        except Exception:
            logger.warning('Gemini report generation failed, using rule-based report generator.')

    # Fallback / default rule-based generation
    findings = []
    for abnormality, probability in sorted(predictions.items(), key=lambda item: item[1], reverse=True):
        level = confidence_label(probability)
        if probability >= 0.75:
            findings.append(f'AI identified a {level.lower()} probability of {abnormality} abnormality.')
        elif probability > 0.4:
            findings.append(f'AI flagged {abnormality} as a {level.lower()} priority finding.')
    findings_text = ' '.join(findings) if findings else 'No major abnormalities were flagged by the vision model.'

    high = any(probability >= 0.75 for probability in predictions.values())
    if high:
        impression = 'AI analysis flags potential knee abnormalities requiring radiologist review.'
    else:
        impression = 'AI analysis suggests no dominant high-confidence findings; radiologist correlation remains recommended.'

    recommendation = 'Review AI-highlighted regions and correlate with clinical findings.'
    return {
        'studyId': study_id,
        'findings': findings_text,
        'impression': impression,
        'recommendation': recommendation,
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'reviewStatus': 'pending',
    }
