"""이미지 MIME 매직넘버 판정 — 모바일 업로드 MIME 오류(application/octet-stream 등) 대응.

회귀: 안드로이드 '파일' 피커로 올린 스크린샷의 MIME이 틀리게 와서 비전 API가 거부 → 인식 실패.
바이트 매직넘버로 실제 포맷을 재판정해 업로드 MIME에 의존하지 않게 함.
"""
from core.vision_parser import _image_mime, _to_supported


def test_png_magic():
    assert _image_mime(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8) == "image/png"


def test_jpeg_magic():
    assert _image_mime(b"\xff\xd8\xff\xe0" + b"\x00") == "image/jpeg"


def test_webp_magic():
    assert _image_mime(b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00") == "image/webp"


def test_gif_magic():
    assert _image_mime(b"GIF89a" + b"\x00") == "image/gif"


def test_unknown_returns_empty():
    assert _image_mime(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c") == ""


def test_to_supported_passes_through_correct_mime():
    d = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    assert _to_supported(d) == (d, "image/png")   # 업로드 MIME 무관, 바이트 기준
