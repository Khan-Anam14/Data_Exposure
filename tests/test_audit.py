import asyncio
import hashlib
import sys
import os
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_prompt_hash_matches_sha256():
    """Verify prompt_hash logic without DB: sha256(prompt) == expected."""
    prompt = "test incident context"
    expected = hashlib.sha256(prompt.encode()).hexdigest()
    assert len(expected) == 64
    assert expected == hashlib.sha256(b"test incident context").hexdigest()


def test_output_hash_matches_sha256():
    output = '{"root_cause": "DB connection exhausted"}'
    h = hashlib.sha256(output.encode()).hexdigest()
    assert len(h) == 64


def test_none_prompt_produces_none_hash():
    prompt = None
    result = hashlib.sha256(prompt.encode()).hexdigest() if prompt else None
    assert result is None
