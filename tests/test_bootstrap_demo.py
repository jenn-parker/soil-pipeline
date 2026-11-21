from __future__ import annotations

from pathlib import Path

import pytest

from scripts import bootstrap_demo


class FakeResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.is_success = 200 <= status_code < 300

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        if not self.is_success:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeClient:
    def __init__(self, samples: list[dict[str, str]]) -> None:
        self.samples = samples
        self.post_calls: list[dict[str, object]] = []

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        assert url.endswith("/api/v1/soil-samples/mine")
        assert kwargs["headers"] == {"Authorization": "Bearer local-demo-key"}
        return FakeResponse(self.samples)

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        files = kwargs.get("files")
        if isinstance(files, dict) and "file" in files:
            upload = files["file"]
            kwargs["file_body"] = upload[1].read()
        self.post_calls.append({"url": url, **kwargs})
        return FakeResponse({"id": 12, "status": "completed"}, status_code=201)


def test_bootstrap_skips_owned_batch_when_all_demo_samples_exist() -> None:
    client = FakeClient([
        {"sample_id": "demo-owned-ames"},
        {"sample_id": "demo-owned-boone"},
    ])

    result = bootstrap_demo._upload_owned_batch(
        client,
        "http://localhost:8000",
        "local-demo-key",
    )

    assert result == "owned batch already present"
    assert client.post_calls == []


def test_bootstrap_uploads_missing_owned_batch_through_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owned_batch = tmp_path / "demo-owned-batch.csv"
    owned_batch.write_text("sample_id\ndemo-owned-ames\n", encoding="utf-8")
    monkeypatch.setattr(bootstrap_demo, "OWNED_BATCH", owned_batch)
    client = FakeClient([])

    result = bootstrap_demo._upload_owned_batch(
        client,
        "http://localhost:8000",
        "local-demo-key",
    )

    assert result == "created batch 12 (completed)"
    assert len(client.post_calls) == 1
    call = client.post_calls[0]
    assert call["url"] == "http://localhost:8000/api/v1/soil-batches"
    assert call["headers"] == {"Authorization": "Bearer local-demo-key"}
    uploaded_file = call["files"]["file"]  # type: ignore[index]
    assert uploaded_file[0] == "demo-owned-batch.csv"
    assert call["file_body"] == b"sample_id\ndemo-owned-ames\n"


def test_bootstrap_reports_invalid_local_api_key() -> None:
    client = FakeClient([])

    def unauthorized_get(url: str, **kwargs: object) -> FakeResponse:
        return FakeResponse({"detail": "Invalid bearer token"}, status_code=401)

    client.get = unauthorized_get  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="rejected the demo key"):
        bootstrap_demo._upload_owned_batch(
            client,
            "http://localhost:8000",
            "local-demo-key",
        )
