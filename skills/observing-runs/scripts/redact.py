#!/usr/bin/env python3
"""Pattern-based secret redaction — one implementation, two persistence paths.

RM-073 P1-2 (2026-11-06). Before this module, redaction was a value-match on
three environment variables (`run_behavioral_eval._redact`) and `log_run.py`
did no redaction at all. A value-match cannot catch a secret that reaches a
log from model output, a tool result, or a repo file rather than this
process's own environment. The patterns below cover the credential shapes the
consumer sweep found in the fleet (provider keys, Slack bot tokens, GitHub
tokens, Supabase secret keys, AWS access-key IDs) plus PEM private-key blocks.

Consumers:
  - `log_run.py` redacts the free-text `detail` before append.
  - `skills/authoring-skills/scripts/run_behavioral_eval.py` redacts persisted
    event streams, stderr, and (through `log_run`) run-log details.

The environment value-match layer stays as a second line of defence for keys
that have no recognizable shape: callers pass the values they own.

Deliberately NOT redaction of entire records: only free-text fields are
rewritten, so the run-log schema is unchanged (field names, types, enums).
"""
import os
import re

MASK = "***"

# PEM private-key blocks (RSA/EC/OPENSSH/PGP/…), including a truncated block
# that lost its END line. Matched first so the header patterns do not leave a
# half-redacted block behind.
_PEM_BLOCK = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)
_PEM_HEADER = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")

# Ordered most-specific first. Each pattern requires enough body characters to
# avoid matching prose that merely mentions a prefix.
_TOKEN_PATTERNS = (
    # OpenAI / Anthropic / generic `sk-` provider keys (sk-proj-, sk-ant-, …).
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"),
    # Slack tokens: xoxb/xoxp/xoxa/xoxr/xoxs/xoxo.
    re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{8,}"),
    # GitHub fine-grained PAT (checked before the ghp_/gho_ class).
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    # GitHub classic tokens.
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"),
    # Supabase secret keys (new format).
    re.compile(r"\bsb_secret_[A-Za-z0-9_\-]{8,}"),
    # AWS access-key IDs.
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)

# Values shorter than this are not treated as secrets: replacing a 3-character
# env value would corrupt ordinary text without protecting anything.
_MIN_VALUE_LEN = 8

# Environment variables whose VALUES this framework owns. Masked whenever they
# appear in free text, regardless of shape (a provider key may be opaque).
ENV_VALUE_KEYS = (
    "OPENCODE_API_KEY",
    "DEEPSEEK_API_KEY",
    "OPENCODE_GO_API_KEY",
    "OPENCODE_CONFIG_CONTENT",
)


def env_secret_values(environ=None):
    """Values of the framework-owned secret env keys present in `environ`."""
    env = environ if environ is not None else os.environ
    return [env.get(key) for key in ENV_VALUE_KEYS]


def redact(text, values=None):
    """Return `text` with credential shapes and known secret values masked.

    `values` is an optional iterable of secret values this process owns (env
    values). `None`/empty/short values are ignored.
    """
    out = text or ""
    out = _PEM_BLOCK.sub(MASK, out)
    out = _PEM_HEADER.sub(MASK, out)
    for pattern in _TOKEN_PATTERNS:
        out = pattern.sub(MASK, out)
    for value in values or ():
        if value and len(value) >= _MIN_VALUE_LEN and value in out:
            out = out.replace(value, MASK)
    return out


def redaction_patterns():
    """Names of the redaction classes, for tests and documentation parity."""
    return ("pem", "sk-", "xoxb-", "github_pat_", "gh*_", "sb_secret_", "AKIA")
