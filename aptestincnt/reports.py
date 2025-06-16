import requests
import json
import datetime
import pytz
from genson import SchemaBuilder
from jsonschema import validate, ValidationError, SchemaError
from http import HTTPStatus

class ReportGenerator:
    def __init__(self):
        self.entries = []

    def add_entry(self, url, method, status_code, schema_valid, issues, response_time, schema=None, response=None):
        self.entries.append({
            "url": url,
            "method": method,
            "status_code": status_code,
            "schema_valid": schema_valid,
            "issues": issues,
            "response_time": response_time,
            "schema": schema,
            "response": response
        })

    def generate_html(self, filename="report.html"):
        file_path = filename
        local_time = datetime.datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")

        all_passed = all(
            200 <= e["status_code"] < 300 and
            e["schema_valid"] and
            not e["issues"] and
            e["response_time"] <= 2
            for e in self.entries
        )
        final_result = "✅ Validated" if all_passed else "❌ Failed"
        result_class = "pass" if all_passed else "fail"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>API Test Report</title>
<style>
body {{ font-family: Arial; margin: 20px; }}
.card {{ border: 1px solid #ccc; border-radius: 8px; margin-bottom: 20px; padding: 15px; }}
.pass {{ color: green; font-weight: bold; }}
.fail {{ color: red; font-weight: bold; }}
button {{ margin-top: 5px; margin-bottom: 10px; }}
.code-block {{ display: none; background-color: #f9f9f9; border: 1px dashed #999; padding: 10px; white-space: pre-wrap; margin-top: 5px; }}
</style>
<script>
function toggle(id, btn, label) {{
    const el = document.getElementById(id);
    if (el.style.display === "block") {{
        el.style.display = "none";
        btn.innerText = "Expand " + label;
    }} else {{
        el.style.display = "block";
        btn.innerText = "Close " + label;
    }}
}}
</script>
</head><body>
<h2>API Validation Report</h2>
<p>Generated at: {local_time}</p>
<h3 class="{result_class}">Final Result: {final_result}</h3>
""")
            for i, e in enumerate(self.entries):
                schema_html = '<span class="pass">Passed</span>' if e["schema_valid"] else '<span class="fail">Failed</span>'
                status_html = (
                    f"<span class='pass'>{e['status_code']}</span>"
                    if 200 <= e["status_code"] < 300
                    else f"<span class='fail'>{e['status_code']}</span>"
                )
                issues_str = "<br>".join(e["issues"]) or "None"
                schema_str = json.dumps(e.get("schema", {}), indent=2, ensure_ascii=False)
                response_str = json.dumps(e.get("response", {}), indent=2, ensure_ascii=False)

                f.write(f"""
<div class="card">
    <h3>{e['method']} ➜ {e['url']}</h3>
    <p><strong>Status:</strong> {status_html} | <strong>Schema:</strong> {schema_html} | <strong>Time:</strong> {e['response_time']:.2f}s</p>
    <p><strong>Issues:</strong><br>{issues_str}</p>
    <button onclick="toggle('schema_{i}', this, 'Schema')">Expand Schema</button>
    <div id="schema_{i}" class="code-block">{schema_str}</div>
    <button onclick="toggle('resp_{i}', this, 'Response')">Expand Response</button>
    <div id="resp_{i}" class="code-block">{response_str}</div>
</div>
""")
            f.write("</body></html>")
        print(f"\n📄 Report saved at: {file_path}")
        print(f"✅ Final Validation Status: {final_result}")

def smart_predict_method(url):
    methods = ["POST", "PUT", "PATCH", "GET", "DELETE", "OPTIONS", "HEAD"]
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    dummy_payload = {"test": "value"}

    for method in methods:
        try:
            if method in ["POST", "PUT", "PATCH"]:
                res = requests.request(method, url, headers=headers, json=dummy_payload, timeout=10)
            else:
                res = requests.request(method, url, headers=headers, timeout=10)

            if res.status_code not in [404, 405]:
                return method, res, res.elapsed.total_seconds()
        except requests.exceptions.RequestException:
            continue

    return None, None, 0

def auto_validate(url, report):
    method, response, response_time = smart_predict_method(url)
    issues = []

    if method is None or response is None:
        report.add_entry(url, "UNKNOWN", 0, False, ["No valid response received"], 0)
        return

    user_payload = None
    if method in ["POST", "PUT", "PATCH"]:
        try:
            user_input = input(f"📝 Enter JSON payload for {method} request (or press Enter to use dummy): ").strip()
            if user_input:
                user_payload = json.loads(user_input)
            else:
                user_payload = {"test": "value"}
        except json.JSONDecodeError:
            print("❌ Invalid JSON. Using dummy payload.")
            user_payload = {"test": "value"}

        try:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            response = requests.request(method, url, headers=headers, json=user_payload, timeout=10)
            response_time = response.elapsed.total_seconds()
        except requests.exceptions.RequestException as e:
            report.add_entry(url, method, 0, False, [str(e)], 0)
            return

    status = response.status_code
    schema_valid = False
    schema = {}
    json_data = {}

    if not (200 <= status < 300):
        issues.append(f"Unexpected status code: {status} {HTTPStatus(status).phrase if status in HTTPStatus._value2member_map_ else ''}")

    content_type = response.headers.get("Content-Type", "").lower()
    if "application/json" not in content_type:
        issues.append(f"Invalid content-type: {content_type}")

    try:
        data = response.json()
        json_data = data
        builder = SchemaBuilder()
        builder.add_object(data)
        schema = builder.to_schema()

        try:
            validate(instance=data, schema=schema)
            schema_valid = True
        except (ValidationError, SchemaError) as ve:
            issues.append(f"Schema validation failed: {ve.message}")
    except json.JSONDecodeError:
        issues.append("Response is not valid JSON")

    if response_time > 2:
        issues.append(f"Response time too long: {response_time:.3f}s")

    report.add_entry(url, method, status, schema_valid, issues, response_time, schema, json_data)

if __name__ == "__main__":
    print("🔍 Smart API Validator with Method + Payload Prompt")
    try:
        url = input("Enter API URL: ").strip()
        if not url.startswith("http"):
            print("❌ Invalid URL. Must begin with http:// or https://")
            exit(1)
        report = ReportGenerator()
        auto_validate(url, report)
        report.generate_html()
    except KeyboardInterrupt:
        print("\n❗ Aborted by user.") 
