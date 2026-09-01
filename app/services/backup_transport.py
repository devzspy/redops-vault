"""Uploads a built backup archive to a BackupDestination's external
provider. One function per provider, dispatched from upload(). Cloud SDKs
are imported lazily inside each function so the app can start even if a
particular provider's package is missing.
"""

from datetime import datetime, timezone

from app.models.backup import (
    PROVIDER_AWS,
    PROVIDER_AZURE,
    PROVIDER_GCP,
    PROVIDER_OCI,
    PROVIDER_SELF_HOSTED,
    STORAGE_TYPE_OBJECT_STORAGE,
)
from app.services import crypto_service


class BackupTransportError(Exception):
    """Raised when a backup destination can't be reached or is misconfigured."""


def upload(destination, local_path, remote_filename):
    secret = crypto_service.decrypt_field(destination.secret_encrypted)

    if destination.provider == PROVIDER_AWS:
        _upload_s3(destination, local_path, remote_filename, secret, endpoint_url=destination.endpoint_url or None)
    elif destination.provider == PROVIDER_OCI:
        if not destination.endpoint_url:
            raise BackupTransportError(
                "OCI destinations need the S3-compatible endpoint URL "
                "(https://<namespace>.compat.objectstorage.<region>.oraclecloud.com) in Endpoint URL."
            )
        _upload_s3(destination, local_path, remote_filename, secret, endpoint_url=destination.endpoint_url)
    elif destination.provider == PROVIDER_AZURE:
        _upload_azure(destination, local_path, remote_filename, secret)
    elif destination.provider == PROVIDER_GCP:
        _upload_gcp(destination, local_path, remote_filename, secret)
    elif destination.provider == PROVIDER_SELF_HOSTED:
        if destination.storage_type == STORAGE_TYPE_OBJECT_STORAGE:
            if not destination.endpoint_url:
                raise BackupTransportError("Self-hosted object storage needs an S3-compatible Endpoint URL.")
            _upload_s3(destination, local_path, remote_filename, secret, endpoint_url=destination.endpoint_url)
        else:
            _upload_sftp(destination, local_path, remote_filename, secret)
    else:
        raise BackupTransportError(
            f"Automatic execution isn't supported for provider '{destination.provider}'. "
            "Use 'Log Success' / 'Log Failure' to record runs performed outside the app."
        )


def list_files(destination):
    """Lists backup archives already at a destination. Returns a list of
    dicts: {"name": remote_filename, "size": bytes_or_None, "last_modified":
    datetime_or_None}, newest first. Raises BackupTransportError for
    providers this app can't reach directly (PROVIDER_OTHER).
    """
    secret = crypto_service.decrypt_field(destination.secret_encrypted)

    if destination.provider == PROVIDER_AWS:
        return _list_s3(destination, secret, endpoint_url=destination.endpoint_url or None)
    if destination.provider == PROVIDER_OCI:
        if not destination.endpoint_url:
            raise BackupTransportError("OCI destinations need the S3-compatible endpoint URL.")
        return _list_s3(destination, secret, endpoint_url=destination.endpoint_url)
    if destination.provider == PROVIDER_AZURE:
        return _list_azure(destination, secret)
    if destination.provider == PROVIDER_GCP:
        return _list_gcp(destination, secret)
    if destination.provider == PROVIDER_SELF_HOSTED:
        if destination.storage_type == STORAGE_TYPE_OBJECT_STORAGE:
            if not destination.endpoint_url:
                raise BackupTransportError("Self-hosted object storage needs an S3-compatible Endpoint URL.")
            return _list_s3(destination, secret, endpoint_url=destination.endpoint_url)
        return _list_sftp(destination, secret)
    raise BackupTransportError(
        f"Browsing isn't supported for provider '{destination.provider}'. "
        "Retrieve backups for this destination outside the app."
    )


def download(destination, remote_filename, local_path):
    """Downloads one backup archive from a destination to a local path."""
    secret = crypto_service.decrypt_field(destination.secret_encrypted)

    if destination.provider == PROVIDER_AWS:
        _download_s3(destination, remote_filename, local_path, secret, endpoint_url=destination.endpoint_url or None)
    elif destination.provider == PROVIDER_OCI:
        _download_s3(destination, remote_filename, local_path, secret, endpoint_url=destination.endpoint_url)
    elif destination.provider == PROVIDER_AZURE:
        _download_azure(destination, remote_filename, local_path, secret)
    elif destination.provider == PROVIDER_GCP:
        _download_gcp(destination, remote_filename, local_path, secret)
    elif destination.provider == PROVIDER_SELF_HOSTED:
        if destination.storage_type == STORAGE_TYPE_OBJECT_STORAGE:
            _download_s3(destination, remote_filename, local_path, secret, endpoint_url=destination.endpoint_url)
        else:
            _download_sftp(destination, remote_filename, local_path, secret)
    else:
        raise BackupTransportError(f"Downloading isn't supported for provider '{destination.provider}'.")


def _split_bucket_prefix(value, label):
    if not value:
        raise BackupTransportError(f"{label} is required.")
    if "/" in value:
        bucket, prefix = value.split("/", 1)
        prefix = prefix.strip("/")
        return bucket, (prefix + "/") if prefix else ""
    return value, ""


def _s3_client(destination, secret, endpoint_url):
    import boto3
    from botocore.config import Config

    if not destination.access_key_id or not secret:
        raise BackupTransportError("Access Key ID and Secret are required.")

    return boto3.client(
        "s3",
        aws_access_key_id=destination.access_key_id,
        aws_secret_access_key=secret,
        region_name=destination.region or None,
        endpoint_url=endpoint_url,
        # botocore >=1.36 adds a checksum header/trailer to every S3 upload
        # by default, which non-AWS S3-compatible services (OCI, MinIO, ...)
        # often can't validate, breaking SigV4 signing with a
        # SignatureDoesNotMatch error. Restrict checksums to operations that
        # actually require them, matching pre-1.36 behavior.
        config=Config(request_checksum_calculation="when_required", response_checksum_validation="when_required"),
    )


def _upload_s3(destination, local_path, remote_filename, secret, endpoint_url):
    bucket, prefix = _split_bucket_prefix(destination.bucket_or_resource, "Bucket / Container / Instance")
    client = _s3_client(destination, secret, endpoint_url)
    client.upload_file(local_path, bucket, prefix + remote_filename)


def _list_s3(destination, secret, endpoint_url):
    bucket, prefix = _split_bucket_prefix(destination.bucket_or_resource, "Bucket / Container / Instance")
    client = _s3_client(destination, secret, endpoint_url)
    files = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            files.append(
                {"name": obj["Key"][len(prefix):], "size": obj.get("Size"), "last_modified": obj.get("LastModified")}
            )
    files.sort(key=lambda f: f["last_modified"] or "", reverse=True)
    return files


def _download_s3(destination, remote_filename, local_path, secret, endpoint_url):
    bucket, prefix = _split_bucket_prefix(destination.bucket_or_resource, "Bucket / Container / Instance")
    client = _s3_client(destination, secret, endpoint_url)
    client.download_file(bucket, prefix + remote_filename, local_path)


def _azure_container_client(destination, secret):
    from azure.storage.blob import BlobServiceClient

    container, prefix = _split_bucket_prefix(destination.bucket_or_resource, "Container name")
    if not destination.access_key_id or not secret:
        raise BackupTransportError("Storage account name (Access Key ID) and account key (Secret) are required.")

    account_url = destination.endpoint_url or f"https://{destination.access_key_id}.blob.core.windows.net"
    service = BlobServiceClient(account_url=account_url, credential=secret)
    return service.get_container_client(container), prefix


def _upload_azure(destination, local_path, remote_filename, secret):
    container_client, prefix = _azure_container_client(destination, secret)
    blob_client = container_client.get_blob_client(prefix + remote_filename)
    with open(local_path, "rb") as f:
        blob_client.upload_blob(f, overwrite=True)


def _list_azure(destination, secret):
    container_client, prefix = _azure_container_client(destination, secret)
    files = []
    for blob in container_client.list_blobs(name_starts_with=prefix):
        files.append({"name": blob.name[len(prefix):], "size": blob.size, "last_modified": blob.last_modified})
    files.sort(key=lambda f: f["last_modified"] or "", reverse=True)
    return files


def _download_azure(destination, remote_filename, local_path, secret):
    container_client, prefix = _azure_container_client(destination, secret)
    blob_client = container_client.get_blob_client(prefix + remote_filename)
    with open(local_path, "wb") as f:
        f.write(blob_client.download_blob().readall())


def _gcp_bucket(destination, secret):
    import json

    from google.cloud import storage as gcs
    from google.oauth2 import service_account

    bucket_name, prefix = _split_bucket_prefix(destination.bucket_or_resource, "Bucket name")
    if not secret:
        raise BackupTransportError("A service account JSON key is required in the Secret field.")
    try:
        info = json.loads(secret)
    except ValueError as exc:
        raise BackupTransportError("GCP Secret must be the full service account JSON key.") from exc

    credentials = service_account.Credentials.from_service_account_info(info)
    client = gcs.Client(project=destination.account_identifier or info.get("project_id"), credentials=credentials)
    return client.bucket(bucket_name), prefix


def _upload_gcp(destination, local_path, remote_filename, secret):
    bucket, prefix = _gcp_bucket(destination, secret)
    blob = bucket.blob(prefix + remote_filename)
    blob.upload_from_filename(local_path)


def _list_gcp(destination, secret):
    bucket, prefix = _gcp_bucket(destination, secret)
    files = []
    for blob in bucket.list_blobs(prefix=prefix):
        files.append({"name": blob.name[len(prefix):], "size": blob.size, "last_modified": blob.updated})
    files.sort(key=lambda f: f["last_modified"] or "", reverse=True)
    return files


def _download_gcp(destination, remote_filename, local_path, secret):
    bucket, prefix = _gcp_bucket(destination, secret)
    blob = bucket.blob(prefix + remote_filename)
    blob.download_to_filename(local_path)


def _sftp_connect(destination, secret):
    import paramiko

    if not destination.endpoint_url:
        raise BackupTransportError("Host is required in Endpoint URL, e.g. sftp.example.com or sftp.example.com:2222.")
    if not destination.access_key_id:
        raise BackupTransportError("Username is required in Access Key ID / Username.")

    host = destination.endpoint_url
    port = 22
    if ":" in host:
        host, port_str = host.rsplit(":", 1)
        port = int(port_str)

    remote_dir = (destination.bucket_or_resource or ".").rstrip("/")

    transport = paramiko.Transport((host, port))
    transport.connect(username=destination.access_key_id, password=secret or None)
    return transport, paramiko.SFTPClient.from_transport(transport), remote_dir


def _upload_sftp(destination, local_path, remote_filename, secret):
    transport, sftp, remote_dir = _sftp_connect(destination, secret)
    try:
        sftp.put(local_path, f"{remote_dir}/{remote_filename}")
    finally:
        sftp.close()
        transport.close()


def _list_sftp(destination, secret):
    transport, sftp, remote_dir = _sftp_connect(destination, secret)
    try:
        files = [
            {"name": attr.filename, "size": attr.st_size, "last_modified": datetime.fromtimestamp(attr.st_mtime, tz=timezone.utc)}
            for attr in sftp.listdir_attr(remote_dir)
            if not attr.filename.startswith(".")
        ]
        files.sort(key=lambda f: f["last_modified"] or "", reverse=True)
        return files
    finally:
        sftp.close()
        transport.close()


def _download_sftp(destination, remote_filename, local_path, secret):
    transport, sftp, remote_dir = _sftp_connect(destination, secret)
    try:
        sftp.get(f"{remote_dir}/{remote_filename}", local_path)
    finally:
        sftp.close()
        transport.close()
