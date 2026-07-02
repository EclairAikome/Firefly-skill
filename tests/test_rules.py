"""Rule-function tests. Fixtures are REAL sentences from the 2026-07-02 run's
corpus - the eight employer year-requirements the adversarial review confirmed,
the noise patterns that must be ignored, the AVP/SVP titles that leaked, and the
roadshow copy that slipped the MLM net. Run:
  uv run --with pytest python -m pytest tests/ -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import lib_common as L


# ---------- years: real employer requirements (must fire) ----------
@pytest.mark.parametrize("txt,floor", [
    ("Requirements: 6-10 years of experience in banking transformation projects.", 6),
    ("You should have at least 7 years of relevant experience in financial markets.", 7),
    ("Minimum 3-5 years of experience in retail operations required.", 3),
    ("A minimum of 7 years experience managing outsourced vendors is required.", 7),
    ("5-8 years of hands-on experience with Murex or similar platforms.", 5),
    ("10-15 years of experience in enterprise sales required.", 10),
    ("Minimum 2 years of experience in an analytical or reporting role.", 2),
    ("Candidates must have 8+ years in growth or business development roles.", 8),
])
def test_years_real_requirements(txt, floor):
    got, ev = L.min_required_years(txt)
    assert got == floor, (got, ev)


# ---------- years: LinkedIn noise (must NOT fire) ----------
@pytest.mark.parametrize("txt", [
    "• 3+ years of work experience with Power BI • 2+ years of work experience with SQL",
    "Company insight: 2 year growth; median employee tenure: 4 years.",
    "Our history spans 80 years of engineering excellence.",
    "This is a 2 year contract position with option to renew.",   # contract length, not experience
])
def test_years_noise_ignored(txt):
    got, _ = L.min_required_years(txt)
    assert got is None, got


def test_years_stacked_clauses_visible():
    """The Hytech miss (2026-07-02): '3+ yrs PM AND 2+ yrs AI' gated at floor=2.
    The floor stays lenient by design, but ALL clauses must be surfaced for
    Phase 7 to read."""
    txt = ("Required Qualifications • 3+ years in product management or related "
           "roles • 2+ years of experience in AI/ML product delivery")
    clauses = L.required_years_clauses(txt)
    floors = sorted(y for y, _ in clauses)
    assert floors == [2, 3], clauses
    got, _ = L.min_required_years(txt)
    assert got == 2


def test_years_soft_mention_ignored_unless_hard():
    got, _ = L.min_required_years("Experience with SQL would be a plus; ideally 5 years in fintech.")
    assert got is None
    got, _ = L.min_required_years("Minimum 5 years of experience required; fintech ideally.")
    assert got == 5


def test_years_growth_domain_not_noise():
    """'growth' as a job domain must not be treated as company-insight noise -
    this exact pattern let an explicit 8-yr DBS requirement through on 2026-07-02."""
    got, _ = L.min_required_years(
        "Minimum 8 years of experience in growth, customer management, strategy, "
        "or business development roles.")
    assert got == 8
    got, _ = L.min_required_years("Company insight: 2 year growth; 8% increase.")
    assert got is None


# ---------- senior titles (the six 2026-07-02 leaks + controls) ----------
@pytest.mark.parametrize("title", [
    "Business Analyst (Global Markets), Mgr- AVP",
    "Vice President, Sales Effectiveness Analyst",
    "Global Custody Product Manager - SVP",
    "Business Analyst - IBOR, AVP",
    "Associate/AVP, Risk Analyst, Analysis & Reporting",
    "AVP, Growth & Customer Management, Product Manager",
    "EVP of Marketing",
    "Senior Product Manager",
    "Head of Growth",
])
def test_senior_titles_drop(title):
    assert L.is_senior_title(title)


@pytest.mark.parametrize("title", [
    "Associate Product Manager",
    "Marketing Executive",
    "Developer Advocate",          # 'avp' must not fire inside a word
    "Savvy Marketing Associate",
    "Junior Business Intelligence Developer",
])
def test_non_senior_titles_pass(title):
    assert not L.is_senior_title(title)


# ---------- direct-sales / MLM ----------
def test_mlm_roadshow_title_bait():
    assert L.is_direct_sales_mlm(
        "Hodie Marketing Singapore",
        "Junior Marketing Trainee (Gym membership/Mentorship/Travelling)",
        "mentorship provided, learn marketing")


def test_mlm_face_to_face_copy():
    assert L.is_direct_sales_mlm(
        "PeakPoint Marketing Ventures", "Launch Your Career in Sales & Marketing",
        "Represent leading brands through face-to-face marketing. 18 years old and above.")


def test_mlm_company_token_needs_corroborator():
    assert L.is_direct_sales_mlm(
        "Vision Organisation Pte Ltd", "Events & Brand Activator",
        "no experience needed, uncapped commission for entry level representatives")
    assert not L.is_direct_sales_mlm(
        "World Health Organisation", "Policy Analyst",
        "analyse regional health policy and draft reports")


def test_mlm_real_perks_do_not_fire():
    assert not L.is_direct_sales_mlm(
        "Google", "Product Manager",
        "benefits include gym membership, healthcare and travel insurance")
    assert not L.is_direct_sales_mlm(
        "X-PHY Inc", "Junior Product Executive",
        "Open to entry-level candidates; full training will be provided to ensure success")


# ---------- keyword overlap (heuristic fallback) ----------
def test_keywords_word_boundary():
    _, hits = L.keyword_overlap_score(
        "We write PRDs and April expressions.", "", ["PR", "SQL", "python"])
    assert hits == []
    _, hits = L.keyword_overlap_score(
        "Strong SQL and Python; public relations outreach.", "",
        ["PR", "SQL", "python", "public relations"])
    assert set(hits) == {"SQL", "python", "public relations"}


# ---------- employment type ----------
def test_employment_type_from_header():
    txt = ("Grab\nMarketing Associate - GrabFood, SG (Contract)\n"
           "Singapore, Singapore · 6 days ago · Over 200 applicants\n"
           "On-site Contract Apply\nAbout the job\n...")
    assert L.employment_type("Marketing Associate", txt) == "contract"
    assert L.is_contract("Marketing Associate - GrabFood, SG (Contract)", txt)


def test_contracts_manager_is_not_contract():
    txt = "Acme\nContracts Manager\nSingapore · 2 days ago\nOn-site Full-time Apply\nAbout the job\nmanage contracts"
    assert not L.is_contract("Contracts Manager", txt)


# ---------- listing liveness ----------
def test_fast_close_ghost():
    txt = "Acme\nRole\nSingapore · 1 day ago\nNo longer accepting applications\nAbout the job\n..."
    assert L.listing_status(txt) == "closed"
    assert L.is_fast_close_ghost(txt, 48)


def test_old_close_is_not_ghost():
    txt = "Acme\nRole\nSingapore · 3 weeks ago\nNo longer accepting applications\nAbout the job\n..."
    assert L.listing_status(txt) == "closed"
    assert not L.is_fast_close_ghost(txt, 48)


# ---------- singapore / foreign ----------
def test_foreign_card_conservative():
    assert L.is_foreign_card("Kuala Lumpur, Malaysia", "Marketing Executive")
    assert not L.is_foreign_card("Singapore, Singapore", "Marketing Executive")
    assert not L.is_foreign_card("", "Marketing Executive")   # ambiguous -> keep for JD check
    assert not L.is_foreign_card("Singapore", "Regional Manager - Malaysia market, Singapore based")


def test_identity_gate():
    assert L.identity_in_text("Monee", "Product Manager - LLM Platforms",
                              "Monee\nProduct Manager - LLM Platforms\nSingapore ...")
    assert not L.identity_in_text("Monee", "Product Manager - LLM Platforms",
                                  "Shopee\nData Analyst\nSingapore ...")
