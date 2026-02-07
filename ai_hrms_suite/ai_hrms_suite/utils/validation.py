from jsonschema import validate


def validate_json(data: dict, schema: dict):
    validate(instance=data, schema=schema)
