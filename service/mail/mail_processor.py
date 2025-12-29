"""Module for processing emails."""

import logging
import re
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_serializer

from service.database.azure_nosql_repo import AzureRepository
from service.database.knowledge_database import KnowledgeConcept, KnowledgeDatabase
from service.file.azure_blob_repo import AzureBlobRepository, RepoBlob
from service.llm.knowledge_extraction_llm import (
    KnowledgeExtractionLLM,
    MeteredKnowledgeConceptResponse,
)
from service.mail.mail_fetcher import Mail, MailFetcher
from service.text.text_processor import ProcessingAudit, TextProcessorWrapper
from service.util import calculate_savings

logger = logging.getLogger(__name__)


class ProcessedMail(BaseModel):
    """Represents a processed email to be stored in the blob storage."""

    mail: Mail
    processed_at: datetime
    tokens_used: int
    tokens_cached: int
    model: str
    provider: str
    concept_count: int
    keyword_count: int
    url_count: int
    concepts: list[KnowledgeConcept]

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
    tokens_cached: int = 0
    model: str
    provider: str
    concept_count: int
    keyword_count: int
    url_count: int
    processing_steps: list[ProcessingAudit]
    concepts: list[KnowledgeConcept]

    @field_serializer("processing_start_time", "processing_end_time")
    def serialise_date(self, value: datetime) -> str:
        """Serialize datetime to ISO 8601 format."""
        return value.isoformat()


class ProcessingAudit(BaseModel):
    """Represents an audit record for email processing instance, to be stored in the database."""

    id: str = Field(
        default_factory=lambda: f"mm-{datetime.now(tz=UTC).isoformat()}-{uuid.uuid4()}",
    )
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
        config_repo: AzureRepository,
        blob_repo: AzureBlobRepository,
        blob_container: str,
        text_processor_wrapper: TextProcessorWrapper,
        knowledge_extraction_llm: KnowledgeExtractionLLM,
        knowledge_database: KnowledgeDatabase,
    ) -> None:
        """Initialize MailProcessor with a MailFetcher and approved email list."""
        self.fetcher = fetcher
        self.audit_repo = audit_repo
        self.config_repo = config_repo
        self.blob_repo = blob_repo
        self.blob_container = blob_container
        self.text_processor_wrapper = text_processor_wrapper
        self.knowledge_extraction_llm = knowledge_extraction_llm
        self.knowledge_database = knowledge_database

    def process_emails(self, days: int = 7) -> int:
        """Fetch and process emails from the last 'days' days."""
        approved_mails = self.config_repo.read_item("approved_mails").get("mails", [])
        logger.info(f"✓ Loaded {len(approved_mails)} approved mails from config repo")
        llm_prompt = self.config_repo.read_item("llm_prompt").get("prompt", "")
        topic_prompt = self.config_repo.read_item("concept_topic").get("prompt", "")
        topic_list = self.config_repo.read_item("concept_topic").get("topic", [])
        logger.info(f"✓ Loaded LLM prompt from config repo. Topic list: {topic_list}")
        emails = self.fetcher.fetch_basic_emails(days_ago=days, max_emails=0)
        mails_to_process: list[Mail] = [
            email
            for email in emails
            if self._extract_email_from_sender(email.sender) in approved_mails
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

            processed_mail, processing_audits = self.process_email(
                email=email,
                llm_prompt=f"{llm_prompt}\n{topic_prompt} {topic_list}",
            )
            process_end = datetime.now(tz=UTC)

            mail_audit_record = ProcessingMailAudit(
                mail_identifier=processed_mail.get_identifier(),
                mail_source=self._extract_email_from_sender(email.sender),
                original_body_size=body_size_before,
                processed_body_size=len(processed_mail.mail.body),
                processing_body_savings_percentage=calculate_savings(
                    body_size_before,
                    len(processed_mail.mail.body),
                ),
                processing_start_time=process_start,
                processing_end_time=process_end,
                processing_duration_seconds=(
                    process_end - process_start
                ).total_seconds(),
                processing_steps=processing_audits,
                tokens_used=processed_mail.tokens_used,
                tokens_cached=processed_mail.tokens_cached,
                model=processed_mail.model,
                provider=processed_mail.provider,
                concept_count=processed_mail.concept_count,
                keyword_count=processed_mail.keyword_count,
                url_count=processed_mail.url_count,
                concepts=processed_mail.concepts,
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

    def process_email(
        self, email: Mail, llm_prompt: str
    ) -> tuple[ProcessedMail, list[ProcessingAudit]]:
        """Process a single email."""
        cleaned_text, audits = self.text_processor_wrapper.process(
            email.body,
            source=self._extract_email_from_sender(email.sender),
        )
        email.body = cleaned_text
        metered_response: MeteredKnowledgeConceptResponse = (
            self.knowledge_extraction_llm.get_response(
                query=cleaned_text,
                prompt=llm_prompt,
            )
        )
        self.knowledge_database.add_knowledge(
            concepts=metered_response.concepts,
            email_id=email.get_identifier(),
            source=self._extract_email_from_sender(email.sender),
        )

        return (
            ProcessedMail(
                mail=email,
                processed_at=datetime.now(tz=UTC),
                original_body_size=len(email.body),
                processed_body_size=len(cleaned_text),
                tokens_used=metered_response.total_tokens,
                tokens_cached=metered_response.cached_tokens,
                model=metered_response.model,
                provider=metered_response.provider,
                concept_count=len(metered_response.concepts),
                keyword_count=sum(
                    len(concept.keywords) for concept in metered_response.concepts
                ),
                url_count=sum(
                    len(concept.urls) for concept in metered_response.concepts
                ),
                concepts=metered_response.concepts,
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
