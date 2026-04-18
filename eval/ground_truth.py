import json
from pathlib import Path

BASE_PATH = Path(__file__).resolve().parent.parent


def load_ground_truth(document_id: str) -> dict:
    """
    Load ground truth JSON for a given document_id.
    Returns the extraction-like payload regardless of wrapper shape.
    """
    path = BASE_PATH / "data" / "ground_truth" / f"{document_id}.json"

    if not path.exists():
        raise FileNotFoundError(f"No ground truth found for {document_id}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Try common wrapper shapes
    if isinstance(data, dict):
        if "ground_truth" in data and isinstance(data["ground_truth"], dict):
            return data["ground_truth"]
        if "extraction" in data and isinstance(data["extraction"], dict):
            return data["extraction"]

    return data