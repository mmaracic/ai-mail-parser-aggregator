"""Azure Blob Storage repository implementation."""

from azure.storage.blob import BlobServiceClient
from pydantic import BaseModel


class RepoBlob(BaseModel):
    """Data model for Azure Blob Storage repository configuration."""

    name: str
    container: str
    size: int
    data: bytes | None = None


class AzureBlobRepository:
    """Repository for Azure Blob Storage interactions."""

    def __init__(
        self,
        connection_string: str,
    ) -> None:
        """Initialize Azure Blob Repository with connection string and container name."""
        self.connection_string = connection_string
        self.blob_service_client = BlobServiceClient.from_connection_string(
            self.connection_string,
        )

    def get_container_list(self) -> list[str]:
        """Get a list of container names in the Blob Storage account.

        Returns:
            list[str]: List of container names.

        """
        containers = self.blob_service_client.list_containers()
        return [container.name for container in containers]

    def is_container(self, container_name: str) -> bool:
        """Check if a container exists in the Blob Storage account.

        Args:
            container_name (str): The name of the container.

        Returns:
            bool: True if the container exists, False otherwise.

        """
        containers = self.get_container_list()
        return container_name in containers

    def create_container(self, container_name: str) -> None:
        """Create a new container in the Blob Storage account.

        Args:
            container_name (str): The name of the container to create.

        """
        self.blob_service_client.create_container(container_name)

    def get_container_blobs(self, container_name: str) -> list[RepoBlob]:
        """Get a list of blob names in the specified container.

        Args:
            container_name (str): The name of the container.

        Returns:
            list[str]: List of blob names.

        """
        container_client = self.blob_service_client.get_container_client(container_name)
        blobs = container_client.list_blobs()
        return [
            RepoBlob(name=blob.name, container=container_name, size=blob.size)
            for blob in blobs
        ]

    def upload_blob(self, blob: RepoBlob) -> None:
        """Upload a blob to the specified container.

        Args:
            blob (RepoBlob): The blob to upload.

        """
        container_client = self.blob_service_client.get_container_client(blob.container)
        container_client.upload_blob(name=blob.name, data=blob.data)

    def download_blob(self, blob: RepoBlob) -> RepoBlob:
        """Download a blob from the specified container.

        Args:
            blob (RepoBlob): The blob to download.

        Returns:
            RepoBlob: The downloaded blob with data.

        """
        container_client = self.blob_service_client.get_container_client(blob.container)
        blob_client = container_client.get_blob_client(blob.name)
        downloader = blob_client.download_blob()
        return RepoBlob(
            name=blob.name,
            container=blob.container,
            size=downloader.properties.size,
            data=downloader.readall(),
        )
