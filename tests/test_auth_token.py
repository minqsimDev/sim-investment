"""세션 복원 서명 토큰(인증 우회 방지) 테스트."""
import importlib
import os

import core.auth_token as at


def _reload_with_secret(secret):
    os.environ["APP_SECRET"] = secret
    at._secret_cache = None


def test_roundtrip():
    _reload_with_secret("s1")
    for u in ["minqsim", "Kepco", "한글유저", "a.b@c", "x_y-z"]:
        assert at.verify_token(at.make_token(u)) == u


def test_plaintext_username_rejected():
    # 과거 우회: ?_user=<평문 username> 은 이제 무효여야 한다
    _reload_with_secret("s1")
    for u in ["minqsim", "Kepco", "admin"]:
        assert at.verify_token(u) is None


def test_tampered_or_garbage_rejected():
    _reload_with_secret("s1")
    assert at.verify_token("") is None
    assert at.verify_token("!!!not-base64!!!") is None
    t = at.make_token("minqsim")
    assert at.verify_token(t[:-2] + "zz") is None       # 시그 변조
    assert at.verify_token(t.upper()) != "minqsim"      # 케이스 변조


def test_different_secret_rejected():
    _reload_with_secret("s1")
    t = at.make_token("minqsim")
    _reload_with_secret("s2")
    assert at.verify_token(t) is None


def test_user_param_format():
    _reload_with_secret("s1")
    p = at.user_param("minqsim")
    assert p.startswith("_user=")
    assert at.verify_token(p.split("=", 1)[1]) == "minqsim"
    assert at.user_param("") == ""
