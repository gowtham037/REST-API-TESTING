import os
import json
import requests
from genson import SchemaBuilder
from jsonschema import validate, ValidationError

SCHEMA_DIR = "schemas"
TESTCASE_FILE = "testcases.json"


def save_schema(name, schema):
    os.makedirs(SCHEMA_DIR, exist_ok=True)
    path = os.path.join(SCHEMA_DIR, f"{name}.json")
    with open(path, "w") as f:
        json.dump(schema, f, indent=2)
    print(f"Schema saved to {path}")


def load_schema(name):
    path = os.path.join(SCHEMA_DIR, f"{name}.json")
    if not os.path.exists(path):
        print(f"No schema found for '{name}'")
        return None
    with open(path) as f:
        return json.load(f)


def generate_schema_from_response(url, headers=None):
    print(f"\n🔄 Sending request to: {url}")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None, None

    try:
        data = response.json()
        builder = SchemaBuilder()
        builder.add_object(data)
        schema = builder.to_schema()
        print("✅ Generated JSON Schema:\n", json.dumps(schema, indent=2))
        return data, schema
    except Exception as e:
        print(f"❌ Failed to process JSON response: {e}")
        return None, None


def validate_against_schema(url, schema, headers=None):
    print(f"\n🔍 Validating response from: {url}")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        validate(instance=data, schema=schema)
        print("✅ Validation passed against the generated schema.")
        return True
    except ValidationError as ve:
        print(f"❌ Validation failed: {ve.message}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def run_test_cases(testcases):
    results = []
    for tc in testcases:
        print(f"\n===== Running test case: {tc['name']} =====")
        schema = None

        # Load existing schema if exists
        if tc.get("use_existing_schema", False):
            schema = load_schema(tc["schema_name"])
            if schema is None:
                print(f"Skipping test '{tc['name']}' - schema not found.")
                results.append({"name": tc["name"], "status": "SKIPPED"})
                continue
        else:
            # Generate schema from first response if requested
            if tc.get("generate_schema", False):
                _, schema = generate_schema_from_response(tc["url"], tc.get("headers"))
                if schema:
                    save_schema(tc["schema_name"], schema)
                else:
                    print(f"Failed to generate schema for '{tc['name']}'")
                    results.append({"name": tc["name"], "status": "FAILED"})
                    continue

        if schema:
            # Validate response against schema
            valid = validate_against_schema(tc["url"], schema, tc.get("headers"))
            results.append({"name": tc["name"], "status": "PASS" if valid else "FAIL"})
        else:
            print(f"No schema available for test '{tc['name']}'")
            results.append({"name": tc["name"], "status": "NO SCHEMA"})

    print("\n=== TEST SUMMARY ===")
    for r in results:
        print(f"Test '{r['name']}': {r['status']}")
    return results


if __name__ == "__main__":
    # Load test cases from JSON file
    if not os.path.exists(TESTCASE_FILE):
        print(f"Test case file '{TESTCASE_FILE}' not found. Please create it.")
        print("Sample test case file structure:")
        print(json.dumps([
            {
                "name": "Get post 1",
                "url": "https://jsonplaceholder.typicode.com/posts/1",
                "schema_name": "post_1_schema",
                "generate_schema": True,
                "use_existing_schema": False,
                "headers": None
            },
            {
                "name": "Validate post 1",
                "url": "https://jsonplaceholder.typicode.com/posts/1",
                "schema_name": "post_1_schema",
                "generate_schema": False,
                "use_existing_schema": True,
                "headers": None
            }
        ], indent=2))
        exit(1)

    with open(TESTCASE_FILE) as f:
        testcases = json.load(f)

    run_test_cases(testcases)

    # Future: Add AI-based schema improvements here
    # e.g., call an AI model to optimize or extend the schema based on many samples
