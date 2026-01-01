"""Service for interacting with Azure Cosmos DB for processing audits."""

from datetime import datetime

from pydantic import BaseModel

from service.database.azure_nosql_repo import AzureRepository
from service.mail.mail_processor import ProcessingAudit


class BasicProcessingAudit(BaseModel):
    """Represents a basic processing audit record."""

    total_emails_fetched: int
    total_emails_processed: int
    mail_start_window: datetime | None
    mail_end_window: datetime | None
    processing_start_time: datetime
    processing_end_time: datetime


class AzureService:
    """Service for interacting with Azure Cosmos DB for processing audits."""

    def __init__(self, repo: AzureRepository) -> None:
        """Service for interacting with Azure Cosmos DB for processing audits."""
        self.repo = repo

    def read_most_recent_items(self, limit: int = 10) -> list[BasicProcessingAudit]:
        """Read the most recent items from the Cosmos DB container.

        Args:
            limit (int): The maximum number of items to retrieve.

        Returns:
            list[BasicProcessingAudit]: List of the most recent ProcessingAudit items.

        """
        items = self.repo.read_most_recent_items(limit=limit)
        audits = [ProcessingAudit.model_validate(item) for item in items]
        return [
            BasicProcessingAudit(
                total_emails_fetched=audit.total_emails_fetched,
                total_emails_processed=audit.total_emails_processed,
                mail_start_window=audit.mail_start_window,
                mail_end_window=audit.mail_end_window,
                processing_start_time=audit.processing_start_time,
                processing_end_time=audit.processing_end_time,
            )
            for audit in audits
        ]
