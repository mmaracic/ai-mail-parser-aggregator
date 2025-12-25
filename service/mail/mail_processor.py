"""Module for processing emails."""

import re
from datetime import UTC, datetime

from bs4 import BeautifulSoup
from pydantic import BaseModel, field_serializer

from service.mail.mail_fetcher import Mail, MailFetcher


class ProcessedMail(BaseModel):
    """Represents a processed email."""

    mail: Mail
    processed_at: datetime
    original_body_size: int
    processed_body_size: int

    @field_serializer("processed_at")
    def serialise_date(self, value: datetime) -> str:
        """Serialize datetime to ISO 8601 format."""
        return value.isoformat()

    def get_identifier(self) -> str:
        """Return a unique identifier for the processed email."""
        return self.mail.get_identifier()


class MailProcessor:
    """Process emails fetched by MailFetcher."""

    def __init__(self, fetcher: MailFetcher, approved_mails: list[str]) -> None:
        """Initialize MailProcessor with a MailFetcher and approved email list."""
        self.fetcher = fetcher
        self.approved_mails = approved_mails

    def process_emails(self, days: int = 7) -> int:
        """Fetch and process emails from the last 'days' days."""
        emails = self.fetcher.fetch_basic_emails(days=days, max_emails=0)
        mails_to_process = [
            email
            for email in emails
            if self._extract_email_from_sender(email.sender) in self.approved_mails
        ]
        processed_mails = 0
        for email in mails_to_process:
            if self.process_email(email):
                processed_mails += 1

        return processed_mails

    def process_email(self, email: Mail) -> bool:
        # Clean HTML with BeautifulSoup
        soup = BeautifulSoup(email.body, "html.parser")

        # Extract text content
        cleaned_text = soup.get_text(separator="\n", strip=True)

        email.body = cleaned_text

        processed_mail = ProcessedMail(
            mail=email,
            processed_at=datetime.now(tz=UTC),
            original_body_size=len(email.body),
            processed_body_size=len(cleaned_text),
        )

        return True

    def _extract_email_from_sender(self, sender) -> str | None:
        """Extract relevant data from the sender's email address."""
        # Match email in angle brackets: Name <email@domain.com>
        match = re.search(r"<([^>]+)>", sender)
        if match:
            return match.group(1)
        if "@" in sender:
            return sender.strip()
        return None
