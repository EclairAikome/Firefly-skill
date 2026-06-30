"""Shared helpers for linkedin-job-scout.

Encodes the hard-won lessons from past runs:
- always UTF-8 (emojis appear in company names and JDs)
- ignore LinkedIn's auto skill-tags and company-insight noise when reading experience
- convert relative post dates to absolute
- Singapore base/business detection and direct-sales/MLM blacklisting
"""
import sys, io, re, os, datetime, json

# Force UTF-8 stdout so emoji/non-latin company names never crash a run.
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass


def load_config(path):
    import yaml  # invoke scripts via: uv run --with pyyaml python ...
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def clean_title(t):
    return re.sub(r"\s+with verification\s*$", "", (t or "").strip())


def identity_in_text(company, title, txt, head=400):
    """True iff the detail BODY actually describes this (company, title) job.

    A LinkedIn job detail page opens with "<company><job title> <location> · <posted> ...".
    A correctly-read page therefore contains the candidate's own company and the leading words
    of its title near the top. If it does not, the read captured a DIFFERENT job (the SPA
    off-by-one race) and the file must be rejected — never written to the workbook as this job.

    Tuned against the full captured corpus: flags exactly the cross-talk files, passes the rest.
    """
    h = norm(txt[:head] if txt else "")
    if not h:
        return False
    c, t = norm(company), norm(title)
    # The company name (when distinctive enough) must appear in the header region.
    if len(c) >= 4 and c not in h:
        return False
    # And a solid leading chunk of the title must appear too (guards short company names and
    # the rare case where two roles share a company).
    frag = t[:20]
    if len(frag) >= 6 and frag not in h:
        return False
    # If both signals are too weak to judge (tiny company AND tiny title), fall back to requiring
    # at least one of them to be present so we never silently accept an unrelated page.
    if len(c) < 4 and len(frag) < 6:
        return (c and c in h) or (frag and frag in h)
    return True


# ---------- dates ----------
_REL = re.compile(r"·\s*(?:Reposted\s*)?(\d+)\s*(minute|hour|day|week|month)s?\s*ago", re.I)
_UNIT_DAYS = {"minute": 0, "hour": 0, "day": 1, "week": 7, "month": 30}


def rel_to_abs_date(text, today=None):
    today = today or datetime.date.today()
    m = _REL.search(text or "")
    if not m:
        return today, "TBD"
    days = _UNIT_DAYS[m.group(2).lower()] * int(m.group(1))
    d = today - datetime.timedelta(days=days)
    return d, d.isoformat()


def loc_line(txt):
    for ln in (txt or "").split("\n"):
        if re.search(r"·.*(ago|apply)", ln, re.I) and re.search(
            r"singapore|remote|hybrid|on-site|hong kong|malaysia|apac|woodlands|jakarta|manila", ln, re.I):
            return re.sub(r"\s+", " ", ln).strip()
    return ""


def clean_loc(card_loc):
    base = (card_loc or "").split("(")[0].strip().rstrip(",").strip()
    return base or "Singapore"


def work_mode(card_loc):
    if "Hybrid" in (card_loc or ""):
        return "Hybrid"
    if "Remote" in (card_loc or ""):
        return "Remote"
    return "On-site"


# ---------- experience years ----------
# Read the employer's required experience from the FULL (expanded) JD. The hard part is not
# being fooled by: LinkedIn's auto skill-tags ("• 3+ years of work experience with <skill>"),
# company-insight noise ("2 year growth", "median tenure 4 years"), contract durations, or the
# word "age" hiding inside "manAGEment". So: scan normalized text (not lines), tie each
# year-number to an experience context, take the LOWER bound of any range, and use the smallest
# hard requirement as the floor.
_SKILLTAG = re.compile(r"•?\s*\d+\+?\s*years?\s*of work experience with[^•]*", re.I)
_EXCL = re.compile(r"\b(contract|tenure|history|growth|anniversary|founded|established|spans|"
                   r"hires|years old|aged)\b", re.I)
_SOFT = re.compile(r"\b(prefer\w*|nice to have|advantage|asset|bonus|ideally|a plus|would be)\b", re.I)
_HARD = re.compile(r"minimum|at least|must|require", re.I)
_YR = re.compile(r"(\d+)\s*(?:[-–—~～/]|to|and)?\s*(\d+)?\s*(\+)?\s*years?\b", re.I)


def min_required_years(txt):
    """Return (floor_years or None, evidence). Floor = smallest lower-bound across hard,
    experience-tied year requirements; a range like '3-5 years' contributes its lower number."""
    s = re.sub(r"\s+", " ", txt or "")
    s = _SKILLTAG.sub(" ", s)
    out = []
    for m in _YR.finditer(s):
        foll = s[m.end():m.end() + 30].lower().lstrip()
        ctx = s[max(0, m.start() - 45):m.end() + 30].lower()
        plus = bool(m.group(3))
        # a real requirement reads like "<n> years of/in/as ..." or "... experience ..." or
        # carries an explicit "+" (nobody writes "5+ years" for a contract length)
        if not (foll.startswith(("of ", "in ", "as ")) or "experien" in ctx or plus):
            continue
        if _EXCL.search(ctx):
            continue
        if _SOFT.search(ctx) and not _HARD.search(ctx):
            continue
        lo = int(m.group(1))
        if lo > 30:
            continue
        out.append((lo, s[max(0, m.start() - 15):m.end() + 22].strip()))
    if not out:
        return None, None
    out.sort(key=lambda x: x[0])
    return out[0][0], out[0][1][:160]


_SENIOR = re.compile(r"\b(senior|sr\.?|lead|principal|staff|director|vp|chief|head of)\b", re.I)


def is_senior_title(title):
    """A clear seniority signal in the title is not entry-level, whatever years it states."""
    return bool(_SENIOR.search(title or ""))


# ---------- employment type (full-time vs contract / part-time) ----------
# LinkedIn's job header reads "<Company><Title> <loc> · <posted> · <N> applicants ... <WorkMode>
# <EmploymentType> <Apply/Save>", e.g. "Hybrid Full-time Easy Apply", "On-site Contract Apply",
# "Hybrid Internship Easy Apply". The employment type is sandwiched between the work mode
# (On-site/Hybrid/Remote) and the Apply/Save action, so we read it from there (reliable) rather
# than from the word "contract" appearing anywhere in the JD body (which would catch "sales
# contracts" or a permanent "Contracts Manager" role).
_EMP_AFTER_MODE = re.compile(
    r"\b(?:on-?site|hybrid|remote)\s+(full-time|part-time|contract|temporary|internship|volunteer|other)\b", re.I)
_EMP_BEFORE_ACT = re.compile(
    r"\b(full-time|part-time|contract|temporary|internship|volunteer)\b\s*(?:easy apply|apply|save)\b", re.I)
# Title qualifiers that mark a fixed-term role even when the header is missing/ambiguous:
#   "(1 year contract)", "(Full-time Contract - 12 Months)", "12 Months Contract", "fixed-term".
# Note: bare "contract" alone is NOT used (would wrongly hit permanent "Contract/Contracts Manager").
_CONTRACT_TITLE = re.compile(
    r"\(\s*[^)]*\bcontract\b[^)]*\)|"
    r"\b\d+\s*(?:month|months|mth|mths|year|years|yr|yrs)[\s-]*contract\b|"
    r"\bcontract\b\s*[-–—]\s*\d+\s*(?:month|months|year|years)\b|"
    r"\bfixed[\s-]term\b", re.I)
_PARTTIME = re.compile(r"\bpart[\s-]?time\b", re.I)


def employment_type(title, txt):
    """Return the LinkedIn employment type token (lowercased) read from the header, or None."""
    head = (txt or "")[:700]
    m = _EMP_AFTER_MODE.search(head) or _EMP_BEFORE_ACT.search(head)
    return m.group(1).lower() if m else None


def is_part_time(title, txt):
    """True for part-time roles (header type Part-time, or 'part time' in the title)."""
    if _PARTTIME.search(title or ""):
        return True
    return employment_type(title, txt) == "part-time"


def is_contract(title, txt):
    """True for fixed-term / contract / temporary roles (header type, or a contract qualifier in
    the title). A permanent 'Full-time Contract - N Months' still counts as contract by intent."""
    if employment_type(title, txt) in ("contract", "temporary"):
        return True
    return bool(_CONTRACT_TITLE.search(title or ""))


# ---------- listing liveness / ghost detection (S1 + S3) ----------
# Fake/phishing/ghost listings tend to be dead or closed by the time the shortlist is read:
# the page is gone (404 placeholder), or it stopped accepting applications within a day or two
# of posting (resume-harvesting ghosts). Both are readable signals we previously ignored.
_REMOVED = re.compile(
    r"job posting (?:may not be valid|has been removed|is no longer available)|"
    r"unable to load the page|this job is no longer available", re.I)
_CLOSED = re.compile(r"no longer accepting applications", re.I)
_AGE = re.compile(r"(\d+)\s*(minute|hour|day|week|month)s?\s*ago", re.I)
_AGE_UNIT_H = {"minute": 1 / 60, "hour": 1, "day": 24, "week": 168, "month": 720}


def listing_status(txt):
    """'removed' (page gone), 'closed' (no longer accepting), or 'open'. Read from the detail
    text (works on already-saved files) or from a live re-ping's page text."""
    t = txt or ""
    if _REMOVED.search(t):
        return "removed"
    if _CLOSED.search(t[:1200]):   # the apply-status banner sits near the top of the pane
        return "closed"
    return "open"


def posted_hours(txt):
    """Hours since the listing was posted (from the '· N <unit> ago' header), or None."""
    m = _AGE.search((txt or "")[:600])
    if not m:
        return None
    return int(m.group(1)) * _AGE_UNIT_H[m.group(2).lower()]


def is_fast_close_ghost(txt, max_hours=48):
    """S3 freshness anomaly: a listing that has already stopped accepting applications within
    ~max_hours of being posted is almost never a real role filling that fast — it is the
    classic resume-harvesting / ghost pattern (e.g. 'posted 1 day ago' + 'no longer accepting')."""
    if listing_status(txt) != "closed":
        return False
    ph = posted_hours(txt)
    return ph is not None and ph <= max_hours


# ---------- Singapore base/business ----------
_FOREIGN_TAG = re.compile(r"\(hong kong\)|\bhong kong\b|\b-\s*my\b|\bmalaysia\b|\bjakarta\b|"
                          r"\bmanila\b|\bvietnam\b|\bthailand\b|\bindonesia\b|\beurope\b|\bchennai\b", re.I)


def is_singapore(loc, title, txt):
    lc = (loc or "").lower()
    if _FOREIGN_TAG.search(title or "") and "singapore" not in (title or "").lower():
        return False
    if "singapore" in lc:
        return True
    if lc.strip().startswith("apac") or "remote" in lc and "singapore" not in lc:
        return False
    return "singapore" in (txt or "").lower()[:600]


# ---------- direct-sales / MLM blacklist ----------
_MLM_COMPANY = re.compile(r"\b(organisation|organization)\b|\borg\b|marketing group|"
                          r"marketing solutions|business consulting", re.I)
_MLM_COPY = re.compile(
    r"invest in yourself|build the future you want|\bwarrior\b|uncapped commission|"
    r"commission only|no experience needed|training (is )?provided!!!|"
    r"sales (and|&) marketing representative|campaign marketing & sales|"
    r"travelling opportunities|unlimited earning|be your own boss", re.I)


def is_direct_sales_mlm(company, title, txt):
    blob = f"{title}\n{txt}"
    if _MLM_COPY.search(blob):
        return True
    if _MLM_COMPANY.search(company or ""):
        # company-name signal needs a sales/entry corroborator to avoid false positives
        if re.search(r"sales|entry.level|representative|no experience|commission|recruit", blob, re.I):
            return True
    return False


# ---------- heuristic fit score (fallback when not agent-scored) ----------
def keyword_overlap_score(jd, req, keywords):
    blob = f"{jd}\n{req}".lower()
    hits = sorted({k for k in keywords if k.lower() in blob})
    base = 60 + min(len(hits), 8) * 4          # 60..92
    return min(base, 95), hits


def read_json(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return json.load(f)


def write_json(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
