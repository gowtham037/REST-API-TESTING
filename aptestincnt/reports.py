import requests
import json
import datetime
import time
from genson import SchemaBuilder
from jsonschema import validate, ValidationError, SchemaError
import os
from http import HTTPStatus
import hashlib

SCHEMA_DIR = "schemas"
os.makedirs(SCHEMA_DIR, exist_ok=True)

def schema_filename(url, method):
    unique_id = hashlib.md5(f"{method}_{url}".encode()).hexdigest()
    return os.path.join(SCHEMA_DIR, f"{unique_id}_schema.json")

class ReportGenerator:
    def __init__(self):
        self.entries = []

    def add_entry(self, url, method, status_code, schema_valid, issues, response_time):
        self.entries.append({
            "url": url,
            "method": method,
            "status_code": status_code,
            "schema_valid": schema_valid,
            "issues": issues,
            "response_time": response_time
        })

    def generate_html(self, filename="reports.html"):
        file_path = os.path.join(os.getcwd(), filename)
        with open(file_path, "w") as f:
            f.write(f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>API Testing Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; }}
        h1 {{ color: #2c3e50; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
        th {{ background-color: #f0f0f0; }}
        .pass {{ color: green; font-weight: bold; }}
        .fail {{ color: red; font-weight: bold; }}
        .skip {{ color: gray; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>API Testing Report</h1>
    <p>Generated on: {str(datetime.datetime.now())}</p>
    <table>
        <tr>
            <th>Method</th>
            <th>URL</th>
            <th>Status Code</th>
            <th>Response Time (s)</th>
            <th>Schema Validation</th>
            <th>Issues</th>
            <th>Final Result</th>
        </tr>""")
            for entry in self.entries:
                final_pass = (200 <= entry['status_code'] < 300) and (
                    len(entry['issues']) == 0 or (entry['schema_valid'] is None))

                final_result = "Passed" if final_pass else "Failed"

                schema_status = '<span class="skip">Skipped</span>'
                if entry['schema_valid'] is True:
                    schema_status = '<span class="pass">Passed</span>'
                elif entry['schema_valid'] is False:
                    schema_status = '<span class="fail">Failed</span>'

                final_class = "pass" if final_pass else "fail"
                issues_str = "<br>".join(entry['issues']) if entry['issues'] else "None"

                f.write(f"""
        <tr>
            <td>{entry['method']}</td>
            <td>{entry['url']}</td>
            <td>{entry['status_code']}</td>
            <td>{entry['response_time']:.3f}</td>
            <td>{schema_status}</td>
            <td>{issues_str}</td>
            <td class="{final_class}">{final_result}</td>
        </tr>""")
            f.write("""
    </table>
</body>
</html>""")
        print(f"\n📄 Report saved at: {file_path}")

def get_response(url, method="GET", payload=None):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    start_time = time.time()
    method = method.upper()
    try:
        if method == "POST":
            response = requests.post(url, json=payload, headers=headers)
        elif method == "PUT":
            response = requests.put(url, json=payload, headers=headers)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            response = requests.get(url, headers=headers)
        elapsed = time.time() - start_time
        return response, elapsed
    except requests.exceptions.RequestException:
        return None, 0

def validate_payload(payload, expected_schema=None):
    issues = []
    if not expected_schema:
        return issues  # No validation
    for key, expected_type in expected_schema.items():
        if key not in payload:
            issues.append(f"Missing field: {key}")
        elif not isinstance(payload[key], expected_type):
            issues.append(
                f"Field '{key}' should be {expected_type.__name__}, got {type(payload[key]).__name__}")
    return issues

def validate_response(url, method, report, payload=None, expected_schema=None):
    issues = []

    if method in ["POST", "PUT"] and payload:
        payload_issues = validate_payload(payload, expected_schema)
        if payload_issues:
            report.add_entry(url, method, 0, False, payload_issues, 0)
            return

    response, response_time = get_response(url, method, payload)
    if response is None:
        report.add_entry(url, method, 0, False, ["No response received"], 0)
        return

    status_code = response.status_code
    content_type = response.headers.get("Content-Type", "")
    schema_valid = None

    if not (200 <= status_code < 300):
        reason = HTTPStatus(status_code).phrase if status_code in HTTPStatus._value2member_map_ else "Unknown"
        issues.append(f"Unexpected status code: {status_code} {reason}")
        report.add_entry(url, method, status_code, None, issues, response_time)
        return

    if "application/json" not in content_type.lower():
        issues.append(f"Invalid content type: {content_type}")
        report.add_entry(url, method, status_code, None, issues, response_time)
        return

    if response_time > 2:
        issues.append(f"Response time too long: {response_time:.3f}s")

    try:
        data = response.json()
        schema_file = schema_filename(url, method)

        if not os.path.exists(schema_file):
            builder = SchemaBuilder()
            builder.add_object(data)
            schema = builder.to_schema()
            with open(schema_file, "w") as f:
                json.dump(schema, f, indent=2)
            issues.append("Schema created and saved (baseline)")
            schema_valid = True
        else:
            with open(schema_file) as f:
                schema = json.load(f)
            try:
                validate(instance=data, schema=schema)
                schema_valid = True
            except (ValidationError, SchemaError) as ve:
                schema_valid = False
                issues.append(f"Schema validation failed: {ve.message}")
    except json.JSONDecodeError:
        schema_valid = False
        issues.append("Invalid JSON in response")

    report.add_entry(url, method, status_code, schema_valid, issues, response_time)

if __name__ == "__main__":
    print("🔧 Multi-Method API Validation Tool")

    try:
        num = int(input("🔢 Number of endpoints: "))
        endpoints = []

        for i in range(num):
            url = input(f"🌐 URL #{i + 1}: ").strip()
            if not url.startswith("http"):
                print("❌ Invalid URL")
                continue

            method = input("🔁 Method (GET/POST/PUT/DELETE): ").strip().upper()
            if method not in ["GET", "POST", "PUT", "DELETE"]:
                print("❌ Invalid method")
                continue

            payload = None
            expected_schema = None
            if method in ["POST", "PUT"]:
                body = input("📦 JSON payload: ").strip()
                if body:
                    try:
                        payload = json.loads(body)
                        # Optional: Define expected schema here
                        define_schema = input("🎯 Want to define expected schema? (y/n): ").strip().lower()
                        if define_schema == "y":
                            expected_schema = {}
                            for key in payload.keys():
                                dtype = input(f"🔡 Expected type for '{key}' (str/int/float/bool): ").strip().lower()
                                expected_schema[key] = {
                                    "str": str, "int": int, "float": float, "bool": bool
                                }.get(dtype, str)
                    except json.JSONDecodeError as e:
                        print(f"❌ Invalid JSON: {e}")
                        continue

            endpoints.append((url, method, payload, expected_schema))

        report = ReportGenerator()
        for url, method, payload, expected_schema in endpoints:
            validate_response(url, method, report, payload, expected_schema)
 
        report.generate_html()
        
    except Exception as e:
        print(f"❌ Error: {e}")
