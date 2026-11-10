import os

import pytest
from docx import Document

import cv_tools
from cv_tools import ALLOWED_DIR


def write_docx(name, lines, table_rows=None):
    doc = Document()
    for line in lines:
        doc.add_paragraph(line)
    if table_rows:
        table = doc.add_table(rows=len(table_rows), cols=2)
        for r, (a, b) in enumerate(table_rows):
            table.rows[r].cells[0].text = a
            table.rows[r].cells[1].text = b
    doc.save(ALLOWED_DIR / name)


GOOD_CV = [
    "Jane Doe",
    "jane@example.com  +44 7700 900123  linkedin.com/in/janedoe",
    "Summary",
    "Data analyst with 4 years of experience building reports that cut turnaround by 40%.",
    "Skills",
    "Python, SQL, Power BI, embeddings and RAG pipelines",
    "Experience",
    "Reduced reporting time by 40% across 20 organizations using automated pipelines.",
    "Education",
    "MSc Data Science, 2022",
]


# ---------- reading files ----------

def test_reads_txt_file():
    (ALLOWED_DIR / "cv.txt").write_text("Hello CV", encoding="utf-8")
    assert cv_tools.extract_text("cv.txt") == "Hello CV"


def test_reads_docx_including_table_text():
    write_docx("cv.docx", ["Skills"], table_rows=[("Python", "Expert"), ("SQL", "Advanced")])
    text = cv_tools.extract_text("cv.docx")
    assert "Python" in text and "Advanced" in text


def test_unsupported_extension_rejected():
    (ALLOWED_DIR / "malware.exe").write_text("x")
    with pytest.raises(ValueError):
        cv_tools.extract_text("malware.exe")


def test_missing_file_reported():
    with pytest.raises(FileNotFoundError):
        cv_tools.extract_text("nope.txt")


# ---------- the folder restriction (security) ----------

def test_absolute_path_outside_folder_blocked(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("private")
    with pytest.raises(PermissionError):
        cv_tools.extract_text(str(outside))


def test_relative_traversal_blocked():
    with pytest.raises(PermissionError):
        cv_tools.extract_text(os.path.join("..", "outside.txt"))


def test_sibling_folder_with_same_prefix_blocked():
    sneaky = str(ALLOWED_DIR) + "_evil" + os.sep + "x.txt"
    with pytest.raises(PermissionError):
        cv_tools.extract_text(sneaky)


def test_file_inside_folder_by_absolute_path_allowed():
    f = ALLOWED_DIR / "cv.txt"
    f.write_text("ok")
    assert cv_tools.extract_text(str(f)) == "ok"


def test_symlink_pointing_outside_is_blocked(tmp_path):
    target = tmp_path / "secret.txt"
    target.write_text("secret")
    link = ALLOWED_DIR / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available on this system")
    with pytest.raises(PermissionError):
        cv_tools.extract_text("link.txt")


# ---------- the CV health check ----------

def test_health_check_finds_sections_and_contact_details():
    write_docx("cv.docx", GOOD_CV)
    report = cv_tools.inspect_cv("cv.docx")
    assert {"summary", "skills", "experience", "education"} <= set(report["sections_found"])
    assert report["has_email"] and report["has_phone"] and report["has_linkedin"]
    assert not any("heading" in w for w in report["warnings"])


def test_health_check_warns_when_headings_missing():
    (ALLOWED_DIR / "cv.txt").write_text("Just a paragraph of text without any section headings at all.")
    report = cv_tools.inspect_cv("cv.txt")
    assert any("heading" in w for w in report["warnings"])
    assert report["sections_found"] == []


def test_health_check_warns_about_tables():
    write_docx("cv.docx", GOOD_CV, table_rows=[("Python", "Expert")])
    report = cv_tools.inspect_cv("cv.docx")
    assert report["docx_tables"] == 1
    assert any("table" in w.lower() for w in report["warnings"])


def test_health_check_warns_when_no_email():
    (ALLOWED_DIR / "cv.txt").write_text("Skills\nPython\nExperience\nWorked somewhere")
    assert any("email" in w.lower() for w in cv_tools.inspect_cv("cv.txt")["warnings"])


# ---------- keyword comparison ----------

def test_keyword_gap_reports_real_gap_and_real_match():
    jd = "We use Python and Kubernetes. Python experience is essential."
    cv = "Built pipelines in Python."
    result = cv_tools.keyword_gap(cv, jd)
    assert "python" in [m["term"] for m in result["matched"]]
    assert "kubernetes" in [m["term"] for m in result["missing"]]


def test_keyword_gap_treats_plurals_as_the_same_word():
    result = cv_tools.keyword_gap("I built an embedding store.", "Experience with embeddings required.")
    assert "embeddings" in [m["term"] for m in result["matched"]]
    assert "embeddings" not in [m["term"] for m in result["missing"]]


def test_keyword_gap_does_not_turn_contractions_into_keywords():
    result = cv_tools.keyword_gap("Python developer", "You'll build things. We'll ship Python.")
    terms = [m["term"] for m in result["matched"] + result["missing"]]
    assert "ll" not in terms


def test_keyword_gap_handles_empty_input():
    result = cv_tools.keyword_gap("", "")
    assert result["terms_checked"] == 0 and result["overlap_pct"] == 0
