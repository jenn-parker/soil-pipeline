"""Bootstrap the repeatable local portfolio demo.

This command is intentionally explicit rather than part of application startup.
It seeds reference records directly through PostgreSQL and creates demo-owned
records through the authenticated HTTP upload path.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_SQL = ROOT / "scripts" / "seed_ssurgo_demo.sql"
OWNED_BATCH = ROOT / "data" / "seed" / "demo-owned-batch.csv"
DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_API_KEY = "local-demo-key"
DEMO_SAMPLE_IDS = {"demo-owned-ames", "demo-owned-boone"}


def _run_reference_seed() -> None:
    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        "db",
        "psql",
        "-U",
        "earth_user",
        "-d",
        "soil_db",
    ]
    try:
        subprocess.run(
            command,
            cwd=ROOT,
            input=REFERENCE_SQL.read_bytes(),
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Docker Compose is required to bootstrap the local demo") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("The SSURGO reference seed failed") from exc


def _wait_for_api(client: httpx.Client, api_url: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            response = client.get(f"{api_url}/health/ready")
            if response.is_success:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError(f"The API did not become ready at {api_url}")


def _upload_owned_batch(client: httpx.Client, api_url: str, api_key: str) -> str:
    headers = {"Authorization": f"Bearer {api_key}"}
    samples_response = client.get(
        f"{api_url}/api/v1/soil-samples/mine",
        headers=headers,
    )
    if samples_response.status_code == 401:
        raise RuntimeError(
            "The local API rejected the demo key; run the bootstrap in API-key mode "
            "or set DEMO_API_KEY to a configured local key"
        )
    samples_response.raise_for_status()
    existing_ids = {
        str(sample.get("sample_id"))
        for sample in samples_response.json()
        if isinstance(sample, dict)
    }
    if DEMO_SAMPLE_IDS <= existing_ids:
        return "owned batch already present"

    with OWNED_BATCH.open("rb") as batch_file:
        response = client.post(
            f"{api_url}/api/v1/soil-batches",
            headers=headers,
            files={"file": (OWNED_BATCH.name, batch_file, "text/csv")},
        )
    if response.status_code == 409:
        raise RuntimeError(
            "The demo batch conflicts with existing sample data; remove the local "
            "demo data or choose different IDs before retrying"
        )
    response.raise_for_status()
    payload = response.json()
    return f"created batch {payload.get('id', '<unknown>')} ({payload.get('status', 'unknown')})"


def main() -> int:
    api_url = os.getenv("DEMO_API_URL", DEFAULT_API_URL).rstrip("/")
    api_key = os.getenv("DEMO_API_KEY", DEFAULT_API_KEY)
    if not api_url.startswith(("http://localhost", "http://127.0.0.1")):
        raise RuntimeError("DEMO_API_URL must point to a local HTTP service")
    if not REFERENCE_SQL.is_file() or not OWNED_BATCH.is_file():
        raise RuntimeError("The demo seed assets are missing")

    print("Seeding SSURGO reference records...")
    _run_reference_seed()
    with httpx.Client(timeout=10.0) as client:
        print("Waiting for the API...")
        _wait_for_api(client, api_url)
        print(_upload_owned_batch(client, api_url, api_key))
    print("Local demo bootstrap complete.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, httpx.HTTPError) as exc:
        print(f"Demo bootstrap failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
