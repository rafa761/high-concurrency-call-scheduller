from common.signing import sign_payload, verify_signature


def test_sign_is_deterministic():
    a = sign_payload("secret", b'{"x":1}')
    b = sign_payload("secret", b'{"x":1}')
    assert a == b and len(a) == 64  # sha256 hex


def test_verify_accepts_valid_signature():
    body = b'{"event":"ok"}'
    sig = sign_payload("secret", body)
    assert verify_signature("secret", body, sig)


def test_verify_rejects_tampered_body_or_wrong_secret():
    body = b'{"event":"ok"}'
    sig = sign_payload("secret", body)
    assert not verify_signature("secret", b'{"event":"tampered"}', sig)
    assert not verify_signature("other-secret", body, sig)
    assert not verify_signature("secret", body, "deadbeef")
