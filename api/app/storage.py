"""Object storage client for MinIO/GCS."""

from datetime import timedelta
from typing import Optional
from minio import Minio
from minio.error import S3Error
from urllib.parse import urljoin

from app.config import settings
from app.logging_config import logger


class StorageClient:
    """Singleton storage client for MinIO/GCS."""

    _instance: Optional[Minio] = None

    @classmethod
    def get_client(cls) -> Minio:
        """Get or create MinIO client instance."""
        if cls._instance is None:
            # Parse endpoint to remove http:// or https://
            endpoint = settings.minio_endpoint.replace("http://", "").replace("https://", "")

            cls._instance = Minio(
                endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=settings.minio_secure,
            )

            # Ensure buckets exist
            cls._ensure_buckets()

            logger.info("MinIO client initialized", endpoint=endpoint)

        return cls._instance

    @classmethod
    def _ensure_buckets(cls):
        """Ensure required buckets exist."""
        client = cls._instance
        if not client:
            return

        buckets_to_create = [
            settings.storage_bucket_uploads,
            settings.storage_bucket_sidecars,
        ]

        for bucket_name in buckets_to_create:
            try:
                if not client.bucket_exists(bucket_name):
                    client.make_bucket(bucket_name)
                    logger.info("Created storage bucket", bucket=bucket_name)
            except S3Error as e:
                logger.error(
                    "Failed to create bucket",
                    bucket=bucket_name,
                    error=str(e)
                )

    @classmethod
    def generate_presigned_upload_url(
        cls,
        bucket: str,
        object_key: str,
        expires: timedelta = timedelta(minutes=15),
    ) -> str:
        """
        Generate presigned URL for uploading an object.

        Args:
            bucket: Bucket name
            object_key: Object key (path)
            expires: URL expiration time (default: 15 minutes)

        Returns:
            Presigned URL for PUT operation
        """
        client = cls.get_client()

        try:
            # Generate presigned URL with internal endpoint
            url = client.presigned_put_object(
                bucket,
                object_key,
                expires=expires,
            )

            logger.debug(
                "Original presigned URL from MinIO",
                url=url[:150] + "..." if len(url) > 150 else url
            )

            # Replace internal endpoint with external endpoint for browser access
            # MinIO signs the URL with the Host header, so we need to replace it carefully
            internal_endpoint = settings.minio_endpoint.replace("http://", "").replace("https://", "")
            external_endpoint = settings.minio_external_endpoint.replace("http://", "").replace("https://", "")

            if internal_endpoint != external_endpoint and internal_endpoint in url:
                # Replace the hostname in the URL
                url = url.replace(f"://{internal_endpoint}/", f"://{external_endpoint}/")
                logger.info(
                    "Replaced internal endpoint with external endpoint",
                    internal=internal_endpoint,
                    external=external_endpoint,
                    final_url=url[:150] + "..." if len(url) > 150 else url
                )

            logger.debug(
                "Generated presigned upload URL",
                bucket=bucket,
                object_key=object_key,
                expires_in=str(expires)
            )
            return url
        except S3Error as e:
            logger.error(
                "Failed to generate presigned upload URL",
                bucket=bucket,
                object_key=object_key,
                error=str(e)
            )
            raise

    @classmethod
    def generate_presigned_download_url(
        cls,
        bucket: str,
        object_key: str,
        expires: timedelta = timedelta(minutes=10),
    ) -> str:
        """
        Generate presigned URL for downloading an object.

        Args:
            bucket: Bucket name
            object_key: Object key (path)
            expires: URL expiration time (default: 10 minutes)

        Returns:
            Presigned URL for GET operation
        """
        client = cls.get_client()

        try:
            url = client.presigned_get_object(
                bucket,
                object_key,
                expires=expires,
            )

            logger.debug(
                "Generated presigned download URL",
                bucket=bucket,
                object_key=object_key,
                expires_in=str(expires)
            )
            return url
        except S3Error as e:
            logger.error(
                "Failed to generate presigned download URL",
                bucket=bucket,
                object_key=object_key,
                error=str(e)
            )
            raise

    @classmethod
    def put_object(cls, bucket: str, object_key: str, data: bytes, content_type: str = "application/octet-stream"):
        """
        Upload an object to storage.

        Args:
            bucket: Bucket name
            object_key: Object key (path)
            data: Object data
            content_type: MIME type

        Returns:
            Upload result
        """
        client = cls.get_client()

        from io import BytesIO

        try:
            result = client.put_object(
                bucket,
                object_key,
                BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
            logger.info(
                "Uploaded object to storage",
                bucket=bucket,
                object_key=object_key,
                size_bytes=len(data)
            )
            return result
        except S3Error as e:
            logger.error(
                "Failed to upload object",
                bucket=bucket,
                object_key=object_key,
                error=str(e)
            )
            raise

    @classmethod
    def get_object(cls, bucket: str, object_key: str) -> bytes:
        """
        Download an object from storage.

        Args:
            bucket: Bucket name
            object_key: Object key (path)

        Returns:
            Object data as bytes
        """
        client = cls.get_client()

        try:
            response = client.get_object(bucket, object_key)
            data = response.read()
            response.close()
            response.release_conn()
            logger.debug(
                "Downloaded object from storage",
                bucket=bucket,
                object_key=object_key,
                size_bytes=len(data)
            )
            return data
        except S3Error as e:
            logger.error(
                "Failed to download object",
                bucket=bucket,
                object_key=object_key,
                error=str(e)
            )
            raise

    @classmethod
    def delete_object(cls, bucket: str, object_key: str):
        """
        Delete an object from storage.

        Args:
            bucket: Bucket name
            object_key: Object key (path)
        """
        client = cls.get_client()

        try:
            client.remove_object(bucket, object_key)
            logger.info(
                "Deleted object from storage",
                bucket=bucket,
                object_key=object_key
            )
        except S3Error as e:
            logger.error(
                "Failed to delete object",
                bucket=bucket,
                object_key=object_key,
                error=str(e)
            )
            raise


# Convenience function
def get_storage_client() -> Minio:
    """Get storage client instance (for dependency injection)."""
    return StorageClient.get_client()
