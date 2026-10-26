import re

_PATTERNS = [
    (re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL]'),
    (re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'), '[IPv4]'),
    (re.compile(r'\bsk-[A-Za-z0-9\-_]{20,}\b'), '[API_TOKEN]'),
    (re.compile(r'\bghp_[A-Za-z0-9]{36}\b'), '[GH_TOKEN]'),
    (re.compile(r'\beyJ[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_=]*\b'), '[JWT]'),
    # generic long tokens last — catches leftovers
    (re.compile(r'\b[A-Za-z0-9\-_]{40,}\b'), '[TOKEN]'),
]


def redact(text: str) -> str:
    for pattern, placeholder in _PATTERNS:
        text = pattern.sub(placeholder, text)
    return text


def redact_commit(commit: dict) -> dict:
    return {**commit, "message": redact(commit.get("message", ""))}


if __name__ == "__main__":
    cases = [
        ("user@example.com", "[EMAIL]"),
        ("192.168.1.1", "[IPv4]"),
        ("sk-ant-api03-abcdefghijklmnopqrst", "[API_TOKEN]"),
    ]
    for text, expected in cases:
        result = redact(text)
        assert expected in result, f"FAIL: redact({text!r}) = {result!r}"
    print("redactor self-check passed")
