import asyncio
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from botocore.config import Config


def _upload_to_s3(contents: bytes, object_key: str) -> tuple[str, str]:
    bucket = os.getenv("S3_BATCH_BUCKET", "soil-pipeline-batches")
    endpoint_url = os.getenv("AWS_ENDPOINT_URL_S3") or None
    client_options = {
        "endpoint_url": endpoint_url,
        "region_name": os.getenv("AWS_REGION", "us-east-1"),
        "config": Config(s3={"addressing_style": "path"} if endpoint_url else {}),
    }
    if endpoint_url:
        client_options["aws_access_key_id"] = os.getenv("AWS_ACCESS_KEY_ID", "test")
        client_options["aws_secret_access_key"] = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
    elif os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_SECRET_ACCESS_KEY"):
        client_options["aws_access_key_id"] = os.getenv("AWS_ACCESS_KEY_ID")
        client_options["aws_secret_access_key"] = os.getenv("AWS_SECRET_ACCESS_KEY")
    client = boto3.client(
        "s3",
        **client_options,
    )
    client.put_object(
        Bucket=bucket,
        Key=object_key,
        Body=contents,
        ContentType="text/csv",
        ServerSideEncryption="AES256",
    )
    return bucket, object_key


async def archive_batch_upload(
    contents: bytes,
    object_key: str,
) -> tuple[str, str]:
    """Archive the original CSV in S3 without blocking the async request loop."""
    try:
        return await asyncio.to_thread(_upload_to_s3, contents, object_key)
    except (BotoCoreError, ClientError, OSError) as exc:
        raise RuntimeError("Unable to store the uploaded batch file") from exc
