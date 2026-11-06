"""Offline tests for Gnani response parsing. No network."""

import pytest

from src.gnani import check_wav_bytes, parse_embedding_response
from src.retry import RequestError

EMB = {"embedding": "AAAB", "shape": [1, 768], "dtype": "torch.bfloat16"}


def test_embedding_wrapped_form_from_docs():
    body = {"success": True, "message": "ok", "data": {"voice_clone_embedding": EMB}}
    assert parse_embedding_response(body) == EMB


def test_embedding_unwrapped_form_from_brief():
    assert parse_embedding_response(dict(EMB)) == EMB


def test_embedding_unknown_shape_raises():
    with pytest.raises(RequestError):
        parse_embedding_response({"success": True, "data": {"something_else": 1}})


def test_wav_bytes_accepted():
    fake = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 20
    assert check_wav_bytes(fake, "audio/wav") == fake


def test_json_error_with_200_rejected():
    with pytest.raises(RequestError):
        check_wav_bytes(b'{"success": false, "message": "bad"}', "application/json")
