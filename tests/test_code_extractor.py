"""Tests for bouncer_logic.code_extractor."""

from bouncer_logic import code_extractor


class TestExtractPythonSnippets:
    def test_finds_function_with_sql(self):
        code = '''
def get_user(uid):
    query = "SELECT * FROM users WHERE id=" + uid
    return db.execute(query)

def hello():
    print("hi")
'''
        snippets = code_extractor.extract_security_snippets(code, "app.py")
        names = [s["name"] for s in snippets]
        assert any("get_user" in n for n in names)
        # hello() has no security patterns, should not be included
        assert not any("hello" in n for n in names)

    def test_finds_function_with_eval(self):
        code = '''
def process(data):
    return eval(data)
'''
        snippets = code_extractor.extract_security_snippets(code, "util.py")
        assert len(snippets) >= 1
        assert any("code execution" in r for s in snippets for r in s["match_reasons"])

    def test_finds_class_with_auth(self):
        code = '''
class AuthHandler:
    def login(self, password):
        if password == self.secret_token:
            return True
'''
        snippets = code_extractor.extract_security_snippets(code, "auth.py")
        assert len(snippets) >= 1

    def test_skips_innocent_code(self):
        code = '''
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
'''
        snippets = code_extractor.extract_security_snippets(code, "math.py")
        assert len(snippets) == 0


class TestExtractJsTsSnippets:
    def test_finds_function_with_innerhtml(self):
        code = '''
function renderUser(data) {
    document.getElementById("user").innerHTML = data.name;
}

function add(a, b) {
    return a + b;
}
'''
        snippets = code_extractor.extract_security_snippets(code, "app.js")
        assert len(snippets) >= 1
        names = [s["name"] for s in snippets]
        assert any("renderUser" in n for n in names)

    def test_finds_api_handler(self):
        code = '''
export async function POST(request) {
    const body = await request.json();
    const result = await db.query("SELECT * FROM users WHERE id=" + body.id);
    return response.json(result);
}
'''
        snippets = code_extractor.extract_security_snippets(code, "route.ts")
        assert len(snippets) >= 1


class TestExtractLineWindows:
    def test_fallback_finds_patterns_in_unstructured_code(self):
        code = "line1\nline2\npassword = 'hardcoded123'\nline4\nline5"
        snippets = code_extractor.extract_security_snippets(code, "config.txt")
        assert len(snippets) >= 1
        assert any("sensitive data" in r for s in snippets for r in s["match_reasons"])


class TestBuildFocusedContent:
    def test_formats_snippets(self):
        snippets = [
            {
                "name": "FunctionDef: get_user",
                "start_line": 10,
                "end_line": 15,
                "code": "def get_user(uid):\n    return db.query(uid)",
                "match_reasons": ["SQL query", "database call"],
            }
        ]
        result = code_extractor.build_focused_content(snippets, "app.py")
        assert "get_user" in result
        assert "SQL query" in result
        assert "lines 10-15" in result

    def test_empty_snippets_returns_empty(self):
        result = code_extractor.build_focused_content([], "app.py")
        assert result == ""

    def test_multiple_snippets_joined(self):
        snippets = [
            {"name": "func_a", "start_line": 1, "end_line": 5, "code": "a", "match_reasons": ["SQL query"]},
            {"name": "func_b", "start_line": 10, "end_line": 15, "code": "b", "match_reasons": ["auth/security"]},
        ]
        result = code_extractor.build_focused_content(snippets, "app.py")
        assert "func_a" in result
        assert "func_b" in result
