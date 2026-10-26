import os
import re
import math
import pandas as pd
from urllib.parse import urlparse
import tldextract
from collections import Counter

# Load DATA_DIR from environment (same default as config)
DATA_DIR = os.getenv('DATA_DIR', r'C:\\Users\\jayes\\OneDrive\\Desktop\\pbl sem 5\\new')

# Keyword list for counting in URLs
KEYWORDS = [
    "login", "verify", "update", "secure", "account", "bank",
    "kyc", "otp", "refund", "pay"
]

# List of known URL shortener domains (top common ones)
SHORTENER_DOMAINS = {
    "bit.ly", "goo.gl", "t.co", "tinyurl.com", "ow.ly",
    "bit.do", "buff.ly", "adf.ly", "cutt.ly", "tiny.cc"
}

def shannon_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not s:
        return 0.0
    counts = Counter(s)
    probs = [c / len(s) for c in counts.values()]
    return -sum(p * math.log2(p) for p in probs)

def longest_alnum_token(s: str) -> int:
    """Length of the longest continuous alphanumeric token in the string."""
    tokens = re.findall(r"[A-Za-z0-9]+", s)
    return max((len(tok) for tok in tokens), default=0)

def vowel_ratio(host: str) -> float:
    """Proportion of vowel characters in the host string."""
    if not host:
        return 0.0
    vowels = sum(1 for ch in host.lower() if ch in "aeiou")
    return vowels / len(host)

def has_ip(host: str) -> bool:
    """Detect if the host part is an IPv4 address."""
    return bool(re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", host))

def keyword_count(url_norm: str) -> int:
    """Count how many of the defined keywords appear in the URL (case‑insensitive)."""
    low = url_norm.lower()
    return sum(1 for kw in KEYWORDS if kw in low)

def is_shortener(domain: str) -> bool:
    return domain.lower() in SHORTENER_DOMAINS

def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    """Given a DataFrame with a ``url_norm`` column, return a DataFrame of engineered features.
    The function does **not** perform any network calls; all operations are local string parsing.
    """
    features = {}
    # Pre‑allocate lists for each feature
    url_lengths = []
    host_lengths = []
    path_lengths = []
    query_lengths = []
    num_dots = []
    num_hyphens = []
    num_digits = []
    digit_ratios = []
    num_special = []
    num_subdomains = []
    path_depths = []
    host_entropies = []
    path_entropies = []
    longest_token = []
    vowel_ratios = []
    ip_flags = []
    at_flags = []
    punycode_flags = []
    kw_counts = []
    shortener_flags = []
    tlds = []

    for url in df["url_norm"]:
        # Basic lengths
        url_lengths.append(len(url))
        # Parse using a dummy scheme so urlparse can split host/path/query
        parsed = urlparse("http://" + url)
        host = parsed.hostname or ""
        path = parsed.path or ""
        query = parsed.query or ""
        host_lengths.append(len(host))
        path_lengths.append(len(path))
        query_lengths.append(len(query))
        # Character counts
        num_dots.append(host.count('.'))
        num_hyphens.append(host.count('-'))
        digits = sum(ch.isdigit() for ch in url)
        num_digits.append(digits)
        digit_ratios.append(digits / len(url) if url else 0.0)
        # Special characters (non‑alphanumeric and not typical URL symbols)
        special = sum(1 for ch in url if not ch.isalnum() and ch not in "-._~:/?&#%")
        num_special.append(special)
        # Subdomains via tldextract
        ext = tldextract.extract(url)
        sub = ext.subdomain
        num_subdomains.append(len(sub.split('.')) if sub else 0)
        # Path depth (segments count)
        depth = len([seg for seg in path.split('/') if seg])
        path_depths.append(depth)
        # Entropies
        host_entropies.append(shannon_entropy(host))
        path_entropies.append(shannon_entropy(path))
        # Longest alphanumeric token
        longest_token.append(longest_alnum_token(url))
        # Vowel ratio in host
        vowel_ratios.append(vowel_ratio(host))
        # Flags
        ip_flags.append(has_ip(host))
        at_flags.append('@' in url)
        punycode_flags.append('xn--' in host)
        # Keyword count
        kw_counts.append(keyword_count(url))
        # Shortener detection
        shortener_flags.append(is_shortener(ext.domain + '.' + ext.suffix))
        # TLD (categorical)
        tlds.append(ext.suffix.lower() if ext.suffix else '')

    features["url_length"] = url_lengths
    features["host_length"] = host_lengths
    features["path_length"] = path_lengths
    features["query_length"] = query_lengths
    features["num_dots"] = num_dots
    features["num_hyphens"] = num_hyphens
    features["num_digits"] = num_digits
    features["digit_ratio"] = digit_ratios
    features["num_special_chars"] = num_special
    features["num_subdomains"] = num_subdomains
    features["path_depth"] = path_depths
    features["host_entropy"] = host_entropies
    features["path_entropy"] = path_entropies
    features["longest_token_len"] = longest_token
    features["vowel_ratio_host"] = vowel_ratios
    features["has_ip_host"] = ip_flags
    features["has_at_symbol"] = at_flags
    features["has_punycode"] = punycode_flags
    features["keyword_count"] = kw_counts
    features["is_url_shortener"] = shortener_flags
    features["tld"] = tlds

    return pd.DataFrame(features)

# When executed as a script, run a quick sanity test on 1 000 rows.
if __name__ == "__main__":
    import time
    train_path = os.path.join(DATA_DIR, "train_urls.csv")
    df = pd.read_csv(train_path, usecols=["url_norm"]).head(1000)
    start = time.time()
    feats = extract_features(df)
    elapsed = time.time() - start
    print("Feature columns:", ", ".join(feats.columns))
    print(f"Extracted {len(df)} rows in {elapsed:.2f}s")
