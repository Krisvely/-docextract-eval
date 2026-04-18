import argparse
import json
import requests

BASE_URL = "http://localhost:8000"


def extract(document_id: str, model: str = "v1", seed: int | None = 42) -> None:
    url = f"{BASE_URL}/extract"
    payload = {
        "document_id": document_id,
        "model": model,
        "seed": seed,
    }

    response = requests.post(url, json=payload, timeout=30)

    print("Status:", response.status_code)

    try:
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception:
        print(response.text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--document-id", default="loss_run_libertymutual")
    parser.add_argument("--model", default="v1", choices=["v1", "v2"])
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    extract(
        document_id=args.document_id,
        model=args.model,
        seed=args.seed,
    )