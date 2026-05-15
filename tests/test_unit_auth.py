import pytest

from app.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("hunter22-correct-horse")
    assert h != "hunter22-correct-horse"
    assert verify_password("hunter22-correct-horse", h)
    assert not verify_password("wrong", h)


def test_verify_password_handles_bad_hash():
    assert not verify_password("anything", "not-a-valid-bcrypt-hash")


def test_jwt_roundtrip():
    token = create_access_token(subject="alice")
    payload = decode_access_token(token)
    assert payload["sub"] == "alice"
    assert "exp" in payload and "iat" in payload


def test_jwt_invalid_token_rejected():
    import jwt as pyjwt

    with pytest.raises(pyjwt.PyJWTError):
        decode_access_token("definitely.not.a.jwt")
