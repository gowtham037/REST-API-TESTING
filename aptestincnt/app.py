import requests
import json
import uuid
from genson import SchemaBuilder
from jsonschema import validate, ValidationError, SchemaError

def is_valid_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False

def generate_schema_from_response(url):
    print(f"\n🔄 Sending request to: {url}")
    response = requests.get(url)

    # HTTP Status Code Check
    print(f"🔍 HTTP Status Code: {response.status_code}")
    if response.status_code != 200:
        print(f" Request failed with status code {response.status_code}")
        return None, None

    # Content-Type Validation
    content_type = response.headers.get("Content-Type", "")
    print(f"🔍 Content-Type: {content_type}")
    if "application/json" not in content_type:
        print("❌ Content-Type is not application/json.")
        return None, None

    try:
        data = response.json()
        builder = SchemaBuilder()
        builder.add_object(data)
        schema = builder.to_schema()
        print("\n✅ Generated JSON Schema:\n", json.dumps(schema, indent=2))
        return data, schema
    except Exception as e:
        print(f"❌ Failed to process JSON response: {e}")
        return None, None

def validate_against_schema(url, schema):
    print(f"\n🔍 Validating response from: {url}")
    try:
        response = requests.get(url)
        print(f"🔍 HTTP Status Code: {response.status_code}")
        if response.status_code != 200:
            print(f"❌ Unexpected status code: {response.status_code}")
            return

        content_type = response.headers.get("Content-Type", "")
        print(f"🔍 Content-Type: {content_type}")
        if "application/json" not in content_type:
            print("❌ Content-Type is not application/json.")
            return

        data = response.json()

        # Validate against schema
        try:
            validate(instance=data, schema=schema)
            print("✅ Schema validation passed.")
        except ValidationError as ve:
            print("❌ Schema validation failed:")
            print(ve.message)
            return
        except SchemaError as se:
            print("❌ Invalid schema structure:")
            print(se.message)
            return

        # Data correctness checks
        print("🔎 Performing data correctness checks...")
        if isinstance(data, list):
            for item in data:
                id_value = item.get("id")
                if isinstance(id_value, str):
                    if not is_valid_uuid(id_value):
                        print(f"❌ Invalid UUID format: {id_value}")
        else:
            print("⚠️ Expected a list of items for correctness checks.")

        print("✅ All checks completed.")

    except requests.exceptions.RequestException as re:
        print(f"❌ Request error: {re}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    target_url = input("Enter an API URL to test (e.g. https://jsonplaceholder.typicode.com/users): ").strip()

    sample_data, schema = generate_schema_from_response(target_url)
    if schema:
        again = input("\nDo you want to validate another response using this schema? (y/n): ").strip().lower()
        if again == 'y':
            validate_against_schema(target_url, schema)
