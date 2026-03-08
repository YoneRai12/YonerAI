from src.skills.remotion_create_video.tool import _validate_public_image_url


def test_validate_public_image_url_rejects_file_scheme():
    ok, err = _validate_public_image_url("file:///etc/passwd")
    assert not ok
    assert "http/https" in err


def test_validate_public_image_url_rejects_localhost():
    ok, err = _validate_public_image_url("http://localhost/secret.png")
    assert not ok
    assert "localhost" in err


def test_validate_public_image_url_rejects_private_ip_literal():
    ok, err = _validate_public_image_url("http://127.0.0.1:8080/secret.png")
    assert not ok
    assert "プライベート/ローカルIP" in err


def test_validate_public_image_url_allows_public_https():
    ok, err = _validate_public_image_url("https://example.com/image.png")
    assert ok
    assert err == ""
