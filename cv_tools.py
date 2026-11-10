import re
import os
from pathlib import Path

ALLOWED_DIR = Path(os.environ.get("JOBHUNT_DIR", "~/jobhunt")).expanduser().resolve()


def _safe_path(path: str) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = ALLOWED_DIR / p
    p = p.resolve()
    if not p.is_relative_to(ALLOWED_DIR):
        raise PermissionError(f"Files must be inside {ALLOWED_DIR}. Move your CV into that folder first.")
    return p
from collections import Counter
from pathlib import Path

from docx import Document
from pypdf import PdfReader

CORE_SECTIONS = {
    "experience": ["experience", "work experience", "professional experience", "employment history", "work history"],
    "education": ["education", "academic background", "qualifications"],
    "skills": ["skills", "technical skills", "core skills", "key skills"],
}
OPTIONAL_SECTIONS = {
    "summary": ["summary", "profile", "professional summary", "about me"],
    "projects": ["projects", "personal projects"],
    "certifications": ["certifications", "certificates", "licenses"],
}

STOPWORDS = set("""a an and are as at be been but by for from has have i in is it its of on or our
that the their this to we will with you your about across also any can more most other such than
then these they those through using use used within without work working experience experienced
years year team teams ability strong good great etc including include role responsibilities
requirements required preferred looking candidate company""".split())
STOPWORDS |= set("""into what get new real doing like well need needs help helps make makes take
takes know see want wants over under between each every both many much very just only own
ll ve re s t d m""".split())

KEEP_SHORT = {"r", "c"}
TOKEN = re.compile(r"[a-z][a-z0-9+#.\-]*")
SPLIT = re.compile(r"[\n;:,!?()|•/]|\.\s")


def load_cv(path: str) -> dict:
    p = _safe_path(path)
    if not p.exists():
        raise FileNotFoundError(f"No file at {p}")
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(p))
        raw = "\n".join((page.extract_text() or "") for page in reader.pages)
        bad = raw.count("\x00") + raw.count("\ufffd")
        return {"text": raw.replace("\x00", ""), "file_type": "pdf", "pages": len(reader.pages),
                "tables": None, "unreadable_chars": bad}
    if suffix == ".docx":
        doc = Document(str(p))
        parts = [par.text for par in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" ".join(cell.text for cell in row.cells))
        return {"text": "\n".join(parts), "file_type": "docx", "pages": None, "tables": len(doc.tables)}
    if suffix in {".txt", ".md"}:
        return {"text": p.read_text(encoding="utf-8", errors="ignore"),
                "file_type": suffix[1:], "pages": None, "tables": None}
    raise ValueError(f"Unsupported file type '{suffix}'. Use PDF, DOCX, TXT or MD.")


def extract_text(path: str) -> str:
    return load_cv(path)["text"]


def _headings_found(text: str) -> set:
    found = set()
    sections = {**CORE_SECTIONS, **OPTIONAL_SECTIONS}
    for line in text.splitlines():
        clean = re.sub(r"[^a-z ]", "", line.lower()).strip()
        if not clean or len(clean) > 40:
            continue
        for name, aliases in sections.items():
            if clean in aliases:
                found.add(name)
    return found


def inspect_cv(path: str) -> dict:
    cv = load_cv(path)
    text = cv["text"]
    word_count = len(text.split())
    found = _headings_found(text)
    lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 25]
    with_numbers = [l for l in lines if re.search(r"\d|%|\$", l)]
    pct_numeric = round(100 * len(with_numbers) / len(lines)) if lines else 0

    has_email = bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text))
    has_phone = bool(re.search(r"\+?\d[\d\s().-]{8,}\d", text))
    has_linkedin = "linkedin.com" in text.lower()

    warnings = []
    bad = cv.get("unreadable_chars", 0)
    if bad:
        warnings.append(f"{bad} unreadable characters found. Some text, often headings in a special font, "
                        "could not be extracted, so a text-based ATS parser may not see it either.")

        if cv["pages"] and cv["pages"] > 2:
            per_page = round(word_count / cv["pages"])
            msg = f"{cv['pages']} pages (about {per_page} words per page). Two pages is the usual length for a CV."
            if per_page < 400:
                msg += " A low words-per-page figure suggests heavy spacing or margins."
            warnings.append(msg)
    if cv["file_type"] == "pdf" and cv["pages"] and word_count / cv["pages"] < 80:
        warnings.append("Very little text per page. This PDF may be a scan or image, which ATS parsers cannot read.")
    if cv["tables"]:
        warnings.append(f"{cv['tables']} table(s) found. Many ATS parsers scramble table content.")
    missing = [s for s in CORE_SECTIONS if s not in found]
    if missing:
        warnings.append(f"Standard section heading(s) not detected: {', '.join(missing)}.")
    if not has_email:
        warnings.append("No email address detected in the extracted text.")
    if pct_numeric < 25:
        warnings.append(f"Only {pct_numeric}% of lines contain a number. Quantified results usually read stronger.")

    return {
        "file_type": cv["file_type"], "unreadable_chars": bad,
        "pages": cv["pages"],
        "word_count": word_count,
        "sections_found": sorted(found),
        "has_email": has_email,
        "has_phone": has_phone,
        "has_linkedin": has_linkedin,
        "docx_tables": cv["tables"],
        "lines_with_numbers_pct": pct_numeric,
        "warnings": warnings,
    }


def _clean(text: str) -> str:
    text = text.replace("\u2019", "'")
    return re.sub(r"'(?:s|ll|ve|re|d|t|m)\b", "", text)  # you'll -> you, company's -> company


def _terms(text: str) -> Counter:
    terms = Counter()
    for segment in SPLIT.split(_clean(text).lower()):
        toks = [t.rstrip(".-") for t in TOKEN.findall(segment)]
        toks = [t for t in toks if len(t) > 1 or t in KEEP_SHORT]
        for t in toks:
            if t not in STOPWORDS:
                terms[t] += 1
        for a, b in zip(toks, toks[1:]):
            if a not in STOPWORDS and b not in STOPWORDS:
                terms[f"{a} {b}"] += 1
    return terms


def _skill_like(text: str) -> set:
    """Words written Capitalised or ALL-CAPS mid-sentence: a cheap hint that they are tools or skills."""
    like = set()
    for segment in SPLIT.split(_clean(text)):
        words = [w.rstrip(".-") for w in re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]*", segment)]
        for w in words[1:]:
            if len(w) > 1 and w[0].isupper():
                like.add(w.lower())
    return like

def _norm(w: str) -> str:
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def _key(term: str) -> str:
    return " ".join(_norm(w) for w in term.split())



def keyword_gap(cv_text: str, jd_text: str, top_n: int = 40) -> dict:
    jd = _terms(jd_text)
    cv = _terms(cv_text)
    cv_keys = {_key(t) for t in cv}
    like = _skill_like(jd_text)

    def score(term, count):
        boost = 3 if all(w in like for w in term.split()) else 1
        return count * boost

    ranked = sorted(jd.items(), key=lambda kv: (-score(*kv), -len(kv[0])))[:top_n]
    matched = [{"term": t, "times_in_job": n} for t, n in ranked if _key(t) in cv_keys]
    missing = [{"term": t, "times_in_job": n} for t, n in ranked if _key(t) not in cv_keys]
    return {
        "terms_checked": len(ranked),
        "overlap_pct": round(100 * len(matched) / len(ranked)) if ranked else 0,
        "matched": matched,
        "missing": missing,
        "note": ("Crude word-overlap, not a real ATS score. The list contains noise. "
                 "Only suggest adding a missing term if the candidate genuinely has that skill."),
    }