from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.config import GEMINI_API_KEY, ROBOFLOW_API_KEY, ROBOFLOW_WORKSPACE, ROBOFLOW_WORKFLOW_ID

logger = logging.getLogger(__name__)


class InferenceProvider(ABC):
    @abstractmethod
    def predict(self, images: list[str]) -> dict[str, float]:
        raise NotImplementedError


class GeminiInferenceProvider(InferenceProvider):
    """Analyze knee MRI/X-ray scans using Google Gemini Vision API."""

    TARGETS = [
        'ACL', 'MCL', 'Medial Meniscus', 'Lateral Meniscus', 'Medial OA',
        'Lateral OA', 'PF OA', 'Effusion', 'Synovitis', "Baker's",
        'Contusion', 'Fracture',
    ]

    def __init__(self, api_key: str = ''):
        self.api_key = api_key or GEMINI_API_KEY
        if not self.api_key:
            raise ValueError(
                'GEMINI_API_KEY is required. '
                'Set it in your .env file or pass it directly.'
            )

        from google import genai
        self.client = genai.Client(api_key=self.api_key)

    def predict(self, images: list[str]) -> dict[str, float]:
        if not images:
            return {t: 0.0 for t in self.TARGETS}

        import json
        from PIL import Image

        pil_images = []
        for img_path in images:
            try:
                pil_images.append(Image.open(img_path))
            except Exception:
                logger.warning('Could not open image file: %s', img_path)

        if not pil_images:
            return {t: 0.0 for t in self.TARGETS}

        prompt = (
            "You are an expert musculoskeletal radiologist. Analyze the provided knee MRI/X-ray image(s).\n"
            "Evaluate the probability (between 0.00 and 1.00) of presence for each of the following 12 knee abnormalities:\n"
            "- ACL (Anterior Cruciate Ligament tear/sprain)\n"
            "- MCL (Medial Collateral Ligament tear/sprain)\n"
            "- Medial Meniscus (Medial Meniscal tear/degeneration)\n"
            "- Lateral Meniscus (Lateral Meniscal tear/degeneration)\n"
            "- Medial OA (Medial Compartment Osteoarthritis)\n"
            "- Lateral OA (Lateral Compartment Osteoarthritis)\n"
            "- PF OA (Patellofemoral Osteoarthritis)\n"
            "- Effusion (Joint effusion/fluid accumulation)\n"
            "- Synovitis (Synovial inflammation/thickening)\n"
            "- Baker's (Baker's cyst/popliteal cyst)\n"
            "- Contusion (Bone contusion/marrow edema)\n"
            "- Fracture (Cortical fracture/trabecular injury)\n\n"
            "Return ONLY valid JSON matching this exact structure mapping each abnormality name to a float probability:\n"
            "{\n"
            '  "ACL": 0.15,\n'
            '  "MCL": 0.05,\n'
            '  "Medial Meniscus": 0.85,\n'
            '  "Lateral Meniscus": 0.10,\n'
            '  "Medial OA": 0.60,\n'
            '  "Lateral OA": 0.10,\n'
            '  "PF OA": 0.20,\n'
            '  "Effusion": 0.75,\n'
            '  "Synovitis": 0.30,\n'
            '  "Baker\'s": 0.05,\n'
            '  "Contusion": 0.25,\n'
            '  "Fracture": 0.00\n'
            "}"
        )

        try:
            contents = [*pil_images, prompt]
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents,
            )

            raw_text = (response.text or '').strip()
            if raw_text.startswith('```'):
                lines = raw_text.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                raw_text = '\n'.join(lines).strip()

            data = json.loads(raw_text)

            result = {}
            for target in self.TARGETS:
                val = data.get(target, 0.0)
                try:
                    result[target] = round(min(1.0, max(0.0, float(val))), 4)
                except (ValueError, TypeError):
                    result[target] = 0.0
            return result
        except Exception:
            logger.exception('Gemini API inference failed')
            raise


class PrototypeInferenceProvider(InferenceProvider):
    """Deterministic demo predictions — no real model, no API calls."""

    def __init__(self):
        self.abnormalities = [
            'ACL', 'MCL', 'Medial Meniscus', 'Lateral Meniscus', 'Medial OA',
            'Lateral OA', 'PF OA', 'Effusion', 'Synovitis', "Baker's",
            'Contusion', 'Fracture'
        ]

    def predict(self, images: list[str]) -> dict[str, float]:
        seed = sum(len(image) for image in images) if images else 0
        values = {}
        for idx, abnormality in enumerate(self.abnormalities):
            base = ((seed + idx * 17) % 101) / 100
            adjusted = min(0.98, max(0.05, base))
            values[abnormality] = round(adjusted, 4)
        return values


class RoboflowInferenceProvider(InferenceProvider):
    """Send images to the Roboflow Workflow API and parse predictions.

    The Roboflow workflow should be configured to return classification
    probabilities for knee abnormalities.  If the API returns detection-style
    results, we map class names to the 12 abnormality targets.
    """

    TARGETS = [
        'ACL', 'MCL', 'Medial Meniscus', 'Lateral Meniscus', 'Medial OA',
        'Lateral OA', 'PF OA', 'Effusion', 'Synovitis', "Baker's",
        'Contusion', 'Fracture',
    ]

    def __init__(
        self,
        api_key: str = '',
        workspace: str = '',
        workflow_id: str = '',
    ):
        self.api_key = api_key or ROBOFLOW_API_KEY
        self.workspace = workspace or ROBOFLOW_WORKSPACE
        self.workflow_id = workflow_id or ROBOFLOW_WORKFLOW_ID

        if not self.api_key:
            raise ValueError(
                'ROBOFLOW_API_KEY is required. '
                'Set it in your .env file or pass it directly.'
            )

        from inference_sdk import InferenceHTTPClient, InferenceConfiguration

        self.client = InferenceHTTPClient(
            api_url='https://serverless.roboflow.com',
            api_key=self.api_key,
        ).configure(InferenceConfiguration(
            api_key_transport='header',
        ))

    def predict(self, images: list[str]) -> dict[str, float]:
        """Run inference on the first uploaded image via the Roboflow workflow.

        The workflow is expected to return predictions that can be mapped to
        the 12 knee abnormality targets.
        """
        if not images:
            return {t: 0.0 for t in self.TARGETS}

        # Aggregate results across all images
        aggregated: dict[str, list[float]] = {t: [] for t in self.TARGETS}

        for image_path in images:
            try:
                result = self.client.run_workflow(
                    workspace_name=self.workspace,
                    workflow_id=self.workflow_id,
                    images={'image': image_path},
                    parameters={'classes': 'knee'},
                    use_cache=True,
                )
                self._parse_result(result, aggregated)
            except Exception:
                logger.exception('Roboflow inference failed for %s', image_path)

        # Average across images, default 0.0 if no results
        return {
            target: round(
                sum(scores) / len(scores) if scores else 0.0, 4
            )
            for target, scores in aggregated.items()
        }

    def _parse_result(
        self,
        result: list | dict,
        aggregated: dict[str, list[float]],
    ) -> None:
        """Extract probabilities from Roboflow workflow response.

        Roboflow workflows return a list of output dicts. The shape depends
        on how the workflow is configured.  We handle the common patterns:

        1. Classification: result[0]['predictions'] is a dict of class→confidence
        2. Detection: result[0]['predictions'] is a list of detection dicts
        3. Flat dict: result[0] contains keys matching target names
        """
        if not result:
            return

        payload = result[0] if isinstance(result, list) else result

        # Pattern 1: predictions as dict  {class_name: confidence}
        preds = payload.get('predictions', payload)

        if isinstance(preds, dict):
            for target in self.TARGETS:
                key_lower = target.lower()
                for key, value in preds.items():
                    if isinstance(value, (int, float)) and key.lower() == key_lower:
                        aggregated[target].append(float(value))

        # Pattern 2: predictions as list of detection dicts
        elif isinstance(preds, list):
            for det in preds:
                if not isinstance(det, dict):
                    continue
                class_name = det.get('class', '')
                confidence = det.get('confidence', 0.0)
                for target in self.TARGETS:
                    if class_name.lower() == target.lower():
                        aggregated[target].append(float(confidence))


class MRIInferenceService:
    """Facade that delegates to whichever provider is configured."""

    def __init__(self, provider: InferenceProvider | None = None):
        self.provider = provider or PrototypeInferenceProvider()

    def predict(self, images: list[str]) -> dict[str, float]:
        return self.provider.predict(images)


def get_inference_provider() -> InferenceProvider:
    """Return the best available provider based on environment config."""
    if GEMINI_API_KEY:
        try:
            return GeminiInferenceProvider()
        except Exception:
            logger.warning('Gemini setup failed, trying Roboflow fallback.')
    if ROBOFLOW_API_KEY:
        try:
            return RoboflowInferenceProvider()
        except Exception:
            logger.warning('Roboflow setup failed, falling back to prototype mode.')
    return PrototypeInferenceProvider()

