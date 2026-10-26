import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.pii.redactor import redact, redact_commit


def test_email_redacted():
    assert redact("contact user@example.com now") == "contact [EMAIL] now"


def test_ipv4_redacted():
    assert "[IPv4]" in redact("server at 192.168.1.100 failed")


def test_sk_token_redacted():
    assert "[API_TOKEN]" in redact("key=sk-ant-api03-ABCDEFGHIJKLMNOPQRST123456")


def test_jwt_redacted():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    assert "[JWT]" in redact(jwt)


def test_plain_text_unchanged():
    text = "Latency spiked on payment service"
    assert redact(text) == text


def test_redact_commit_only_message():
    commit = {"sha": "abc123", "author": "riya", "message": "fix user@example.com auth"}
    result = redact_commit(commit)
    assert result["sha"] == "abc123"
    assert result["author"] == "riya"
    assert "[EMAIL]" in result["message"]
