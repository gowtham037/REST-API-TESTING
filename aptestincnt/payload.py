import requests, json, datetime, pytz, re
from genson import SchemaBuilder
from jsonschema import validate
from urllib.parse import urljoin
from itertools import product

context_store = {}
payload_store = {}
id_sources = {}

class ReportGenerator:
    def __init__(self): self.entries = []

    def add_entry(self, url, method, status_code, schema_valid, issues, response_time, schema=None, response=None, payload=None):
        self.entries.append({
            "url": url, "method": method, "status_code": status_code, "schema_valid": schema_valid,
            "issues": issues, "response_time": response_time, "schema": schema,
            "response": response, "payload": payload
        })

    def generate_html(self, filename="report.html"):
        file_path = filename
        local_time = datetime.datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>API Test Report</title><style>
body {{ font-family: Arial; margin: 20px; }} .card {{ border: 1px solid #ccc; border-radius: 8px; margin-bottom: 20px; padding: 15px; }}
.pass {{ color: green; font-weight: bold; }} .fail {{ color: red; font-weight: bold; }}
.code-block {{ display: none; background-color: #f9f9f9; border: 1px dashed #999; padding: 10px; white-space: pre-wrap; margin-top: 5px; }}
</style><script>function toggle(id, btn, label) {{
const el = document.getElementById(id);
el.style.display = el.style.display === "block" ? "none" : "block";
btn.innerText = el.style.display === "block" ? "Close " + label : "Expand " + label;
}}</script></head><body>
<h2>API Validation Report</h2><p>Generated at: {local_time}</p>
""")
            for i, e in enumerate(self.entries):
                schema_html = '<span class="pass">Passed</span>' if e["schema_valid"] else '<span class="fail">Skipped</span>'
                status_html = f"<span class='pass'>{e['status_code']}</span>" if 200 <= e["status_code"] < 300 else f"<span class='fail'>{e['status_code']}</span>"
                issues_str = "<br>".join(e["issues"]) or "None"
                schema_str = json.dumps(e.get("schema", {}), indent=2, ensure_ascii=False)
                response_content = e.get("response", {})
                response_str = json.dumps(response_content, indent=2, ensure_ascii=False) if isinstance(response_content, (dict, list)) else str(response_content)
                payload_str = json.dumps(e.get("payload", {}), indent=2, ensure_ascii=False)

                f.write(f"""<div class="card">\n<h3>{e['method']} ➞ {e['url']}</h3>
<p><strong>Status:</strong> {status_html} | <strong>Schema:</strong> {schema_html} | <strong>Time:</strong> {e['response_time']:.2f}s</p>
<p><strong>Issues:</strong><br>{issues_str}</p>
<button onclick="toggle('payload_{i}', this, 'Payload')">Expand Payload</button><div id="payload_{i}" class="code-block">{payload_str}</div>
<button onclick="toggle('schema_{i}', this, 'Schema')">Expand Schema</button><div id="schema_{i}" class="code-block">{schema_str}</div>
<button onclick="toggle('resp_{i}', this, 'Response')">Expand Response</button><div id="resp_{i}" class="code-block">{response_str}</div>
</div>""")
            f.write("</body></html>")
        print(f"\n📄 Report saved at: {file_path}")

def build_payload_from_error(detail):
    payload = {}
    for err in detail:
        if err.get("type") == "missing" and isinstance(err.get("loc", []), list) and err["loc"][0] == "body":
            keys = err["loc"][1:]
            current = payload
            for k in keys[:-1]:
                current = current.setdefault(k, {})
            current[keys[-1]] = "auto-filled"
    return payload

def resolve_all_combinations(path):
    placeholders = re.findall(r"\{([^}]+)\}", path)
    if not placeholders:
        return [path]
    value_lists = []
    for key in placeholders:
        values = context_store.get(key)
        if values is None:
            values = [f"dummy-{key}"]
        elif not isinstance(values, list):
            values = [values]
        value_lists.append(values)
    resolved = []
    for combo in product(*value_lists):
        temp = path
        for key, val in zip(placeholders, combo):
            temp = temp.replace(f"{{{key}}}", val)
        resolved.append(temp)
    return resolved

def extract_ids_and_payloads(data, method, path):
    if method == "GET":
        payload_store[path] = data
    extract_ids_from_response(data)

def extract_ids_from_response(data, parent=""):
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, str):
                lowered = k.lower()
                if "id" in lowered or lowered.endswith("_id"):
                    context_store.setdefault(k, []).append(v)
                    if parent and k == "id":
                        context_store.setdefault(f"{parent}_id", []).append(v)
            elif isinstance(v, (dict, list)):
                extract_ids_from_response(v, parent=k)
    elif isinstance(data, list):
        for item in data:
            extract_ids_from_response(item, parent=parent)

def auto_validate(method, url, schema, report, base_url, raw_path):
    headers = {"Accept": "*/*", "Content-Type": "application/json"}
    issues, response_data = [], None
    payload = {}

    try:
        if method in ["POST", "PUT", "PATCH"]:
            payload = {}
            response = requests.request(method, url, headers=headers, json=payload, timeout=10)

            if response.status_code == 422:
                try:
                    detail = response.json().get("detail", [])
                    payload = build_payload_from_error(detail)
                    response = requests.request(method, url, headers=headers, json=payload, timeout=10)
                except:
                    issues.append("Failed to parse 422 error details.")
        else:
            response = requests.request(method, url, headers=headers, timeout=10)

        response_time = response.elapsed.total_seconds()
        status = response.status_code
        content_type = response.headers.get("Content-Type", "").lower()
        schema_valid, final_schema = False, {}

        if "application/json" in content_type:
            try:
                response_data = response.json()
                builder = SchemaBuilder()
                builder.add_object(response_data)
                final_schema = builder.to_schema()
                validate(instance=response_data, schema=final_schema)
                schema_valid = True
                extract_ids_and_payloads(response_data, method, raw_path)
            except Exception as e:
                issues.append(f"Schema validation failed: {e}")
        else:
            issues.append("Non-JSON response; skipping schema validation.")

        if response_time > 2:
            issues.append(f"Response time too long: {response_time:.2f}s")

        report.add_entry(url, method, status, schema_valid, issues, response_time, final_schema, response_data, payload)

    except Exception as e:
        report.add_entry(url, method, 0, False, [str(e)], 0, {}, None, payload)

def parse_openapi(openapi_url):
    res = requests.get(openapi_url)
    res.raise_for_status()
    data = res.json()
    base_url = input("🌐 Enter base API URL (e.g., http://localhost:8000): ").strip().rstrip("/")
    endpoints = []
    for path, methods in data.get("paths", {}).items():
        for method, meta in methods.items():
            req_schema = meta.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
            endpoints.append((method.upper(), path, req_schema))
    return endpoints, base_url

# ------------------ MAIN ------------------

if __name__ == "__main__":
    print("🔍 Auto API Validator With Real-Time Payloads")
    try:
        openapi_url = input("🔗 Enter OpenAPI URL (e.g., http://localhost:8000/openapi.json): ").strip()
        if not openapi_url.startswith("http"):
            print("❌ Invalid OpenAPI URL")
            exit(1)

        endpoints, base_url = parse_openapi(openapi_url)
        report = ReportGenerator()

        for method, path, schema in endpoints:
            all_paths = resolve_all_combinations(path)
            for final_path in all_paths:
                full_url = urljoin(base_url + "/", final_path.lstrip("/"))
                print(f"\n🔎 Validating {method} {full_url}")
                auto_validate(method, full_url, schema, report, base_url, path)

        report.generate_html()

    except KeyboardInterrupt:
        print("\n❗ Aborted by user.")
