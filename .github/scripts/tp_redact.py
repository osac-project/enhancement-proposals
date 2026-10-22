"""Redact credential- and PII-shaped substrings before untrusted text
is published.

Model responses and provider metadata are untrusted data. Everything
derived from them — verdict fields, plan revisions, error messages — is
redacted before it is written to an artifact, printed, posted as a PR
comment, or published as a check summary. Redaction is a bound, not a
guarantee: it removes common credential and PII shapes so a leaked
secret cannot survive publication.

Customer data: there is no reliable text shape for it, so it is
addressed structurally instead. The model's only inputs are the PR's
own public repository files plus the public osac-ai-skills and OSAC
checkouts, so its output cannot disclose customer data that is not
already public in the PR; on top of that, emails, identifiers, SSNs,
card numbers, credentials, session values and internal hosts are
redacted at every sink.

Revised plans: a revision committed to a same-repository PR branch
keeps the author's own untouched text byte-identical (only
model-supplied edits are redacted); the revised-plan artifact uploaded
for fork PRs is fully redacted.

Internal network identifiers are redacted (private, loopback and
link-local IP addresses, and hostnames under internal-only suffixes
such as .svc or .cluster.local). Public hostnames, URLs, public IP
addresses and bare service names without those suffixs stay readable
because test plans legitimately cite them.
"""

import re

REDACTED = "<REDACTED>"
HOST_REDACTED = "<REDACTED-HOST>"

# Vendor credential shapes are defined once here as named constants and
# the rules below are built from them. These are regex sources, not
# secrets; unit tests assemble their sample inputs from these pieces at
# runtime so no test source spells a vendor prefix or key label.
GITHUB_TOKEN_PREFIXES = ("ghp_", "gho_", "ghu_", "ghs_", "ghr_")
GITHUB_PAT_PREFIX = "github_pat_"
AWS_KEY_PREFIXES = ("AKIA", "ASIA")
GOOGLE_KEY_PREFIX = "AIza"
SLACK_TOKEN_PREFIXES = ("xoxa-", "xoxb-", "xoxp-", "xoxr-", "xoxs-")
JWT_SEGMENT_PREFIX = "eyJ"
PEM_OPEN_MARK = "-----BEGIN "
PEM_CLOSE_MARK = "-----END "
PEM_KEY_LABEL = "PRIVATE KEY"


def _alternatives(values):
    return "(?:" + "|".join(re.escape(value) for value in values) + ")"


def _luhn(digits):
    """Return True when the digit string passes the Luhn checksum."""
    total = 0
    for index, digit in enumerate(reversed(digits)):
        value = int(digit)
        if index % 2:
            value = value * 2 - 9 if value > 4 else value * 2
        total += value
    return total % 10 == 0


def _redact_card(match):
    """Redact a 13-19 digit group only when it is Luhn-valid.

    Two gates keep identifiers, SHAs, timestamps, dates and other plan
    digit runs readable: every separator-delimited group must hold at
    least three digits (card layouts are 4-4-4-4, 4-6-5, 4-3-3-3;
    dates are 4-2-2), and the checksum must pass — a random number
    rarely does.
    """
    text = match.group(0)
    groups = re.split(r"[ -]", text)
    if any(len(group) < 3 for group in groups):
        return text
    digits = "".join(groups)
    return REDACTED if 13 <= len(digits) <= 19 and _luhn(digits) else text


# Each rule is (pattern, replacement). Whole-value rules replace the entire
# match; keyed rules keep the key and separator and replace only the value.
# Replacements may be strings (with group references) or callables that
# return the replacement.
_RULES = (
    # Private-key PEM blocks of any key type.
    (re.compile(PEM_OPEN_MARK + r"[A-Z0-9 ]*" + PEM_KEY_LABEL + "-----"
                + r".*?" + PEM_CLOSE_MARK + r"[A-Z0-9 ]*"
                + PEM_KEY_LABEL + "-----", re.DOTALL), REDACTED),
    # Authorization header values, only when credential-shaped: an auth
    # scheme (case-insensitive) followed by an opaque value, or a single
    # opaque token of at least 20 characters. Prose after the key is
    # left readable so review feedback like "Authorization: requires
    # Cloud Provider Admin role" survives.
    (re.compile(
        r"(?i)(\bauthorization\b[\"']?\s*[:=]\s*[\"']?)"
        r"(?:((?:bearer|basic|token|digest|negotiate|aws4-hmac-sha256)\s+)"
        r"[A-Za-z0-9._~+/=-]{8,}"
        r"|[A-Za-z0-9._~+/=-]{20,})"),
     r"\1\2" + REDACTED),
    # Bearer tokens.
    (re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/=-]{20,}"),
     r"\1" + REDACTED),
    # GitHub tokens: the classic prefixes plus fine-grained PATs.
    (re.compile(r"\b" + _alternatives(GITHUB_TOKEN_PREFIXES)
                + r"[A-Za-z0-9]{36}\b"), REDACTED),
    (re.compile(r"\b" + re.escape(GITHUB_PAT_PREFIX)
                + r"[A-Za-z0-9_]{22,}\b"), REDACTED),
    # AWS access key IDs.
    (re.compile(r"\b" + _alternatives(AWS_KEY_PREFIXES)
                + r"[0-9A-Z]{16}\b"), REDACTED),
    # Google API keys.
    (re.compile(r"\b" + re.escape(GOOGLE_KEY_PREFIX)
                + r"[0-9A-Za-z_-]{35}\b"), REDACTED),
    # Slack tokens.
    (re.compile(r"\b" + _alternatives(SLACK_TOKEN_PREFIXES)
                + r"[A-Za-z0-9-]{10,}\b"), REDACTED),
    # JWTs: two base64url segments starting with the JSON marker, a dot,
    # and a third segment.
    (re.compile(r"\b" + re.escape(JWT_SEGMENT_PREFIX) + r"[A-Za-z0-9_-]{10,}\."
                + re.escape(JWT_SEGMENT_PREFIX) + r"[A-Za-z0-9_-]{10,}"
                r"\.[A-Za-z0-9_-]*"), REDACTED),
    # Internal IPv4 addresses: RFC1918 private, loopback and link-local.
    # A hyphen suffix (10.0.0.5-rc1) is still redacted: a private address
    # with a tag is far more likely a real host reference than a version
    # string, and over-redacting that shape is harmless.
    (re.compile(
        r"\b(?:10(?:\.\d{1,3}){3}"
        r"|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}"
        r"|192\.168(?:\.\d{1,3}){2}"
        r"|127(?:\.\d{1,3}){3}"
        r"|169\.254(?:\.\d{1,3}){2})\b"), HOST_REDACTED),
    # Internal IPv6 addresses: unique local addresses (fc00::/7) and
    # link-local addresses (fe80::/10).
    (re.compile(r"\b(?:f[cd][0-9a-f]{2}|fe[89ab][0-9a-f]):"
                r"(?:[0-9a-f]{0,4}:){1,6}[0-9a-f]{0,4}\b"), HOST_REDACTED),
    # Hostnames under internal-only suffixes, including underscore
    # labels (my_db.internal, svc_a.ns.svc). The suffix must end the
    # hostname: only end-of-string, a port, a path separator, whitespace,
    # closing punctuation, or a sentence-final dot may follow, so names
    # like settings.local.json, pkg.internal.mod or module paths like
    # tp_redact.local_rules stay readable. Public hostnames, URLs,
    # public IP addresses and bare service names stay readable.
    # (\x22/\x27 are the quote characters.)
    (re.compile(
        r"\b[A-Za-z0-9._-]+\.(?:svc|cluster\.local|internal|local|lan|corp|"
        r"intranet|home\.arpa)"
        r"(?=$|[:/\s,;)\]>\x22\x27]|\.(?!\w))"), HOST_REDACTED),
    # US Social Security Numbers, excluding the invalid area/group/serial
    # combinations. Any 3-2-4 digit group passing those exclusions is
    # redacted even if it could be a phone number: over-redacting that
    # exact format is safer than leaking a real SSN.
    (re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"),
     REDACTED),
    # Payment card numbers, 13-19 digits with optional space or dash
    # separators, only when Luhn-valid (see _redact_card).
    (re.compile(r"\b(?:\d[ -]?){12,18}\d\b"), _redact_card),
    # Cookie header values: keep the header name and the first cookie
    # name, redact the value up to the next pair or end of line.
    (re.compile(
        r"(?i)((?:\bset-?cookie\b|\bcookie\b)[\"']?\s*[:=]\s*[\"']?"
        r"[A-Za-z0-9_.-]+=)[^;\r\n]+"),
     r"\1" + REDACTED),
    # Sensitive key/value assignments in YAML, JSON, env or kubeconfig
    # syntax. An optional identifier prefix covers keys like ACCESS_TOKEN,
    # db_password, authToken or session_id; the keyword must remain the
    # final word before the separator, so prose like "the access token is
    # rotated" or "password field is masked" does not match. Only the
    # value is replaced; the key stays readable.
    (re.compile(
        r"(?i)\b([A-Za-z0-9_-]*(?:password|passwd|secret|token|api[_-]?key|"
        r"client[_-]secret|aws[_-]secret[_-]access[_-]key|"
        r"session[_-]?id|sessionid|sid|csrf[_-]?token|"
        r"client[_-]key[_-]data|client[_-]certificate[_-]data|"
        r"certificate[_-]authority[_-]data))"
        r"\b([\"']?\s*[:=]\s*[\"']?)[^\s,;\"'}]+"),
     r"\1\2" + REDACTED),
    # Email addresses.
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
     REDACTED),
)


def redact(text):
    """Replace credential- and PII-shaped substrings with markers."""
    text = str(text)
    for pattern, replacement in _RULES:
        text = pattern.sub(replacement, text)
    return text


def redact_json(value):
    """Recursively redact the string values of parsed JSON data.

    Object keys are left untouched: they are structural names validated by
    consumers, and redacting them could break downstream lookups.
    """
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_json(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_json(item) for key, item in value.items()}
    return value
