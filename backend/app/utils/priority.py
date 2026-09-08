ABNORMALITIES = [
    'ACL',
    'MCL',
    'Medial Meniscus',
    'Lateral Meniscus',
    'Medial OA',
    'Lateral OA',
    'PF OA',
    'Effusion',
    'Synovitis',
    "Baker's",
    'Contusion',
    'Fracture',
]


def calculate_priority(predictions: dict[str, float]) -> str:
    if not predictions:
        return 'LOW'

    high_confidence = any(predictions.get(name, 0.0) >= 0.75 for name in ABNORMALITIES)
    if high_confidence:
        return 'HIGH'

    moderate = any(0.4 <= predictions.get(name, 0.0) < 0.75 for name in ABNORMALITIES)
    if moderate:
        return 'MEDIUM'

    return 'LOW'


def calculate_priority_score(predictions: dict[str, float]) -> float:
    values = [float(predictions.get(name, 0.0)) for name in ABNORMALITIES]
    return round(sum(values) / max(len(values), 1), 4)
