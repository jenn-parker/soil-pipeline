import asyncio
import logging
import os
from time import perf_counter
from threading import Lock

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from botocore.config import Config

logger = logging.getLogger(__name__)

_s3_client = None
_s3_client_signature = None
_s3_client_lock = Lock()


def _get_s3_client():
    global _s3_client, _s3_client_signature
    endpoint_url = os.getenv("AWS_ENDPOINT_URL_S3") or None
    region_name = os.getenv("AWS_REGION", "us-east-1")
    access_key_id = os.getenv("AWS_ACCESS_KEY_ID", "test" if endpoint_url else None)
    secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", "test" if endpoint_url else None)
    signature = (endpoint_url, region_name, access_key_id, secret_access_key, boto3.client)
    if _s3_client is None or signature != _s3_client_signature:
        with _s3_client_lock:
            if _s3_client is None or signature != _s3_client_signature:
                client_options = {
                    "endpoint_url": endpoint_url,
                    "region_name": region_name,
                    "config": Config(s3={"addressing_style": "path"} if endpoint_url else {}),
                }
                if endpoint_url:
                    client_options["aws_access_key_id"] = access_key_id
                    client_options["aws_secret_access_key"] = secret_access_key
                elif access_key_id or secret_access_key:
                    client_options["aws_access_key_id"] = access_key_id
                    client_options["aws_secret_access_key"] = secret_access_key
                _s3_client = boto3.client("s3", **client_options)
                _s3_client_signature = signature
    return _s3_client


def _upload_to_s3(contents: bytes, object_key: str) -> tuple[str, str]:
    bucket = os.getenv("S3_BATCH_BUCKET", "soil-pipeline-batches")
    _get_s3_client().put_object(
        Bucket=bucket,
        Key=object_key,
        Body=contents,
        ContentType="text/csv",
        ServerSideEncryption="AES256",
    )
    return bucket, object_key


def _delete_from_s3(bucket: str, object_key: str) -> None:
    _get_s3_client().delete_object(Bucket=bucket, Key=object_key)


async def archive_batch_upload(
    contents: bytes,
    object_key: str,
) -> tuple[str, str]:
    """Archive the original CSV in S3 without blocking the async request loop."""
    started_at = perf_counter()
    bucket = os.getenv("S3_BATCH_BUCKET", "soil-pipeline-batches")
    try:
        result = await asyncio.to_thread(_upload_to_s3, contents, object_key)
    except (BotoCoreError, ClientError, OSError) as exc:
        logger.exception(
            "S3 batch archive failed",
            extra={
                "s3_bucket": bucket,
                "upload_size_bytes": len(contents),
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            },
        )
        raise RuntimeError("Unable to store the uploaded batch file") from exc
    logger.info(
        "S3 batch archive completed",
        extra={
            "s3_bucket": result[0],
            "upload_size_bytes": len(contents),
            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
        },
    )
    return result


async def discard_batch_upload(bucket: str, object_key: str) -> None:
    """Best-effort compensation for an archive whose database transaction failed."""
    try:
        await asyncio.to_thread(_delete_from_s3, bucket, object_key)
    except (BotoCoreError, ClientError, OSError) as exc:
        logger.exception(
            "S3 batch archive cleanup failed",
            extra={"s3_bucket": bucket, "object_key": object_key},
        )
        raise RuntimeError("Unable to clean up the uploaded batch file") from exc
