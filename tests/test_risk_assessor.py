"""Tests for bouncer_logic.risk_assessor."""

from bouncer_logic import risk_assessor
from bouncer_logic.risk_assessor import RISK_HIGH, RISK_MEDIUM, RISK_LOW, RISK_SKIP


class TestAssessFileRisk:
    # -- Skip rules --
    def test_skips_package_lock(self):
        assert risk_assessor.assess_file_risk("package-lock.json") == RISK_SKIP

    def test_skips_markdown(self):
        assert risk_assessor.assess_file_risk("docs/README.md") == RISK_SKIP

    def test_skips_node_modules(self):
        assert risk_assessor.assess_file_risk("node_modules/lodash/index.js") == RISK_SKIP

    def test_skips_minified_js(self):
        assert risk_assessor.assess_file_risk("dist/bundle.min.js") == RISK_SKIP

    def test_skips_type_definitions(self):
        assert risk_assessor.assess_file_risk("types/global.d.ts") == RISK_SKIP

    def test_skips_images(self):
        assert risk_assessor.assess_file_risk("assets/logo.png") == RISK_SKIP

    # -- High risk by name --
    def test_env_file_high_risk(self):
        assert risk_assessor.assess_file_risk(".env") == RISK_HIGH

    def test_dockerfile_high_risk(self):
        assert risk_assessor.assess_file_risk("Dockerfile") == RISK_HIGH

    # -- High risk by path pattern --
    def test_auth_module_high_risk(self):
        assert risk_assessor.assess_file_risk("src/auth/login.py") == RISK_HIGH

    def test_api_routes_high_risk(self):
        assert risk_assessor.assess_file_risk("src/api/users.ts") == RISK_HIGH

    def test_controllers_high_risk(self):
        assert risk_assessor.assess_file_risk("app/controllers/payment.js") == RISK_HIGH

    def test_db_module_high_risk(self):
        assert risk_assessor.assess_file_risk("src/db/queries.py") == RISK_HIGH

    def test_config_high_risk(self):
        assert risk_assessor.assess_file_risk("config/settings.py") == RISK_HIGH

    # -- Content-based scoring --
    def test_content_with_many_keywords_is_high(self):
        content = 'password = "abc"\ntoken = "xyz"\nsecret = "123"'
        score = risk_assessor.assess_file_risk("utils/helper.py", content)
        assert score == RISK_HIGH

    def test_content_with_one_keyword_is_medium(self):
        content = 'api_key = os.getenv("KEY")'
        score = risk_assessor.assess_file_risk("utils/helper.py", content)
        assert score == RISK_MEDIUM

    def test_content_with_sql_keywords(self):
        content = 'query = "SELECT * FROM users WHERE id=" + uid'
        score = risk_assessor.assess_file_risk("utils/data.py", content)
        assert score >= RISK_MEDIUM

    def test_content_with_eval(self):
        content = "result = eval(user_input)"
        score = risk_assessor.assess_file_risk("utils/calc.py", content)
        assert score >= RISK_MEDIUM

    # -- Low risk (scannable but no special signals) --
    def test_plain_python_file_is_low(self):
        assert risk_assessor.assess_file_risk("src/utils/math.py") == RISK_LOW

    def test_plain_js_file_is_low(self):
        assert risk_assessor.assess_file_risk("src/components/button.js") == RISK_LOW


class TestPrioritizeFiles:
    def test_filters_out_skippable_files(self):
        files = [
            {"path": "src/auth.py", "full_stage_path": "@repo/src/auth.py"},
            {"path": "README.md", "full_stage_path": "@repo/README.md"},
            {"path": "package-lock.json", "full_stage_path": "@repo/package-lock.json"},
        ]
        result = risk_assessor.prioritize_files(files)
        paths = [f["path"] for f in result]
        assert "src/auth.py" in paths
        assert "README.md" not in paths
        assert "package-lock.json" not in paths

    def test_sorts_high_risk_first(self):
        files = [
            {"path": "src/utils/math.py", "full_stage_path": "@repo/math.py"},
            {"path": "src/auth/login.py", "full_stage_path": "@repo/login.py"},
            {"path": "src/helpers.py", "full_stage_path": "@repo/helpers.py"},
        ]
        result = risk_assessor.prioritize_files(files)
        assert result[0]["path"] == "src/auth/login.py"

    def test_uses_content_for_scoring(self):
        files = [
            {"path": "a.py", "full_stage_path": "@repo/a.py"},
            {"path": "b.py", "full_stage_path": "@repo/b.py"},
        ]
        contents = {
            "a.py": "x = 1",
            "b.py": 'password = "hunter2"\ntoken = "abc"\nsecret = "xyz"',
        }
        result = risk_assessor.prioritize_files(files, contents)
        assert result[0]["path"] == "b.py"

    def test_adds_risk_score_key(self):
        files = [{"path": "src/app.py", "full_stage_path": "@repo/app.py"}]
        result = risk_assessor.prioritize_files(files)
        assert "risk_score" in result[0]

    def test_empty_input(self):
        assert risk_assessor.prioritize_files([]) == []
