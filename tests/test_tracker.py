import pytest

import tracker


def test_save_and_list():
    result = tracker.save_job("AI Engineer", "Acme", "Remote", "https://acme.com/1", "Build RAG systems")
    assert result["saved"] is True
    jobs = tracker.list_jobs()
    assert len(jobs) == 1 and jobs[0]["title"] == "AI Engineer" and jobs[0]["status"] == "saved"


def test_get_job_returns_full_description():
    job_id = tracker.save_job("Data Analyst", "Acme", description="Full text here")["id"]
    assert tracker.get_job(job_id)["description"] == "Full text here"


def test_duplicate_url_not_saved_twice():
    tracker.save_job("AI Engineer", "Acme", url="https://acme.com/1")
    again = tracker.save_job("Different title", "Other", url="https://acme.com/1")
    assert again["saved"] is False
    assert len(tracker.list_jobs()) == 1


def test_duplicate_company_and_title_ignores_case():
    tracker.save_job("AI Engineer", "Acme")
    again = tracker.save_job("ai engineer", "ACME")
    assert again["saved"] is False


def test_title_and_company_required():
    with pytest.raises(ValueError):
        tracker.save_job("", "Acme")
    with pytest.raises(ValueError):
        tracker.save_job("AI Engineer", "   ")


def test_description_is_truncated():
    big = "x" * (tracker.MAX_DESCRIPTION + 5000)
    job_id = tracker.save_job("Role", "Co", description=big)["id"]
    assert len(tracker.get_job(job_id)["description"]) == tracker.MAX_DESCRIPTION


def test_status_update_sets_applied_date_once():
    job_id = tracker.save_job("Role", "Co")["id"]
    assert tracker.get_job(job_id)["applied_at"] is None
    tracker.update_status(job_id, "applied")
    first = tracker.get_job(job_id)["applied_at"]
    assert first
    tracker.update_status(job_id, "interview", "phone screen booked")
    job = tracker.get_job(job_id)
    assert job["status"] == "interview" and job["applied_at"] == first
    assert job["notes"] == "phone screen booked"


def test_invalid_status_rejected():
    job_id = tracker.save_job("Role", "Co")["id"]
    with pytest.raises(ValueError):
        tracker.update_status(job_id, "hired-lol")
    with pytest.raises(ValueError):
        tracker.list_jobs("hired-lol")


def test_missing_job_reported():
    with pytest.raises(ValueError):
        tracker.get_job(999)
    with pytest.raises(ValueError):
        tracker.update_status(999, "applied")


def test_list_filters_by_status():
    a = tracker.save_job("One", "Co")["id"]
    tracker.save_job("Two", "Co")
    tracker.update_status(a, "applied")
    assert [j["title"] for j in tracker.list_jobs("applied")] == ["One"]
    assert len(tracker.list_jobs("saved")) == 1


def test_sql_injection_text_is_stored_as_plain_text():
    evil = "'); DROP TABLE jobs; --"
    tracker.save_job(evil, "Co", description=evil)
    assert len(tracker.list_jobs()) == 1
    assert tracker.list_jobs()[0]["title"] == evil


def test_skipped_status_is_allowed():
    job_id = tracker.save_job("Gen AI Architect", "Unknown agency")["id"]
    tracker.update_status(job_id, "skipped", "needs 12+ years")
    assert tracker.get_job(job_id)["status"] == "skipped"
    assert [j["title"] for j in tracker.list_jobs("skipped")] == ["Gen AI Architect"]
