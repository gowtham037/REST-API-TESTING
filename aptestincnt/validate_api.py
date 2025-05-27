import requests
import json
import uuid
from jsonschema import Draft7Validator, SchemaError

def is_valid_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False

def validate_response(url, user_schema):
    try:
        response = requests.get(url, timeout=5)

        # HTTP status code check
        print(f"🔍 HTTP Status Code: {response.status_code}")
        if response.status_code != 200:
            print(f"❌ Unexpected HTTP status code: {response.status_code}")
            return

        # Content-Type header validation
        content_type = response.headers.get("Content-Type", "")
        print(f"🔍 Content-Type: {content_type}")
        if "application/json" not in content_type:
            print("❌ Response is not JSON.")
            return

        data = response.json()

        # JSON Schema validation using Draft7Validator
        try:
            validator = Draft7Validator(user_schema)
            errors = list(validator.iter_errors(data))
            if errors:
                print("❌ Schema validation failed:")
                for error in errors:
                    print(f"• {error.message}")
            else:
                print("✅ Schema validation passed.")
        except SchemaError as se:
            print("❌ Invalid schema structure:")
            print(se.message)
            return

        # Data correctness checks
        print("🔎 Performing data correctness checks...")

        def check_uuid_in_data(item):
            id_value = item.get("id")
            if isinstance(id_value, str) and not is_valid_uuid(id_value):
                print(f"❌ Invalid UUID format: {id_value}")

        if isinstance(data, list):
            for item in data:
                check_uuid_in_data(item)
        elif isinstance(data, dict):
            check_uuid_in_data(data)
        else:
            print("⚠️ Unexpected data structure. Skipping UUID checks.")

        print("✅ All checks completed.")

    except requests.exceptions.RequestException as re:
        print("❌ Request failed:")
        print(str(re))
    except Exception as e:
        print("❌ An unexpected error occurred:")
        print(str(e))


if __name__ == "__main__":
    # Input URL
    url = input("Enter the API endpoint URL: ").strip()

    # Input multiline JSON schema
    print("\nPaste your JSON schema below. Press Enter twice to finish:")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)

    try:
        schema_input = "\n".join(lines)
        user_schema = json.loads(schema_input)
    except json.JSONDecodeError as e:
        print("❌ Invalid JSON schema provided:")
        print(str(e))
        exit(1)

    validate_response(url, user_schema)
