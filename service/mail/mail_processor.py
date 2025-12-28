"""Module for processing emails."""

import re
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, field_serializer

from service.database.azure_nosql_repo import AzureRepository
from service.file.azure_blob_repo import AzureBlobRepository, RepoBlob
from service.mail.mail_fetcher import Mail, MailFetcher
from service.text.text_processor import ProcessingAudit, TextProcessorWrapper
from service.util import calculate_savings


class ProcessedMail(BaseModel):
    """Represents a processed email to be stored in the blob storage."""

    mail: Mail
    processed_at: datetime

    @field_serializer("processed_at")
    def serialise_date(self, value: datetime) -> str:
        """Serialize datetime to ISO 8601 format."""
        return value.isoformat()

    def get_identifier(self) -> str:
        """Return a unique identifier for the processed email."""
        return self.mail.get_identifier()


class ProcessingMailAudit(BaseModel):
    """Represents an audit record for email processing to be stored in the database."""

    mail_identifier: str
    mail_source: str
    original_body_size: int
    processed_body_size: int
    processing_body_savings_percentage: float = 0.0
    processing_start_time: datetime
    processing_end_time: datetime
    processing_duration_seconds: float
    tokens_used: int = 0
    processing_steps: list[ProcessingAudit]

    @field_serializer("processing_start_time", "processing_end_time")
    def serialise_date(self, value: datetime) -> str:
        """Serialize datetime to ISO 8601 format."""
        return value.isoformat()


class ProcessingAudit(BaseModel):
    """Represents an audit record for email processing instance, to be stored in the database."""

    id: str = "mm-" + datetime.now(tz=UTC).isoformat() + "-" + str(uuid.uuid4())
    total_emails_fetched: int
    total_emails_processed: int
    mail_start_window: datetime | None
    mail_end_window: datetime | None
    processing_start_time: datetime
    processing_end_time: datetime
    processed_mails: list[ProcessingMailAudit] = []

    @field_serializer(
        "processing_start_time",
        "processing_end_time",
        "mail_start_window",
        "mail_end_window",
    )
    def serialise_date(self, value: datetime) -> str:
        """Serialize datetime to ISO 8601 format."""
        return value.isoformat()


class MailProcessor:
    """Process emails fetched by MailFetcher."""

    def __init__(
        self,
        fetcher: MailFetcher,
        audit_repo: AzureRepository,
        blob_repo: AzureBlobRepository,
        blob_container: str,
        approved_mails: list[str],
        text_processor_wrapper: TextProcessorWrapper,
    ) -> None:
        """Initialize MailProcessor with a MailFetcher and approved email list."""
        self.fetcher = fetcher
        self.audit_repo = audit_repo
        self.blob_repo = blob_repo
        self.blob_container = blob_container
        self.approved_mails = approved_mails
        self.text_processor_wrapper = text_processor_wrapper

    def process_emails(self, days: int = 7) -> int:
        """Fetch and process emails from the last 'days' days."""
        emails = self.fetcher.fetch_basic_emails(days_ago=days, max_emails=0)
        mails_to_process: list[Mail] = [
            email
            for email in emails
            if self._extract_email_from_sender(email.sender) in self.approved_mails
        ]
        mail_timestamps = [email.date for email in mails_to_process]
        mail_start_window = min(mail_timestamps) if len(mail_timestamps) > 0 else None
        mail_end_window = max(mail_timestamps) if len(mail_timestamps) > 0 else None
        total_process_start = datetime.now(tz=UTC)
        process_audits = []
        for basic_email in mails_to_process:
            email = self.fetcher.fetch_full_email_by_id(basic_email.id)
            process_start = datetime.now(tz=UTC)
            body_size_before = len(email.body)
            processed_mail, processing_audits = self.process_email(email)
            process_end = datetime.now(tz=UTC)

            mail_audit_record = ProcessingMailAudit(
                mail_identifier=processed_mail.get_identifier(),
                mail_source=self._extract_email_from_sender(email.sender),
                original_body_size=body_size_before,
                processed_body_size=len(processed_mail.mail.body),
                processing_body_savings_percentage=calculate_savings(
                    body_size_before, len(processed_mail.mail.body)
                ),
                processing_start_time=process_start,
                processing_end_time=process_end,
                processing_duration_seconds=(
                    process_end - process_start
                ).total_seconds(),
                processing_steps=processing_audits,
            )
            process_audits.append(mail_audit_record)
            self.blob_repo.upload_blob(
                RepoBlob(
                    name=processed_mail.get_identifier() + ".json",
                    container=self.blob_container,
                    size=len(processed_mail.mail.body),
                    data=processed_mail.model_dump_json(),
                ),
            )
        total_process_end = datetime.now(tz=UTC)
        audit_record = ProcessingAudit(
            total_emails_fetched=len(emails),
            total_emails_processed=len(mails_to_process),
            mail_start_window=mail_start_window,
            mail_end_window=mail_end_window,
            processing_start_time=total_process_start,
            processing_end_time=total_process_end,
            processed_mails=process_audits,
        )
        self.audit_repo.create_item(audit_record.model_dump())
        return len(mails_to_process)

    def process_email(self, email: Mail) -> tuple[ProcessedMail, list[ProcessingAudit]]:
        """Process a single email."""
        cleaned_text, audits = self.text_processor_wrapper.process(
            email.body,
            source=self._extract_email_from_sender(email.sender),
        )
        email.body = cleaned_text

        return (
            ProcessedMail(
                mail=email,
                processed_at=datetime.now(tz=UTC),
                original_body_size=len(email.body),
                processed_body_size=len(cleaned_text),
            ),
            audits,
        )

    def _extract_email_from_sender(self, sender: str) -> str | None:
        """Extract relevant data from the sender's email address."""
        # Match email in angle brackets: Name <email@domain.com>
        match = re.search(r"<([^>]+)>", sender)
        if match:
            return match.group(1)
        if "@" in sender:
            return sender.strip()
        return None
