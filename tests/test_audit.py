import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from auto_remediate import parse_repo_url
from compliance_report import DORA_MAPPING, NIS2_MAPPING, keyword_score
from engine.generate_report import extract_and_load_json
from payment import PRODUCTS


class TestJsonLoading:
    def test_empty(self, tmp_path):
        f = tmp_path / "empty.json"
        f.write_text("")
        assert extract_and_load_json(str(f)) == {}

    def test_valid_json(self, tmp_path):
        data = {"secrets": [{"file": "test.py", "line": 1}]}
        f = tmp_path / "valid.json"
        f.write_text(json.dumps(data))
        assert extract_and_load_json(str(f)) == data

    def test_json_with_markdown_code_block(self, tmp_path):
        data = {"key": "value"}
        content = f"```json\n{json.dumps(data)}\n```"
        f = tmp_path / "codeblock.json"
        f.write_text(content)
        assert extract_and_load_json(str(f)) == data


class TestComplianceScoring:
    def test_100_percent_match(self):
        assert keyword_score("network firewall tls ssl", ["network", "firewall", "tls"]) == 100

    def test_zero_percent_match(self):
        assert keyword_score("hello world python", ["network", "firewall"]) == 0

    def test_partial_match(self):
        assert keyword_score("network python firewall", ["network", "firewall", "tls"]) == 66


class TestNis2Mapping:
    def test_has_expected_keys(self):
        expected = {"network_security", "risk_management", "business_continuity", "supply_chain", "incident_response", "crypto_policies", "access_control"}
        assert set(NIS2_MAPPING.keys()) == expected


class TestDoraMapping:
    def test_has_expected_keys(self):
        expected = {"ict_risk_management", "ict_incident_reporting", "digital_resilience", "third_party_risk", "information_sharing"}
        assert set(DORA_MAPPING.keys()) == expected


class TestParseRepoUrl:
    def test_https_url(self):
        assert parse_repo_url("https://github.com/owner/repo") == ("owner", "repo")

    def test_https_url_with_git_suffix(self):
        assert parse_repo_url("https://github.com/owner/repo.git") == ("owner", "repo")

    def test_with_trailing_slash(self):
        assert parse_repo_url("https://github.com/owner/repo/") == ("owner", "repo")


class TestProductPricing:
    def test_auditoria_unica_price(self):
        assert PRODUCTS["auditoria_unica"]["price_cents"] == 29900

    def test_suscripcion_mensual_price(self):
        assert PRODUCTS["suscripcion_mensual"]["price_cents"] == 19900

    def test_auditoria_unica_repo_limit(self):
        assert PRODUCTS["auditoria_unica"]["repo_limit"] == 1

    def test_suscripcion_mensual_repo_limit(self):
        assert PRODUCTS["suscripcion_mensual"]["repo_limit"] == 4
