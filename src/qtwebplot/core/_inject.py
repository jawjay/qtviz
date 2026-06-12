r"""HTML injection helpers — splice scripts into a backend-produced document.

We splice by string position rather than `re.sub` because the injected JS may
contain backslash sequences (`\d`, `\b`, `\n`) that `re.sub` would interpret as
replacement-string escapes.
"""

from __future__ import annotations

import re


_HEAD_CLOSE = re.compile(r"</head\s*>", re.IGNORECASE)
_BODY_OPEN = re.compile(r"<body\b[^>]*>", re.IGNORECASE)
_BODY_CLOSE = re.compile(r"</body\s*>", re.IGNORECASE)
_HTML_CLOSE = re.compile(r"</html\s*>", re.IGNORECASE)


def inject_head_scripts(html: str, scripts: list[str]) -> str:
    """Insert each `<script>` immediately before `</head>` (or fall back).

    `scripts` are raw `<script>...</script>` strings.
    """
    blob = "\n".join(scripts)
    m = _HEAD_CLOSE.search(html)
    if m:
        i = m.start()
        return html[:i] + blob + html[i:]
    m = _BODY_OPEN.search(html)
    if m:
        i = m.start()
        return html[:i] + blob + html[i:]
    return blob + html


def inject_body_end_script(html: str, script: str) -> str:
    """Insert `script` immediately before `</body>` (or fall back to `</html>`,
    or append).
    """
    m = _BODY_CLOSE.search(html)
    if m:
        i = m.start()
        return html[:i] + script + html[i:]
    m = _HTML_CLOSE.search(html)
    if m:
        i = m.start()
        return html[:i] + script + html[i:]
    return html + script


def wrap_as_script(js_source: str) -> str:
    return f"<script>\n{js_source}\n</script>"
