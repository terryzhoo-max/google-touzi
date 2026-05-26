import os

def run():
    file_path = 'data_engine.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = """@app.get("/api/institutional/ai_compliance_review")
def api_institutional_ai_compliance_review():"""

    replacement = """@app.get("/api/institutional/ai_compliance_review")
@cached(ttl=ROUTE_TTL["institutional_compliance"], key="ai_compliance_review")
def api_institutional_ai_compliance_review():"""

    normalized_content = content.replace('\r\n', '\n')
    normalized_target = target.replace('\r\n', '\n')
    normalized_replacement = replacement.replace('\r\n', '\n')

    if normalized_target in normalized_content:
        new_content = normalized_content.replace(normalized_target, normalized_replacement)
        # Restore CRLF
        new_content = new_content.replace('\n', '\r\n')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("SUCCESS: Caching decorator added to ai_compliance_review route!")
    else:
        print("ERROR: Target route definition not found in data_engine.py!")

if __name__ == '__main__':
    run()
