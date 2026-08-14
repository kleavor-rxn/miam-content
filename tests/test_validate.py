import json
from pathlib import Path

import jsonschema

REPO = Path(__file__).resolve().parents[1]


def test_schemas_are_valid_jsonschema():
    for name in ["recipe", "ingredients", "index"]:
        schema = json.loads((REPO / "schema" / f"{name}.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
