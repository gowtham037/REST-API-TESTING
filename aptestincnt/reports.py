import requests
import json
import datetime
import time
from genson import SchemaBuilder
from jsonschema import validate, ValidationError, SchemaError
import os
from http import HTTPStatus

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
                if entry['schema_valid'] is False:
                    final_pass = False
                else:
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
    if not url.startswith("http://") and not url.startswith("https://"):
        raise ValueError("Only HTTP/HTTPS endpoints are supported.")

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        start_time = time.time()
        method = method.upper()
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
    except requests.exceptions.RequestException as e:
        return None, 0

def validate_response(url, method, report, payload=None):
    issues = []
    try:
        response, response_time = get_response(url, method, payload)
    except ValueError as ve:
        report.add_entry(url, method, 0, False, [str(ve)], 0)
        return
    except Exception as e:
        report.add_entry(url, method, 0, False, [f"Request exception: {e}"], 0)
        return

    if response is None:
        report.add_entry(url, method, 0, False, ["No response received"], 0)
        return

    status_code = response.status_code
    content_type = response.headers.get("Content-Type", "")

    # Validate status code
    if not (200 <= status_code < 300):
        reason = HTTPStatus(status_code).phrase if status_code in HTTPStatus._value2member_map_ else "Unknown"
        issues.append(f"Unexpected status code: {status_code} {reason}")

    # Validate content type
    if "application/json" not in content_type.lower():
        issues.append(f"Invalid content type: {content_type}")

    # Response time check
    if response_time > 2:
        issues.append(f"Response time too long: {response_time:.3f} seconds (threshold: 2s)")

    schema_valid = None
    if "application/json" in content_type.lower():
        try:
            data = response.json()
            if not data:
                issues.append("Empty JSON response; schema validation skipped")
            else:
                builder = SchemaBuilder()
                builder.add_object(data)
                schema = builder.to_schema()
                try:
                    validate(instance=data, schema=schema)
                    schema_valid = True
                except (ValidationError, SchemaError) as ve:
                    schema_valid = False
                    issues.append(f"Schema validation error: {ve}")
        except json.JSONDecodeError as e:
            schema_valid = False
            issues.append(f"JSON parse error: {e}")

    report.add_entry(url, method, status_code, schema_valid, issues, response_time)

if __name__ == "__main__":
    print("\U0001f512 Multi-Method REST API Validation Tool")

    try:
        num = int(input("\U0001f522 How many endpoints to validate? "))
        endpoints = []

        for i in range(num):
            url = input(f"\U0001f517 Enter URL #{i + 1}: ").strip()
            if not url.startswith("http://") and not url.startswith("https://"):
                print("❌ Invalid URL. Must start with http:// or https://. Skipping.")
                continue

            method = input("🔁 Method (GET/POST/PUT/DELETE): ").strip().upper()
            if method not in ["GET", "POST", "PUT", "DELETE"]:
                print(f"❌ Invalid HTTP method '{method}'. Skipping.")
                continue

            payload = None
            if method in ["POST", "PUT"]:
                body = input("📦 Enter JSON payload: ").strip()
                if body:
                    try:
                        payload = json.loads(body)
                    except json.JSONDecodeError as e:
                        print(f"❌ Invalid JSON: {e}")
                        continue

            endpoints.append((url, method, payload))

        report = ReportGenerator()
        for url, method, payload in endpoints:
            validate_response(url, method, report, payload)

        report.generate_html("reports.html")

    except Exception as e:
        print(f"❌ Error: {e}")
