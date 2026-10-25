"""OpenAPI export. The committed docs/openapi.json is the frontend's contract."""

import json
from pathlib import Path

OPENAPI_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "openapi.json"


def render_openapi() -> str:
    from app.main import create_app

    return json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"
