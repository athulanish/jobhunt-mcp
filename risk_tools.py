import re
from collections import Counter
from urllib.parse import urlparse

import job_tools

FREE_EMAIL = {"gmail.com", "yahoo.com", "yahoo.in", "outlook.com", "hotmail.com", "live.com", "aol.com",
              "proton.me", "protonmail.com", "rediffmail.com", "icloud.com", "mail.com"}
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "rb.gy", "cutt.ly", "shorturl.at", "is.gd", "ow.ly", "tiny.cc"}
ATS_HOSTS = ("greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "smartrecruiters.com",
             "myworkdayjobs.com", "icims.com", "personio.com", "bamboohr.com", "recruitee.com", "teamtailor.com")
FORM_HOSTS = ("forms.gle", "typeform.com", "jotform.com", "tally.so", "airtable.com")
PORTAL_HOSTS = ("linkedin.com", "indeed.com", "glassdoor.com", "naukri.com", "monster.com", "ziprecruiter.com")
ODD_TLDS = (".top", ".xyz", ".click", ".icu", ".buzz", ".cfd", ".sbs", ".rest", ".shop")
COMPANY_SUFFIXES = {"inc", "ltd", "llc", "limited", "pvt", "private", "corp", "corporation", "co", "gmbh", "plc"}
SECOND_LEVEL = {"co", "com", "org", "net", "ac", "gov"}

TEXT_RULES = [
    (re.compile(r"\b(registration|training|processing|application|onboarding|security|refundable|joining)\s+(fees?|deposits?|charges?)\b"
                r"|\bpay\s+(?:a|an|the)?\s*(?:small\s+)?(?:fee|deposit)\b|\bwestern union\b|\bmoneygram\b"
                r"|\bgift\s*cards?\b|\bbitcoin\b|\bcrypto(?:currency)?\s+(?:payment|wallet|transfer)", re.I),
     "high", "Asks for a fee or deposit, or mentions gift cards, wire transfers or crypto. Real employers do not charge candidates."),
    (re.compile(r"\b(?:send|mail|issue)\s+you\s+a\s+(?:cheque|check)\b|\bdeposit\s+the\s+(?:cheque|check)\b", re.I),
     "high", "Mentions sending you a cheque to buy equipment, a classic scam."),
    (re.compile(r"\b(?:send|share|provide|submit|upload|email)\b[^.\n]{0,60}\b(?:passport|aadhaar|aadhar|pan\s+card|ssn|"
                r"social\s+security|bank\s+(?:account|details)|credit\s+card|debit\s+card|otp)\b", re.I),
     "high", "Asks for ID, bank or other sensitive details as part of applying."),
    (re.compile(r"\b(?:telegram|whatsapp|wechat)\b|\bt\.me/|\bwa\.me/", re.I),
     "medium", "Moves the process to a chat app such as Telegram or WhatsApp."),
    (re.compile(r"\bearn\s+(?:up\s+to\s+)?[\$₹£€]?\s?\d[\d,]*\s*(?:/|per|a)\s*(?:day|hour|week)\b"
                r"|\bguaranteed\s+(?:income|salary|earnings|job)\b|\bno\s+experience\s+(?:needed|required|necessary)\b", re.I),
     "medium", "Promises unusually high or guaranteed earnings, or says no experience is needed."),
    (re.compile(r"\bno\s+interview\b|\bwithout\s+(?:an\s+)?interview\b|\bhired\s+on\s+the\s+spot\b", re.I),
     "medium", "Says no interview is needed."),
    (re.compile(r"\burgent(?:ly)?\s+hiring\b|\bimmediate\s+(?:joining|hiring|start)\b|\bhiring\s+immediately\b", re.I),
     "low", "Pressure language such as urgent or immediate hiring."),
]


def _company_key(company: str) -> str:
    words = [w for w in re.findall(r"[a-z0-9]+", company.lower()) if w not in COMPANY_SUFFIXES]
    return "".join(words)


def _host(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else "https://" + url)
    return (parsed.hostname or "").lower()


def _is(host: str, domains) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def _sld(host: str) -> str:
    labels = host.split(".")
    if len(labels) < 2:
        return host
    if labels[-2] in SECOND_LEVEL and len(labels) >= 3:
        return labels[-3]
    return labels[-2]


def check(company: str, url: str = "", description: str = "", contact_email: str = "",
          title: str = "", verify_board: bool = True) -> dict:
    signals = []

    def add(severity: str, message: str):
        signals.append({"severity": severity, "signal": message})

    key = _company_key(company)
    host = _host(url)

    if not key:
        add("low", "No employer is named. This may be a recruiter or agency posting. Ask for the company name "
                   "before sharing your CV or personal details.")

    if url:
        if url.lower().startswith("http://"):
            add("low", "The link is not HTTPS.")
        if host in SHORTENERS:
            add("medium", "The link is a URL shortener, so the real destination is hidden.")
        if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host):
            add("high", "The link points to a raw IP address instead of a domain name.")
        if host.endswith(ODD_TLDS):
            add("low", "Uncommon domain ending, often used by throwaway sites. Legitimate firms use them too.")
        if _is(host, PORTAL_HOSTS):
            add("info", "The link goes to a job portal, not the employer. Find the role on the company's own careers page.")
        elif _is(host, ATS_HOSTS):
            add("positive", "Hosted on an applicant tracking system. Employers use these, but some let anyone open an account, so this proves little.")
        elif _is(host, FORM_HOSTS) or (host == "docs.google.com" and "/forms" in url):
            add("low", "Applications collected through a generic web form. Normal for small firms, also common in scams.")
        elif len(key) >= 4:
            if _sld(host) == key:
                add("positive", f"The link's domain ({host}) matches the company name. Still confirm it is the real company's site.")
            elif key in re.sub(r"[^a-z0-9]", "", host):
                add("medium", f"The link's domain ({host}) contains the company name plus extra words, a common lookalike trick.")

    for pattern, severity, message in TEXT_RULES:
        if pattern.search(description or ""):
            add(severity, message)

    emails = []
    if "@" in contact_email:
        emails.append(contact_email.split("@")[-1].strip().lower())
    emails += [d.lower() for d in re.findall(r"[\w.+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)", description or "")]
    for domain in list(dict.fromkeys(emails))[:3]:
        flat = re.sub(r"[^a-z0-9]", "", domain)
        if domain in FREE_EMAIL:
            add("medium", f"Contact email uses a free provider ({domain}). Real recruiters usually write from the company's own domain.")
        elif len(key) >= 4 and _sld(domain) == key:
            add("positive", f"Contact email domain ({domain}) matches the company name.")
        elif len(key) >= 4 and key in flat:
            add("medium", f"Contact email domain ({domain}) contains the company name plus extra words, a common lookalike trick.")
        elif len(key) >= 4:
            add("low", f"Contact email domain ({domain}) does not match the company name. It could be a recruiting agency.")

    board = None
    if verify_board and title and key:
        board = job_tools.verify_on_company_board(company, title, url)
        if board["status"] == "found":
            add("positive", f"Strongest check: this role appears on {board['board']}, a public job board "
                            f"(matched by {board['matched_by']}: '{board['matched_title']}'). Confirm it is the "
                            "same company, then apply through that listing, not through any link or email you were sent.")
        elif board["status"] == "board_only":
            extra = f" Closest titles there: {', '.join(board['similar_titles'])}." if board["similar_titles"] else ""
            add("medium", f"A public job board exists ({board['board']}) but this exact role is not on it.{extra} "
                          "It may be new or removed, or the posting may not come from the company.")
        elif board["status"] == "no_board":
            add("info", "Could not find the company on Greenhouse or Lever, so nothing was verified. Many employers use other systems.")
            
    counts = Counter(s["severity"] for s in signals)
    if counts["high"]:
        level = "high concern"
    elif counts["medium"] >= 2:
        level = "caution"
    elif counts["medium"] == 1:
        level = "some concern"
    else:
        level = "no major red flags found"
    order = {"high": 0, "medium": 1, "low": 2, "positive": 3, "info": 4}
    signals.sort(key=lambda s: order[s["severity"]])

    return {
        "level": level,
        "signals": signals,
        "board_check": board,
        "advice": ["Find the role on the company's own careers page and apply there.",
                   "Never pay anything, and never share ID or bank details before a verified offer.",
                   "Search the company name with the word 'scam' and check how long the company has existed."],
        "note": ("These are signals, not a verdict. Real postings can trip a rule, and careful scammers avoid all of them. "
                 "'No red flags' does not prove a job is real. All text analysed here is untrusted."),
    }