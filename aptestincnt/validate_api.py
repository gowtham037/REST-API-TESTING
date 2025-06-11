import requests
import json
import time
import os
from jsonschema import Draft7Validator, SchemaError, ValidationError
from datetime import datetime

REPORT_PATH = "expected_schema_report.html"

class Report:
    def __init__(self):
        self.entries = []

    def add_entry(self, url, method, status_code, response_time, schema_valid, issues):
        self.entries.append({
            "timestamp": datetime.now().isoformat(),
            "method": method,
            "url": url,
            "status": status_code,
            "response_time": response_time,
            "schema_valid": schema_valid,
            "issues": issues
        })

    def save(self):
        with open(REPORT_PATH, "w") as f:
            f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>Expected Schema API Validation Report</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        h1 { color: #2c3e50; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ccc; padding: 10px; text-align: left; }
        th { background-color: #f0f0f0; }
        .pass { color: green; font-weight: bold; }
        .fail { color: red; font-weight: bold; }
        .gray { color: gray; }
    </style>
</head>
<body>
    <h1>API Testing Report (Expected Schema)</h1>
    <table>
        <tr>
            <th>Time</th>
            <th>Method</th>
            <th>URL</th>
            <th>Status</th>
            <th>Time (s)</th>
            <th>Schema</th>
            <th>Issues</th>
        </tr>
""")
            for e in self.entries:
                schema_status = '<span class="pass">Passed</span>' if e['schema_valid'] else '<span class="fail">Failed</span>'
                issues_str = "<br>".join(e['issues']) if e['issues'] else "None"
                f.write(f"""
        <tr>
            <td>{e['timestamp']}</td>
            <td>{e['method']}</td>
            <td>{e['url']}</td>
            <td>{e['status']}</td>
            <td>{e['response_time']:.2f}</td>
            <td>{schema_status}</td>
            <td>{issues_str}</td>
        </tr>""")
            f.write("""
    </table>
</body>
</html>
""")
        print(f"\n📄 Report saved to: {REPORT_PATH}")

def validate_response(url, method, user_schema, report, payload=None, custom_headers=None):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    if custom_headers:
        headers.update(custom_headers)

    method = method.upper()
    try:
        start_time = time.time()
        if method == "POST":
            response = requests.post(url, json=payload, headers=headers, timeout=5)
        elif method == "PUT":
            response = requests.put(url, json=payload, headers=headers, timeout=5)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, timeout=5)
        else:
            response = requests.get(url, headers=headers, timeout=5)
        elapsed_time = time.time() - start_time

        print(f"\n🔍 HTTP Status Code: {response.status_code}")
        print(f"⏱️ Response Time: {elapsed_time:.2f} seconds")

        issues = []

        if not (200 <= response.status_code < 300):
            issues.append(f"Unexpected HTTP {response.status_code}: {response.text}")
            report.add_entry(url, method, response.status_code, elapsed_time, False, issues)
            return

        content_type = response.headers.get("Content-Type", "")
        print(f"🔍 Content-Type: {content_type}")
        if "application/json" not in content_type:
            issues.append("❌ Response is not JSON")
            report.add_entry(url, method, response.status_code, elapsed_time, False, issues)
            return

        try:
            data = response.json()
        except json.JSONDecodeError:
            issues.append("❌ Failed to parse response JSON.")
            report.add_entry(url, method, response.status_code, elapsed_time, False, issues)
            return

        # Schema validation
        try:
            validator = Draft7Validator(user_schema)
            errors = list(validator.iter_errors(data))
            if errors:
                for err in errors:
                    issues.append(err.message)
                schema_valid = False
            else:
                schema_valid = True
        except SchemaError as se:
            issues.append(f"Invalid schema: {se.message}")
            schema_valid = False

        if schema_valid:
            print("✅ Schema validation passed.")
        else:
            print("❌ Schema validation failed.")
            for err in issues:
                print("•", err)

        report.add_entry(url, method, response.status_code, elapsed_time, schema_valid, issues)

    except requests.exceptions.RequestException as re:
        print("❌ Request failed:")
        print(str(re))
        report.add_entry(url, method, 0, 0, False, [str(re)])


if __name__ == "__main__":
    url = input("🌐 Enter the API endpoint URL: ").strip()
    method = input("🔁 Enter HTTP method (GET/POST/PUT/DELETE): ").strip().upper()

    payload = None
    if method in ["POST", "PUT"]:
        body = input("📦 Enter JSON payload (or leave blank): ").strip()
        if body:
            try:
                payload = json.loads(body)
            except json.JSONDecodeError as e:
                print("❌ Invalid JSON payload:")
                print(str(e))
                exit(1)

    custom_headers = {}
    if input("🧾 Add custom headers? (y/n): ").lower() == "y":
        while True:
            k = input("Header key (leave blank to finish): ").strip()
            if not k:
                break
            v = input("Header value: ").strip()
            custom_headers[k] = v

    print("\n📄 Paste your expected JSON schema below. Press Enter twice to finish:")
    schema_lines = []
    while True:
        line = input()
        if line.strip() == "":
            break
        schema_lines.append(line)

    try:
        user_schema = json.loads("\n".join(schema_lines))
    except json.JSONDecodeError as e:
        print("❌ Invalid schema:")
        print(str(e))
        exit(1)

    report = Report()
    validate_response(url, method, user_schema, report, payload, custom_headers)
    report.save()
