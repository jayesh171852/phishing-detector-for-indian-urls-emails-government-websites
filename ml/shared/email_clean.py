"""
ml/shared/email_clean.py
------------------------
Email cleaning pipeline used identically at training time and inference time.

The email_dataset.csv text column is already cleaned; this module is the
canonical cleaning function so the API produces the same representation.

clean(subject, body) -> str
  Returns:  subject [SEP] body  truncated to 2,400 chars (first 75 % + last 25 %).
"""
from __future__ import annotations

import re
import html

# ── Regex patterns ────────────────────────────────────────────────────────────
_TAG_RE      = re.compile(r"<[^>]+>")
_URL_RE      = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_EMAIL_RE    = re.compile(r"[\w.+-]+@[\w.-]+\.\w{2,}", re.IGNORECASE)
_LEADING_TAG = re.compile(r"^\s*\[[^\]]{1,40}\]\s*")  # e.g. [name], [forward]
_SPACE_PUNCT = re.compile(r"\s+([,.:;!?])")
_WHITESPACE  = re.compile(r"\s+")

_MAX_CHARS   = 2400
_HEAD_FRAC   = 0.75


def _clean_field(text: str) -> str:
    """Strip HTML, mask URLs/emails, lowercase, normalise whitespace."""
    text = html.unescape(str(text))
    text = _TAG_RE.sub(" ", text)
    text = _URL_RE.sub("[URL]", text)
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = text.lower()
    text = _LEADING_TAG.sub("", text)
    text = _SPACE_PUNCT.sub(r"\1", text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text


def clean(subject: str, body: str) -> str:
    """
    Produce the canonical model input string from raw subject and body.

    Steps (matching the dataset preprocessing):
      1. HTML-unescape and strip tags.
      2. Mask URLs -> [URL], email addresses -> [EMAIL].
      3. Lowercase.
      4. Remove leading list/forward tags like [name].
      5. Remove spaces before punctuation; collapse whitespace.
      6. Concatenate as  "<subject> [SEP] <body>".
      7. Truncate to 2,400 chars: keep first 1,800 + last 600.
    """
    s = _clean_field(subject)
    b = _clean_field(body)
    combined = f"{s} [SEP] {b}" if s else b

    if len(combined) <= _MAX_CHARS:
        return combined

    head_len = int(_MAX_CHARS * _HEAD_FRAC)
    tail_len = _MAX_CHARS - head_len
    return combined[:head_len] + combined[-tail_len:]
