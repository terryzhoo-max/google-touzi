from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dompurify_is_loaded_before_app_script():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

    dompurify_index = html.index("purify.min.js")
    main_index = html.index('src="main.js')

    assert dompurify_index < main_index


def test_ai_markdown_is_sanitized_before_inner_html():
    js = (ROOT / "static" / "main.js").read_text(encoding="utf-8")

    assert "DOMPurify.sanitize" in js
    assert "ADD_ATTR: ['style']" not in js
    assert "tw.innerHTML = parsedHTML" not in js
