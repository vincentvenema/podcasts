#!/usr/bin/env python3
"""
sync_inline.py

Rewrites the `const INLINE_DATA = {...};` fallback block in index.html so it
matches podcasts.json exactly. The live site fetches /podcasts.json, so this
block only matters when that fetch fails, but keeping it in sync means the
fallback never serves stale data. Run this at deploy time, before upload.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = ROOT / "index.html"
JSON_PATH = ROOT / "podcasts.json"
MARKER = "const INLINE_DATA = "


def main() -> int:
    html = HTML_PATH.read_text(encoding="utf-8")
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))

    start = html.find(MARKER)
    if start == -1:
        print("INLINE_DATA marker not found; nothing to sync.")
        return 1

    brace_start = html.index("{", start)
    # Walk braces to find the matching close, ignoring braces inside strings.
    depth, i, in_str, esc = 0, brace_start, False, False
    while i < len(html):
        c = html[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
        i += 1
    brace_end = i  # index of the closing brace

    new_obj = json.dumps(data, ensure_ascii=False, indent=2)
    new_html = html[:brace_start] + new_obj + html[brace_end + 1:]
    HTML_PATH.write_text(new_html, encoding="utf-8")
    print(f"INLINE_DATA synced: {len(data['weeks'])} weeks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
