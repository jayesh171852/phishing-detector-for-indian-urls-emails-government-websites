"""
tests/test_gov_verifier.py
--------------------------
Pytest tests for government/gov_verifier.py.

Covers the edge cases called out in docs/SPEC.md Phase 3:
  - uidai.gov.in.evil.xyz          (gov domain in sub-domain of evil host)
  - evil.com/uidai.gov.in/login    (gov domain in path, not host)
  - uidai.gov.in@evil.com          (gov domain in URL credentials / user-info)
  - uppercase hosts                (HTTPS://UIDAI.GOV.IN/)
  - trailing dots                  (https://uidai.gov.in./)
  - ports                          (https://uidai.gov.in:443/)

Plus additional correctness checks for all five rules.
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from government.gov_verifier import GovVerifier

@pytest.fixture(scope="module")
def v():
    """One verifier instance shared across all tests in this module."""
    return GovVerifier()


# ── Rule 2: real .gov.in / .nic.in ───────────────────────────────────────────

class TestRule2:
    def test_plain_gov_in(self, v):
        r = v.check("https://uidai.gov.in/en/my-aadhaar")
        assert r is not None
        assert r.verdict == "LEGIT_GOV"

    def test_plain_nic_in(self, v):
        r = v.check("https://bhagalpur.nic.in/district-election-office/")
        assert r is not None
        assert r.verdict == "LEGIT_GOV"

    def test_uppercase_host(self, v):
        """SPEC: uppercase hosts must still be recognised as LEGIT_GOV."""
        r = v.check("HTTPS://UIDAI.GOV.IN/")
        assert r is not None
        assert r.verdict == "LEGIT_GOV", f"Got: {r}"

    def test_trailing_dot(self, v):
        """SPEC: trailing dot on host must still be recognised as LEGIT_GOV."""
        r = v.check("https://uidai.gov.in./")
        assert r is not None
        assert r.verdict == "LEGIT_GOV", f"Got: {r}"

    def test_port(self, v):
        """SPEC: port in URL must still be recognised as LEGIT_GOV."""
        r = v.check("https://uidai.gov.in:443/")
        assert r is not None
        assert r.verdict == "LEGIT_GOV", f"Got: {r}"

    def test_punycode_gov_in(self, v):
        """
        A Punycode host that genuinely ends .gov.in must be LEGIT_GOV.
        We construct a synthetic xn-- host that decodes to something.gov.in.
        Real example from gov_test: 'xn--something.gov.in' — we fake the label
        but keep the real suffix '.gov.in'.
        """
        # xn--11b5b5a9ajc9c.gov.in is a valid Punycode label with .gov.in suffix
        r = v.check("https://xn--11b5b5a9ajc9c.gov.in/")
        assert r is not None
        assert r.verdict == "LEGIT_GOV", f"Got: {r}"

    def test_punycode_non_gov_in_not_auto_legit(self, v):
        """
        A Punycode host under .bharat (xn--h2brj9c) does NOT end .gov.in
        so rule 2 does not fire.  It must not be mis-classified as PHISHING.
        """
        r = v.check("https://xn--i1b5bzbybhfo5c8b4bxh.xn--11b7cb3a6a.xn--h2brj9c/")
        # Falls through to rule 5 (None) or gets flagged by rule 4.
        # Either way it must NOT be PHISHING or PHISHING_GOV
        if r is not None:
            assert r.verdict not in ("PHISHING", "PHISHING_GOV"), f"Got: {r}"

    def test_subdomain_gov_in(self, v):
        r = v.check("https://services.india.gov.in/service/detail")
        assert r is not None
        assert r.verdict == "LEGIT_GOV"


# ── Rule 4: structural tricks ─────────────────────────────────────────────────

class TestStructuralTricks:
    def test_gov_in_subdomain_of_evil(self, v):
        """SPEC: uidai.gov.in.evil.xyz — .gov.in is a sub-string, not a real suffix."""
        r = v.check("https://uidai.gov.in.evil.xyz/login")
        assert r is not None
        assert r.verdict in ("PHISHING_GOV", "PHISHING"), f"Got: {r}"

    def test_gov_in_in_path(self, v):
        """SPEC: evil.com/uidai.gov.in/login — .gov.in is in the path, not the host."""
        r = v.check("https://evil.com/uidai.gov.in/login")
        assert r is not None
        assert r.verdict in ("PHISHING_GOV", "PHISHING"), f"Got: {r}"

    def test_gov_in_in_credentials(self, v):
        """SPEC: uidai.gov.in@evil.com — real host is evil.com."""
        r = v.check("https://uidai.gov.in@evil.com/")
        assert r is not None
        assert r.verdict in ("PHISHING_GOV", "PHISHING"), f"Got: {r}"

    def test_gov_in_in_subdomain_path(self, v):
        r = v.check("https://secure034.com/uidai.gov.in/login")
        assert r is not None
        assert r.verdict in ("PHISHING_GOV", "PHISHING"), f"Got: {r}"


# ── Rule 4: keyword + risk factor ─────────────────────────────────────────────

class TestImpersonation:
    def test_aadhaar_cheap_tld(self, v):
        r = v.check("https://eaadhar.cfd/")
        assert r is not None
        assert r.verdict in ("PHISHING_GOV", "PHISHING"), f"Got: {r}"

    def test_incometax_lookalike(self, v):
        r = v.check("https://incometax-login.org")
        assert r is not None
        assert r.verdict in ("PHISHING_GOV", "SUSPICIOUS", "PHISHING"), f"Got: {r}"

    def test_parivahan_xyz(self, v):
        r = v.check("https://emparivahan.top/portal/login.php")
        assert r is not None
        assert r.verdict in ("PHISHING_GOV", "PHISHING"), f"Got: {r}"

    def test_keyword_only_no_risk(self, v):
        """
        A URL with a gov keyword but no risk factor should be at most SUSPICIOUS,
        not PHISHING_GOV.  (LEGIT / LEGIT_GOV / None are also acceptable if the
        verifier is conservative.)
        """
        r = v.check("https://passportindia.org/apply")
        # Must NOT return PHISHING_GOV without a risk factor
        if r is not None:
            assert r.verdict != "PHISHING_GOV", (
                f"PHISHING_GOV returned without a risk factor: {r}"
            )


# ── Rule 1: blocklist ─────────────────────────────────────────────────────────

class TestBlocklist:
    def test_blocklisted_host(self, v):
        """phishing.example.com is in the placeholder blocklist."""
        r = v.check("https://phishing.example.com/steal")
        assert r is not None
        assert r.verdict == "PHISHING", f"Got: {r}"

    def test_non_blocklisted_is_not_blocked(self, v):
        r = v.check("https://google.com/")
        # Google is not gov, not blocklisted — should return None or LEGIT
        if r is not None:
            assert r.verdict not in ("PHISHING", "PHISHING_GOV"), f"Got: {r}"


# ── Rule 5: no match ──────────────────────────────────────────────────────────

class TestNoMatch:
    def test_plain_commercial(self, v):
        assert v.check("https://google.com/") is None or \
               v.check("https://google.com/").verdict not in ("PHISHING", "PHISHING_GOV")

    def test_hard_negative_passport(self, v):
        """passport.com is a hard negative — not an Indian gov site, not phishing."""
        r = v.check("https://passport.com/")
        if r is not None:
            assert r.verdict not in ("PHISHING_GOV",), f"Got: {r}"

    def test_hard_negative_usps(self, v):
        r = v.check("https://www.usps.com/search/results.htm?PNO=1&keyword=Passports")
        if r is not None:
            assert r.verdict not in ("PHISHING_GOV",), f"Got: {r}"
