import httpx
import pytest

import job_tools
from cv_tools import ALLOWED_DIR

GREENHOUSE = {"jobs": [
    {"title": "  AI Engineer ", "location": {"name": "Remote, US"},
     "absolute_url": "https://boards.greenhouse.io/acme/jobs/1234567", "updated_at": "2026-10-20T10:00:00Z"},
    {"title": "\tData Analyst", "location": {"name": "Bangalore, India"},
     "absolute_url": "https://boards.greenhouse.io/acme/jobs/7654321", "updated_at": "2026-10-19T10:00:00Z"},
    {"title": "Machine Learning Engineer", "location": {"name": "Bangalore, India"},
     "absolute_url": "https://boards.greenhouse.io/acme/jobs/1112223", "updated_at": "2026-10-18T10:00:00Z"},
]}
LEVER = [{"text": "AI Researcher", "categories": {"location": "London"},
          "hostedUrl": "https://jobs.lever.co/acme/abc-123", "createdAt": 1760000000000}]


def http_error(code=404):
    req = httpx.Request("GET", "https://example.com")
    return httpx.HTTPStatusError("error", request=req, response=httpx.Response(code, request=req))


@pytest.fixture
def fake_net(monkeypatch):
    def fake_get_json(url):
        if "boards/acme/jobs" in url:
            return GREENHOUSE
        if "postings/acme" in url:
            return LEVER
        raise http_error(404)
    monkeypatch.setattr(job_tools, "_get_json", fake_get_json)


# ---------- reading the two job board formats ----------

def test_greenhouse_jobs_are_normalised(fake_net):
    jobs = job_tools.fetch_board("greenhouse", "acme")
    assert [j["title"] for j in jobs][:2] == ["AI Engineer", "Data Analyst"]  # whitespace stripped
    assert jobs[0]["location"] == "Remote, US"
    assert jobs[0]["last_updated"] == "2026-10-20" and jobs[0]["posted"] == ""


def test_lever_jobs_are_normalised(fake_net):
    job = job_tools.fetch_board("lever", "acme")[0]
    assert job["title"] == "AI Researcher" and job["location"] == "London"
    assert job["posted"] == "2025-10-09" and job["last_updated"] == ""


def test_lever_returning_garbage_does_not_crash(monkeypatch):
    monkeypatch.setattr(job_tools, "_get_json", lambda url: {"unexpected": "shape"})
    assert job_tools.fetch_board("lever", "acme") == []


# ---------- searching ----------

def test_any_keyword_match_ranks_best_title_first(fake_net):
    result = job_tools.search_boards(["greenhouse:acme"], keywords="ai engineer")
    titles = [j["title"] for j in result["results"]]
    assert titles[0] == "AI Engineer"
    assert "Data Analyst" not in titles


def test_require_all_keeps_only_full_matches(fake_net):
    result = job_tools.search_boards(["greenhouse:acme"], keywords="ai engineer", require_all=True)
    assert [j["title"] for j in result["results"]] == ["AI Engineer"]


def test_location_filter(fake_net):
    result = job_tools.search_boards(["greenhouse:acme"], location="india")
    assert {j["title"] for j in result["results"]} == {"Data Analyst", "Machine Learning Engineer"}


def test_searches_several_boards_at_once(fake_net):
    result = job_tools.search_boards(["greenhouse:acme", "lever:acme"])
    assert result["total_matches"] == 4
    assert [b["jobs_on_board"] for b in result["boards"]] == [3, 1]


def test_limit_is_clamped(fake_net):
    assert len(job_tools.search_boards(["greenhouse:acme"], limit=0)["results"]) == 1
    assert len(job_tools.search_boards(["greenhouse:acme"], limit=1000)["results"]) == 3


def test_bad_entries_are_reported_not_raised(fake_net):
    result = job_tools.search_boards(["greenhouse:../etc/passwd", "workday:acme", "greenhouse:missing"])
    assert result["results"] == []
    assert all("error" in b for b in result["boards"])
    assert "404" in result["boards"][2]["error"]


def test_empty_list_without_companies_file_gives_clear_error():
    assert "error" in job_tools.search_boards([])


def test_companies_file_is_used_and_comments_ignored(fake_net):
    (ALLOWED_DIR / "companies.txt").write_text("# my list\n\ngreenhouse:acme\n", encoding="utf-8")
    result = job_tools.search_boards([])
    assert result["total_matches"] == 3


@pytest.mark.parametrize("bad", ["", ".", "..", "a/b", "../x", "a b", "-x", "x" * 80, "a?b=c", "a\\b"])
def test_token_pattern_blocks_path_tricks(bad):
    assert not job_tools.TOKEN_RE.match(bad)


# ---------- caching ----------

def test_second_request_uses_cache(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"jobs": []}

    def fake_get(url, **kwargs):
        calls.append(url)
        return FakeResponse()

    monkeypatch.setattr(job_tools.httpx, "get", fake_get)
    monkeypatch.setattr(job_tools.time, "sleep", lambda s: None)
    job_tools._get_json("https://boards-api.greenhouse.io/v1/boards/x/jobs")
    job_tools._get_json("https://boards-api.greenhouse.io/v1/boards/x/jobs")
    assert len(calls) == 1


# ---------- checking a role against the company's own board ----------

def test_found_by_listing_id_even_when_title_differs(fake_net):
    result = job_tools.verify_on_company_board(
        "Acme", "Totally Different Title", "https://careers.example.com/apply?gh_jid=1234567")
    assert result["status"] == "found" and result["matched_by"] == "listing id"


def test_found_by_exact_title(fake_net):
    result = job_tools.verify_on_company_board("Acme", "AI Engineer")
    assert result["status"] == "found" and result["matched_by"] == "exact title"


def test_loosely_similar_title_is_not_verification(fake_net):
    result = job_tools.verify_on_company_board("Acme", "Engineer")
    assert result["status"] == "board_only"
    assert result["similar_titles"] == ["AI Engineer"]


def test_unrelated_title_on_real_board_is_board_only(fake_net):
    result = job_tools.verify_on_company_board("Acme", "Remote Data Entry Specialist")
    assert result["status"] == "board_only"


def test_company_without_board(fake_net):
    assert job_tools.verify_on_company_board("Nonexistent Co", "AI Engineer")["status"] == "no_board"


def test_empty_title_is_skipped(fake_net):
    assert job_tools.verify_on_company_board("Acme", "")["status"] == "skipped"
