from collections.abc import Callable

import pytest
from botocore.exceptions import ClientError

from app.services import object_storage


def test_upload_to_s3_uses_localstack_endpoint_and_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_names: list[str] = []
    client_options: dict[str, object] = {}
    put_object_args: dict[str, object] = {}

    class FakeS3Client:
        def put_object(self, **kwargs: object) -> None:
            put_object_args.update(kwargs)

    def fake_client(service_name: str, **kwargs: object) -> FakeS3Client:
        service_names.append(service_name)
        client_options.update(kwargs)
        return FakeS3Client()

    monkeypatch.setenv("AWS_ENDPOINT_URL_S3", "http://localstack:4566")
    monkeypatch.setenv("S3_BATCH_BUCKET", "test-batches")
    monkeypatch.setattr(object_storage.boto3, "client", fake_client)

    result = object_storage._upload_to_s3(b"sample_id\nA-1\n", "batches/test.csv")

    assert result == ("test-batches", "batches/test.csv")
    assert service_names == ["s3"]
    assert client_options["endpoint_url"] == "http://localstack:4566"
    assert client_options["aws_access_key_id"] == "test"
    assert put_object_args == {
        "Bucket": "test-batches",
        "Key": "batches/test.csv",
        "Body": b"sample_id\nA-1\n",
        "ContentType": "text/csv",
        "ServerSideEncryption": "AES256",
    }


def test_upload_to_s3_uses_ambient_aws_credentials_outside_localstack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_options: dict[str, object] = {}

    class FakeS3Client:
        def put_object(self, **kwargs: object) -> None:
            pass

    def fake_client(service: str, **kwargs: object) -> FakeS3Client:
        captured_options.update(kwargs)
        return FakeS3Client()

    monkeypatch.delenv("AWS_ENDPOINT_URL_S3", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.setattr(object_storage.boto3, "client", fake_client)

    object_storage._upload_to_s3(b"csv", "batch.csv")

    assert "aws_access_key_id" not in captured_options
    assert "aws_secret_access_key" not in captured_options


def test_archive_batch_upload_wraps_s3_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_put(*args: object, **kwargs: object) -> None:
        raise ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}},
            "PutObject",
        )

    class FailingClient:
        put_object: Callable[..., None] = fail_put

    monkeypatch.setattr(object_storage.boto3, "client", lambda *args, **kwargs: FailingClient())

    with pytest.raises(RuntimeError, match="Unable to store"):
        import asyncio

        asyncio.run(object_storage.archive_batch_upload(b"csv", "batch.csv"))
