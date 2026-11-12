from isic.core.storages.minio import PlaceholderMinioStorage, S3ProxyMinioStorage


def test_development_storages_keep_their_behavior_for_unsigned_urls(mocker):
    placeholder = PlaceholderMinioStorage()
    assert placeholder.unsigned_url("images/a.jpg") == placeholder.url("images/a.jpg")
    assert placeholder.unsigned_url("images/a.jpg").startswith("https://picsum.photos/")
    assert placeholder.unsigned_url("images/a.png").endswith("/images/a.png")

    proxy = S3ProxyMinioStorage(upstream_bucket_name="upstream")
    ensure_exists = mocker.patch.object(proxy, "_ensure_exists")
    url = proxy.unsigned_url("images/a.jpg")
    ensure_exists.assert_called_once_with("images/a.jpg")
    assert url.endswith("/images/a.jpg")
    assert "X-Amz-Signature" not in url
