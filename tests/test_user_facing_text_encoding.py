from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

USER_FACING_FILES = [
    ROOT / "static" / "main.js",
    ROOT / "static" / "index.html",
    ROOT / "core" / "strategy_lab.py",
    ROOT / "core" / "market_data.py",
    ROOT / "core" / "yield_curve.py",
    ROOT / "core" / "fed_prob.py",
]

MOJIBAKE_FRAGMENTS = [
    "鍓",
    "鎺",
    "骞",
    "瀵",
    "閸",
    "鈧",
    "绀",
    "繅",
    "閹",
    "楠",
    "濞",
    "娅",
    "鐢",
    "璁",
    "閾",
    "杩",
    "馃",
    "鈥",
]


def test_user_facing_text_contains_no_mojibake_fragments():
    offenders = []
    for path in USER_FACING_FILES:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), 1):
            for fragment in MOJIBAKE_FRAGMENTS:
                if fragment in line:
                    offenders.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()[:120]}")
                    break

    assert offenders == []
