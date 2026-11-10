import pytest

import job_tools
import risk_tools

SCAM = ("Urgent hiring! Work from home, no experience required. Earn $300 per day guaranteed. "
        "Pay a refundable registration fee of $50 to secure your laptop. Interviews are on Telegram. "
        "Send a copy of your passport and bank details to hr.globaltech@gmail.com")


def severities(result):
    return [s["severity"] for s in result["signals"]]


def messages(result):
    return " ".join(s["signal"] for s in result["signals"])


@pytest.fixture
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the board check should not run here")
    monkeypatch.setattr(job_tools, "verify_on_company_board", boom)


def test_scam_text_is_high_concern(no_network):
    result = risk_tools.check("GlobalTech Solutions", "http://bit.ly/apply-now", SCAM, "", "Data Entry", verify_board=False)
    assert result["level"] == "high concern"
    assert severities(result).count("high") >= 2
    assert severities(result)[0] == "high"  # worst signals come first


def test_clean_posting_with_company_domains(monkeypatch):
    monkeypatch.setattr(job_tools, "verify_on_company_board", lambda c, t, u="": {
        "status": "found", "board": "greenhouse:acme", "matched_title": "AI Engineer", "matched_by": "exact title"})
    result = risk_tools.check("Acme Corp", "https://acme.com/careers/1", "Build RAG systems.", "jobs@acme.com", "AI Engineer")
    assert result["level"] == "no major red flags found"
    assert "positive" in severities(result)


def test_free_email_alone_is_some_concern(no_network):
    result = risk_tools.check("Acme Corp", "https://acme.com/jobs/1", "", "recruiter@gmail.com", verify_board=False)
    assert result["level"] == "some concern"


def test_lookalike_link_and_email_is_caution(no_network):
    result = risk_tools.check("Stripe", "https://stripe-careers-apply.com/x", "Apply now.",
                              "recruiter@stripe-hiring.net", verify_board=False)
    assert result["level"] == "caution"
    assert messages(result).count("lookalike") == 2


def test_url_shortener_and_raw_ip_flagged(no_network):
    assert "shortener" in messages(risk_tools.check("Acme Corp", "https://bit.ly/abc", verify_board=False))
    ip = risk_tools.check("Acme Corp", "http://192.168.4.20/apply", verify_board=False)
    assert "high" in severities(ip)


def test_job_portal_link_is_informational(no_network):
    result = risk_tools.check("Acme Corp", "https://www.linkedin.com/jobs/view/123", verify_board=False)
    assert "info" in severities(result) and "high" not in severities(result)


def test_company_missing_from_its_own_board_is_flagged(monkeypatch):
    monkeypatch.setattr(job_tools, "verify_on_company_board", lambda c, t, u="": {
        "status": "board_only", "board": "greenhouse:acme", "similar_titles": []})
    result = risk_tools.check("Acme Corp", "", "", "", "Data Entry")
    assert "medium" in severities(result)


def test_unknown_company_board_is_neutral(monkeypatch):
    monkeypatch.setattr(job_tools, "verify_on_company_board", lambda c, t, u="": {"status": "no_board"})
    result = risk_tools.check("Tiny Local Firm", "", "", "", "Analyst")
    assert result["level"] == "no major red flags found"
    assert "info" in severities(result)


def test_short_company_names_skip_domain_matching(no_network):
    result = risk_tools.check("EY", "https://ey.com/careers/1", verify_board=False)
    assert "lookalike" not in messages(result)


def test_result_always_states_limits(no_network):
    result = risk_tools.check("Acme Corp", verify_board=False)
    assert "not a verdict" in result["note"]


def test_unnamed_employer_is_flagged(no_network):
    result = risk_tools.check("", "", "Immediate opening for an architect.", verify_board=False)
    assert "No employer is named" in messages(result)
    assert result["level"] == "no major red flags found"  # a low signal alone does not raise the level
