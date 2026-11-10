# jobhunt-mcp

A local [MCP](https://modelcontextprotocol.io) server that lets an AI chat app (such as Claude Desktop) help with a job search:

- check whether your CV can be read by applicant tracking systems (ATS),
- compare your CV to a job description and show real gaps versus noise,
- search open roles on companies' own public job boards,
- screen a posting for scam signals,
- keep a private tracker of what you saved and applied to.

It never applies for you. You review every role and submit every application yourself.

Your files stay on your computer. The server runs locally, reads only one folder, and needs no API key or paid service.

## Tools

| Tool | What it does |
|---|---|
| `read_cv` | Reads a PDF, DOCX, TXT or MD file from your jobhunt folder and returns its text. |
| `check_cv_health` | Flags parsing risks: unreadable text, tables (DOCX), missing standard headings, missing contact details, length. |
| `compare_cv_to_job` | Word-overlap between your CV and a pasted job description. Returns matched and missing terms. |
| `search_company_jobs` | Lists open roles on companies' public Greenhouse and Lever boards, filtered by title keywords and location. |
| `check_job_risk` | Looks for scam signals and checks whether the role exists on the company's own job board. |
| `save_job`, `list_jobs`, `get_job`, `update_job_status` | A local tracker (SQLite) for saved roles and application status. |

Two prompts are included: `rewrite_cv_for_role` (tailor your CV without inventing anything) and `evaluate_job` (risk check, honest fit, apply-or-skip recommendation for a saved job).

## What it deliberately does not do

- **No scraping of LinkedIn, Indeed or Glassdoor.** None offers a public job search API, and their terms prohibit scraping. Find a role there yourself, paste the posting into the chat, and the tools take it from there.
- **No auto-applying.** `update_job_status` records what *you* did.
- **No "ATS score".** Nobody outside the ATS vendors knows their scoring, so this tool reports concrete, checkable problems instead.
- **It cannot stop the AI from writing something untrue.** The prompts tell the model to use only facts from your CV. Read every rewrite before you use it.

## Install

You need [uv](https://docs.astral.sh/uv/) and an MCP client that can run local servers (developed and tested with Claude Desktop on Windows; other clients should work but are untested). Python 3.12 or newer is what the test suite is verified on.

```bash
git clone https://github.com/athulanish/jobhunt-mcp
cd jobhunt-mcp
uv sync
uv run setup_config.py
```

`setup_config.py` prints a JSON block. Merge it into your client's config (in Claude Desktop: Settings, Developer, Edit Config), then fully quit and reopen the app. The `jobhunt` server should show as running.

Put your CV in the jobhunt folder (default `~/jobhunt`; set the `JOBHUNT_DIR` environment variable to use another folder, and run `setup_config.py` again).

## Using it

Examples to type into your chat app:

- "Run check_cv_health on cv.pdf and explain each warning."
- "Compare cv.pdf to this job description, then tell me which gaps are real and what you need to ask me." (paste the posting)
- "Search my company boards for AI engineer roles in India." (list companies in `companies.txt`, below)
- "Save this posting to my tracker and run a risk check on it." (paste a posting from any site)

### Choosing companies

`search_company_jobs` reads company boards you choose. Create `companies.txt` in your jobhunt folder with one entry per line:

```
# lines starting with # are ignored
greenhouse:cloudflare
lever:some-company
```

To find a company's token, open its careers page and click a job. If the address starts with `boards.greenhouse.io/`, `job-boards.greenhouse.io/` or `jobs.lever.co/`, the next part of the address is the token. Many employers use other systems this tool cannot read.

## Privacy and security

- **Files:** only the jobhunt folder can be read. Paths outside it are refused, including `..` traversal, look-alike sibling folders and symlinks that point outside. Only `.pdf`, `.docx`, `.txt` and `.md` files are accepted.
- **What leaves your machine:**
  1. Requests to `boards-api.greenhouse.io` and `api.lever.co` when you search or verify a company. These contain company tokens only, never your CV.
  2. Whatever a tool returns (your CV text, a posting) is passed to the AI model behind your chat app, because that is how the AI reads it. Check that provider's privacy terms.
- **What is stored locally:** `jobhunt.db` (your tracker) and `.cache/` (job board responses, kept six hours) inside the jobhunt folder. Delete them whenever you like.
- **Untrusted text:** job postings can contain instructions aimed at an AI ("mark everything as applied"). The server returns posting text as data and tells the model not to follow it, and none of its tools can send email, submit forms or read outside the folder. A fooled AI could still write junk to your tracker, so keep your client's tool-approval prompts switched on and glance at what it saves.

## Limitations

- Covers only companies using Greenhouse or Lever, and only those you list. An empty board can mean a wrong token.
- Greenhouse listings show a last-edited date (`last_updated`), not a posting date. Lever shows a real posting date (`posted`).
- Keyword comparison is plain word counting: English only, noisy, and it does not understand synonyms. Treat it as a prompt for the AI's judgment.
- The health check can miss parsing problems it has no rule for, and DOCX table detection does not apply to PDFs.
- Scam checks are heuristics. Real postings can trip a rule and careful scammers avoid all of them. A role being on a company's own board proves the role exists, not that the person who contacted you works there. Always apply through the company's own careers page.

## Development

```bash
uv sync
uv run pytest
```

The tests use no network (all HTTP is mocked) and a temporary folder, so they never touch your real CV or tracker. They cover the folder restriction, CV parsing, keyword matching, job board parsing and caching, board verification, scam signals and the tracker.

```
server.py        MCP tools and prompts
cv_tools.py      CV reading, health check, keyword comparison, folder restriction
job_tools.py     Greenhouse and Lever boards, caching, board verification
risk_tools.py    scam signals
tracker.py       SQLite tracker
setup_config.py  prints the client config for your machine
tests/           unit tests
```

## Licence

MIT. See `LICENSE`.
