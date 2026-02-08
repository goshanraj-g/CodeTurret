"""Extract security-relevant code snippets instead of sending full files."""

import ast
import os
import re
from typing import Dict, List

from bouncer_logic import config

# Patterns that signal security-relevant code
SECURITY_PATTERNS = [
    (re.compile(r"(?:import|from)\s+(?:subprocess|os|pickle|yaml|sqlite3|hashlib|hmac|jwt|bcrypt)"), "dangerous import"),
    (re.compile(r"(?:SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER)\s", re.IGNORECASE), "SQL query"),
    (re.compile(r"(?:password|passwd|token|secret|api_key|apikey|credential|private_key)", re.IGNORECASE), "sensitive data"),
    (re.compile(r"(?:eval|exec)\s*\("), "code execution"),
    (re.compile(r"(?:os\.system|subprocess\.|child_process|spawn|execFile)"), "command execution"),
    (re.compile(r"(?:innerHTML|dangerouslySetInnerHTML|\.html\()"), "DOM manipulation"),
    (re.compile(r"(?:req\.|request\.|res\.|response\.)"), "HTTP handling"),
    (re.compile(r"(?:open\(|readFile|writeFile|unlink|rmdir|fs\.)"), "file I/O"),
    (re.compile(r"(?:pickle\.loads|yaml\.load|deserialize|unserialize)"), "deserialization"),
    (re.compile(r"(?:verify\s*=\s*False|ssl\s*=\s*False|rejectUnauthorized\s*:\s*false)", re.IGNORECASE), "TLS/SSL bypass"),
    (re.compile(r"(?:\.query\(|\.execute\(|\.raw\(|\.exec\()"), "database call"),
    (re.compile(r"(?:cors|cookie|session|csrf|helmet|auth|login|logout|signup|register)", re.IGNORECASE), "auth/security"),
]


def extract_security_snippets(content: str, file_path: str) -> List[Dict]:
    """Extract security-relevant code blocks from a file.

    Returns list of dicts with name, start_line, end_line, code, match_reasons.
    """
    _, ext = os.path.splitext(file_path)

    if ext == ".py":
        snippets = _extract_python_snippets(content)
    elif ext in (".js", ".ts", ".jsx", ".tsx"):
        snippets = _extract_js_ts_snippets(content)
    else:
        snippets = []

    # Fallback to line-window extraction if AST/regex found nothing
    if not snippets:
        snippets = _extract_line_windows(content)

    return snippets


def build_focused_content(snippets: List[Dict], file_path: str) -> str:
    """Format extracted snippets into a condensed string for the LLM prompt.

    Falls back to full file content (truncated) if no snippets found.
    """
    if not snippets:
        return ""

    parts: List[str] = []
    for s in snippets:
        header = f"=== {s['name']} (lines {s['start_line']}-{s['end_line']}) ==="
        reasons = ", ".join(s["match_reasons"])
        parts.append(f"{header}\n[Flagged: {reasons}]\n\n{s['code']}")

    return "\n\n".join(parts)


def _extract_python_snippets(content: str) -> List[Dict]:
    """AST-based extraction for .py files."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return _extract_line_windows(content)

    lines = content.splitlines()
    snippets: List[Dict] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        start = node.lineno
        end = node.end_lineno or start
        # Extract source lines (1-indexed to 0-indexed)
        code = "\n".join(lines[start - 1:end])

        reasons = _match_security_patterns(code)
        if reasons:
            snippets.append({
                "name": f"{type(node).__name__}: {node.name}",
                "start_line": start,
                "end_line": end,
                "code": code,
                "match_reasons": reasons,
            })

    return snippets


def _extract_js_ts_snippets(content: str) -> List[Dict]:
    """Regex-based extraction for JS/TS files."""
    # Match function/class/method boundaries
    pattern = re.compile(
        r"(?:^|\n)"
        r"(?:export\s+)?(?:default\s+)?"
        r"(?:"
        r"(?:async\s+)?function\s+(\w+)|"           # function name(
        r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(?|"  # const name = ( or =>
        r"class\s+(\w+)|"                             # class Name
        r"(\w+)\s*\([^)]*\)\s*\{"                     # method(args) {
        r")",
        re.MULTILINE,
    )

    lines = content.splitlines()
    snippets: List[Dict] = []
    total_lines = len(lines)

    for match in pattern.finditer(content):
        name = match.group(1) or match.group(2) or match.group(3) or match.group(4)
        if not name:
            continue

        # Find the line number
        start_pos = match.start()
        start_line = content[:start_pos].count("\n") + 1

        # Estimate end by finding matching brace depth or take ~50 lines
        end_line = min(start_line + 50, total_lines)

        # Try to find the end of the block via brace counting
        depth = 0
        found_open = False
        for i in range(start_line - 1, min(start_line + 100, total_lines)):
            line = lines[i]
            for ch in line:
                if ch == "{":
                    depth += 1
                    found_open = True
                elif ch == "}":
                    depth -= 1
            if found_open and depth <= 0:
                end_line = i + 1
                break

        code = "\n".join(lines[start_line - 1:end_line])
        reasons = _match_security_patterns(code)
        if reasons:
            snippets.append({
                "name": f"function: {name}",
                "start_line": start_line,
                "end_line": end_line,
                "code": code,
                "match_reasons": reasons,
            })

    return snippets


def _extract_line_windows(content: str) -> List[Dict]:
    """Fallback: find lines matching security patterns and return context windows."""
    lines = content.splitlines()
    flagged_lines: List[tuple] = []  # (line_number, reasons)

    for i, line in enumerate(lines):
        reasons = _match_security_patterns(line)
        if reasons:
            flagged_lines.append((i, reasons))

    if not flagged_lines:
        return []

    # Merge overlapping windows (10 lines of context)
    WINDOW = 10
    windows: List[Dict] = []
    current_start = max(0, flagged_lines[0][0] - WINDOW)
    current_end = min(len(lines), flagged_lines[0][0] + WINDOW + 1)
    all_reasons: List[str] = list(flagged_lines[0][1])

    for line_num, reasons in flagged_lines[1:]:
        window_start = max(0, line_num - WINDOW)
        window_end = min(len(lines), line_num + WINDOW + 1)

        if window_start <= current_end:
            # Overlapping — extend current window
            current_end = window_end
            all_reasons.extend(r for r in reasons if r not in all_reasons)
        else:
            # Non-overlapping — save current, start new
            code = "\n".join(lines[current_start:current_end])
            windows.append({
                "name": f"lines {current_start + 1}-{current_end}",
                "start_line": current_start + 1,
                "end_line": current_end,
                "code": code,
                "match_reasons": all_reasons,
            })
            current_start = window_start
            current_end = window_end
            all_reasons = list(reasons)

    # Don't forget the last window
    code = "\n".join(lines[current_start:current_end])
    windows.append({
        "name": f"lines {current_start + 1}-{current_end}",
        "start_line": current_start + 1,
        "end_line": current_end,
        "code": code,
        "match_reasons": all_reasons,
    })

    return windows


def _match_security_patterns(text: str) -> List[str]:
    """Check text against all security patterns. Returns list of matching reasons."""
    reasons: List[str] = []
    for pattern, reason in SECURITY_PATTERNS:
        if pattern.search(text):
            if reason not in reasons:
                reasons.append(reason)
    return reasons
