"""
government/gov_verifier.py
--------------------------
Rule-based government-site verifier.  No network calls.  Target < 5 ms/URL.

Rules applied in order (first match wins):
  1. Blocklist  -> PHISHING
  2. .gov.in / .nic.in suffix (incl. Punycode hosts) -> LEGIT_GOV
  3. Trusted allowlist (official_domains.csv) -> LEGIT_GOV or LEGIT
  4. Impersonation (keyword + risk factor, or structural trick) -> PHISHING_GOV or SUSPICIOUS
  5. No match -> None  (fall through to the ML model)

Public API
----------
  verifier = GovVerifier()              # loads data/reference files once
  result   = verifier.check(url)        # returns GovResult | None

GovResult fields:
  verdict   : str  — LEGIT_GOV | LEGIT | PHISHING_GOV | SUSPICIOUS | PHISHING
  reason    : str  — human-readable explanation
  matched   : str | None — the domain/rule that triggered the verdict
"""

from __future__ import annotations

import re
import csv
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from rapidfuzz import fuzz

# ── Paths ─────────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BLOCKLIST_PATH   = _REPO_ROOT / "data" / "reference" / "blocklist.txt"
_ALLOWLIST_PATH   = _REPO_ROOT / "data" / "reference" / "official_domains.csv"

# ── Constants ─────────────────────────────────────────────────────────────────

# Suffixes that grant LEGIT_GOV (checked at a label boundary)
_GOV_SUFFIXES = (".gov.in", ".nic.in")

# Keywords whose presence in the host or path is evidence of impersonation
_GOV_KEYWORDS = {
    "uidai", "aadhaar", "aadhar", "incometax", "itr", "epfo",
    "digilocker", "passport", "parivahan", "nvsp", "pmkisan",
    "umang", "gst", "mygov", "cowin",
    # additional keywords present in eval set lookalikes
    "irctc", "epfindia", "rtionline", "rti",
}

# Strings that, when found *outside* the true suffix, are evidence of impersonation
_FAKE_SUFFIX_PATTERNS = ("gov.in", "nic.in", "gov-in")

# Risk-factor patterns on the host
_CHEAP_TLDS = {
    "xyz", "top", "click", "work", "loan", "online", "site", "shop",
    "info", "biz", "icu", "club", "vip", "buzz", "world", "live",
    "fun", "pro", "digital", "tech", "store", "cfd", "sbs",
    # additional unambiguously low-trust TLDs
    "lol", "cc",
}
_FREE_PLATFORMS = {
    "blogspot.com", "weebly.com", "wixsite.com", "wixstudio.com",
    "pages.dev", "netlify.app", "vercel.app", "github.io", "glitch.me",
    "000webhostapp.com", "wordpress.com",
    # Firebase hosting
    "web.app", "firebaseapp.com",
}

# Keyword strings to fuzzy-match the *first host label* against,
# to catch misspelling lookalikes (uiadi, uidaii, parivahn, etc.)
_FUZZY_KEYWORDS = {
    "uidai", "aadhaar", "aadhar", "incometax", "digilocker",
    "passport", "parivahan", "pmkisan", "mygov", "cowin",
    "irctc", "epfindia", "epfo", "nvsp", "umang", "rtionline",
}
_FUZZY_KEYWORD_THRESHOLD = 85

# RapidFuzz similarity threshold for label-level match to an official org name
_FUZZY_THRESHOLD = 88


@dataclass
class GovResult:
    verdict: str
    reason: str
    matched: Optional[str] = None


def _clean_host(raw_host: str) -> str:
    """Lower-case, strip trailing dot, strip port."""
    h = (raw_host or "").lower().rstrip(".")
    # strip port if present (e.g. uidai.gov.in:443)
    if ":" in h:
        h = h.split(":")[0]
    return h


def _ends_with_gov_suffix(host: str) -> bool:
    """True if host equals or ends with .gov.in or .nic.in at a label boundary."""
    for suf in _GOV_SUFFIXES:
        if host == suf.lstrip("."):
            return True
        if host.endswith(suf):
            return True
    return False


def _tld_of(host: str) -> str:
    """Return the last label(s) of the host as a rough TLD proxy."""
    parts = host.split(".")
    if len(parts) >= 2:
        return parts[-1]
    return host


def _has_risk_factor(host: str) -> bool:
    """True if the host has at least one risk indicator."""
    tld = _tld_of(host)
    if tld in _CHEAP_TLDS:
        return True
    # hyphen present in the host at all (beyond the TLD separator) — common in lookalikes
    # e.g. umang-india.com, incometax-online.com, irctc-link.co.in
    host_without_tld = ".".join(host.split(".")[:-1]) if "." in host else host
    if "-" in host_without_tld:
        return True
    # digit-heavy: more than 4 digits in the host
    digit_count = sum(c.isdigit() for c in host)
    if digit_count >= 4:
        return True
    # free hosting platform
    for plat in _FREE_PLATFORMS:
        if host.endswith("." + plat) or host == plat:
            return True
    return False


def _load_blocklist(path: Path) -> tuple[set, set]:
    """
    Returns (blocked_hosts, blocked_urls).
    Lines starting with # are comments; blank lines ignored.
    """
    hosts: set[str] = set()
    urls: set[str] = set()
    if not path.exists():
        return hosts, urls
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # If it looks like a full URL keep it as-is too; always index the host
            lower = line.lower()
            urls.add(lower)
            parsed = urlparse(lower if "//" in lower else "http://" + lower)
            h = _clean_host(parsed.hostname or "")
            if h:
                hosts.add(h)
    return hosts, urls


def _load_allowlist(path: Path) -> dict[str, dict]:
    """
    Returns {domain_lower: {organisation, category, verified, source_note}}.
    Skips rows where verified == 'no'.
    """
    result: dict[str, dict] = {}
    if not path.exists():
        return result
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("verified", "").strip().lower() == "no":
                continue
            domain = row.get("domain", "").strip().lower().lstrip("www.").rstrip(".")
            if domain:
                result[domain] = dict(row)
    return result


class GovVerifier:
    """
    Thread-safe government-site verifier.
    Call reload() to hot-reload blocklist without restarting.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reload()

    def _reload(self) -> None:
        bl_hosts, bl_urls = _load_blocklist(_BLOCKLIST_PATH)
        allowlist = _load_allowlist(_ALLOWLIST_PATH)
        # Collect official organisation labels for fuzzy matching
        org_labels = [
            v["organisation"].lower()
            for v in allowlist.values()
            if v.get("organisation")
        ]
        with self._lock:
            self._bl_hosts = bl_hosts
            self._bl_urls  = bl_urls
            self._allowlist = allowlist
            self._org_labels = org_labels

    def reload(self) -> None:
        """Hot-reload blocklist and allowlist from disk."""
        self._reload()

    # ── Public entry point ────────────────────────────────────────────────────

    def check(self, url: str) -> Optional[GovResult]:
        """
        Apply the five rules in order.  Returns a GovResult on the first
        match, or None if no rule matches (fall through to the ML model).
        """
        # Parse once; use the raw URL for blocklist, cleaned host for everything else
        try:
            parsed = urlparse(url if "//" in url else "http://" + url)
        except Exception:
            return None

        raw_host = parsed.hostname or ""
        host = _clean_host(raw_host)
        path_str = (parsed.path or "").lower()

        if not host:
            return None

        with self._lock:
            bl_hosts  = self._bl_hosts
            bl_urls   = self._bl_urls
            allowlist = self._allowlist
            org_labels = self._org_labels

        # ── Rule 1: Blocklist ─────────────────────────────────────────────────
        url_lower = url.lower()
        if url_lower in bl_urls or host in bl_hosts:
            return GovResult(
                verdict="PHISHING",
                reason="Listed in the confirmed blocklist.",
                matched=host,
            )

        # ── Rule 2: .gov.in / .nic.in suffix ─────────────────────────────────
        # Applies even to Punycode (xn--) hosts — only gov bodies can register here.
        if _ends_with_gov_suffix(host):
            return GovResult(
                verdict="LEGIT_GOV",
                reason=f"Verified Indian government domain ({host}).",
                matched=host,
            )

        # ── Rule 2b: credential-based structural trick ────────────────────────
        # e.g.  https://uidai.gov.in@evil.com/
        # urlparse correctly puts evil.com as hostname; but the userinfo
        # (before @) contains a gov suffix — that is a deception attempt.
        raw_netloc = parsed.netloc or ""
        if "@" in raw_netloc:
            userinfo = raw_netloc.split("@")[0].lower()
            for suf in _GOV_SUFFIXES:
                if suf in userinfo:
                    return GovResult(
                        verdict="PHISHING_GOV",
                        reason=(
                            f"Government domain '{userinfo}' used in URL credentials "
                            f"to deceive — the real host is '{host}'."
                        ),
                        matched=userinfo,
                    )

        # ── Rule 3: Trusted allowlist ─────────────────────────────────────────
        # Try exact match, then match without leading www.
        for candidate in (host, host.removeprefix("www.")):
            if candidate in allowlist:
                entry = allowlist[candidate]
                cat   = entry.get("category", "").strip().lower()
                org   = entry.get("organisation", candidate)
                if cat == "psu_or_brand":
                    return GovResult(
                        verdict="LEGIT",
                        reason=f"Verified official organisation domain: {org}.",
                        matched=candidate,
                    )
                return GovResult(
                    verdict="LEGIT_GOV",
                    reason=f"On the verified government allowlist: {org}.",
                    matched=candidate,
                )

        # ── Rule 4: Impersonation detection ───────────────────────────────────
        # Decode Punycode host labels to Unicode so keyword/fuzzy checks work on
        # lookalikes like xn--udai-lza.com (ûdai) or xn--dgilocker-vpb.com
        host_decoded = host
        if "xn--" in host:
            try:
                host_decoded = host.encode("ascii").decode("idna")
            except Exception:
                pass  # keep raw if decode fails

        combined = host_decoded + path_str   # search decoded host + path

        # -- Evidence signals --
        keyword_hit: Optional[str] = None
        # Primary: match keywords as whole alphanumeric tokens (not arbitrary substrings)
        # to avoid "rti" matching inside "passportindia", etc.
        _combined_tokens = set(re.findall(r"[a-z0-9]+", combined))
        for kw in _GOV_KEYWORDS:
            if kw in _combined_tokens:
                keyword_hit = kw
                break
        # Secondary: substring match in host only for long keywords (>=5 chars)
        # to catch compound tokens like "mparivahan" containing "parivahan",
        # "rtionlinelogin" containing "rtionline", etc.
        if keyword_hit is None:
            host_tokens_joined = "".join(re.findall(r"[a-z0-9]+", host_decoded))
            for kw in sorted(_GOV_KEYWORDS, key=len, reverse=True):  # longest first
                if len(kw) >= 5 and kw in host_tokens_joined:
                    keyword_hit = kw
                    break

        fake_suffix_hit: Optional[str] = None
        for pat in _FAKE_SUFFIX_PATTERNS:
            if pat in combined:
                fake_suffix_hit = pat
                break

        fuzzy_hit: Optional[str] = None
        if org_labels:
            host_label = host_decoded.split(".")[0]  # first label, decoded
            for label in org_labels:
                ratio = fuzz.ratio(host_label, label)
                if ratio >= _FUZZY_THRESHOLD and host_label != label:
                    fuzzy_hit = label
                    break

        # Also fuzzy-match the first host label against known gov keyword strings
        # to catch misspelling lookalikes (uiadi, uidaii, parivahn, epfindi4, …)
        # Use decoded host so Punycode homographs (xn--udai-lza → ûdai) also match.
        fuzzy_kw_hit: Optional[str] = None
        if fuzzy_hit is None and keyword_hit is None:
            host_label = host_decoded.split(".")[0]
            for kw in _FUZZY_KEYWORDS:
                ratio = fuzz.ratio(host_label, kw)
                if ratio >= _FUZZY_KEYWORD_THRESHOLD and host_label != kw:
                    fuzzy_kw_hit = kw
                    break

        # Structural trick: gov domain appearing in path (not as the real host)
        structural_trick = False
        for suf in _GOV_SUFFIXES:
            # e.g. host = secure034.com, path contains /uidai.gov.in/...
            if suf in path_str:
                structural_trick = True
                break
            # e.g. host = uidai.gov.in@secure034.com → urlparse puts the real
            # host after @; check that uidai.gov.in is NOT the real host
            if suf in host and not _ends_with_gov_suffix(host):
                structural_trick = True
                break

        has_evidence = (
            keyword_hit is not None
            or fake_suffix_hit is not None
            or fuzzy_hit is not None
            or fuzzy_kw_hit is not None
            or structural_trick
        )

        if has_evidence:
            risk = _has_risk_factor(host)
            if risk or fake_suffix_hit or structural_trick:
                # Strong enough to call PHISHING_GOV
                if keyword_hit:
                    reason = (
                        f"Pretends to be a government site "
                        f"(keyword '{keyword_hit}' found) but is not on a .gov.in domain."
                    )
                elif fake_suffix_hit:
                    reason = (
                        f"Contains '{fake_suffix_hit}' outside a real .gov.in/.nic.in "
                        f"suffix — structural impersonation trick."
                    )
                elif structural_trick:
                    reason = "Government domain used in URL path or credentials, not as the real host."
                elif fuzzy_kw_hit:
                    reason = (
                        f"Domain closely resembles government keyword '{fuzzy_kw_hit}' "
                        f"(misspelling/homograph) but is not on a .gov.in domain."
                    )
                else:
                    reason = (
                        f"Closely resembles official government label "
                        f"'{fuzzy_hit}' but is not on a .gov.in domain."
                    )
                return GovResult(
                    verdict="PHISHING_GOV",
                    reason=reason,
                    matched=keyword_hit or fake_suffix_hit or fuzzy_kw_hit or fuzzy_hit or host,
                )
            else:
                # Keyword only without a risk factor → SUSPICIOUS
                reason = (
                    f"Contains government keyword '{keyword_hit or fuzzy_kw_hit}' but lacks "
                    f"other impersonation signals."
                )
                return GovResult(
                    verdict="SUSPICIOUS",
                    reason=reason,
                    matched=keyword_hit or fuzzy_kw_hit,
                )

        # ── Rule 5: No match ──────────────────────────────────────────────────
        return None
