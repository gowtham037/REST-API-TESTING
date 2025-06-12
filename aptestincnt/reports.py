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

ALLOWED_HEADERS = {
    "accept",
    "content-type",
    "authorization",
    "user-agent",
    "cache-control",
    "pragma",
    "x-request-id",
    "x-api-key"
}

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
            f.write("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>API Testing Report</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        h1 { color: #2c3e50; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
        th { background-color: #f0f0f0; } 
        .pass { color: green; font-weight: bold; }
        .fail { color: red; font-weight: bold; }
        .skip { color: gray; font-weight: bold; }
    </style>
</head>
<body>
    <h1>API Testing Report</h1>
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
                    len([i for i in entry['issues'] if "schema created" not in i.lower()]) == 0
                )
                final_result = "Passed" if final_pass else "Failed"

                if entry['schema_valid'] is True:
                    schema_status = '<span class="pass">Passed</span>'
                elif entry['schema_valid'] is False:
                    schema_status = '<span class="fail">Failed</span>'
                else:
                    schema_status = '<span class="skip">Skipped</span>'

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

def validate_custom_headers(headers):
    for key, val in headers.items():
        if key.lower() not in ALLOWED_HEADERS or val.strip() == "":
            return False
    return True

def get_response(url, method="GET", payload=None, custom_headers=None):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    if custom_headers:
        headers.update(custom_headers)

    start_time = time.time()
    method = method.upper()
    try:
        if method == "POST":
            response = requests.post(url, json=payload, headers=headers)
        elif method == "PUT":
            response = requests.put(url, json=payload, headers=headers)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
        elif method == "PATCH":
            response = requests.patch(url, json=payload, headers=headers)
        elif method == "HEAD":
            response = requests.head(url, headers=headers)
        elif method == "OPTIONS":
            response = requests.options(url, headers=headers)
        else:
            response = requests.get(url, headers=headers)
        elapsed = time.time() - start_time
        return response, elapsed
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return None, 0

def validate_response(url, method, report, payload=None, expected_schema=None, custom_headers=None):
    issues = []

    if custom_headers and not validate_custom_headers(custom_headers):
        issues.append("Invalid or disallowed headers provided.")
        report.add_entry(url, method, 0, None, issues, 0)
        return

    response, response_time = get_response(url, method, payload, custom_headers)
    if response is None:
        report.add_entry(url, method, 0, None, ["No response received"], 0)
        return

    status_code = response.status_code
    content_type = response.headers.get("Content-Type", "")
    schema_valid = None

    if not (200 <= status_code < 300):
        reason = HTTPStatus(status_code).phrase if status_code in HTTPStatus._value2member_map_ else "Unknown"
        issues.append(f"Unexpected status code: {status_code} {reason}")
        report.add_entry(url, method, status_code, None, issues, response_time)
        return

    if method in ["HEAD", "OPTIONS"]:
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
    print("🔍 Multi-Method API Validation Tool")

    try:
        num = int(input("🔢 Number of endpoints: "))
        endpoints = []

        for i in range(num):
            url = input(f"🌐 URL #{i + 1}: ").strip()
            method = input("📡 Method (GET/POST/PUT/DELETE/PATCH/HEAD/OPTIONS): ").strip().upper()

            payload = None
            expected_schema = None
            custom_headers = {}

            if method in ["POST", "PUT", "PATCH"]:
                body = input("📦 JSON payload (or leave blank): ").strip()
                if body:
                    try:
                        payload = json.loads(body)
                        define_schema = input("🧩 Define expected schema for payload? (y/n): ").strip().lower()
                        if define_schema == "y":
                            expected_schema = {}
                            for key in payload.keys():
                                dtype = input(f"🔍 Expected type for '{key}' (str/int/float/bool): ").strip().lower()
                                expected_schema[key] = {
                                    "str": str, "int": int, "float": float, "bool": bool
                                }.get(dtype, str)
                    except json.JSONDecodeError as e:
                        print(f"❌ Invalid JSON: {e}")
                        continue

            has_headers = input("📥 Add custom headers? (y/n): ").strip().lower()
            if has_headers == 'y':
                while True:
                    header_key = input("Header key (or leave blank to finish): ").strip()
                    if not header_key:
                        break
                    header_value = input("Header value: ").strip()
                    custom_headers[header_key] = header_value

            endpoints.append((url, method, payload, expected_schema, custom_headers))

        report = ReportGenerator()

        for url, method, payload, expected_schema, custom_headers in endpoints:
            print(f"\n🚀 Testing {method} {url}")
            validate_response(url, method, report, payload, expected_schema, custom_headers)

        report.generate_html()

    except KeyboardInterrupt:
        print("\n❗ Interrupted by user")
