"""Module for fetching emails from an IMAP server."""

import email
import imaplib
import logging
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.message import EmailMessage

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MailFetcherConfiguration(BaseModel):
    """Configuration for MailFetcher."""

    imap_server: str = "imap.gmail.com"
    imap_port: int = 993
    username: str
    password: str
    folder: str = "inbox"


class Attachment(BaseModel):
    """Class representing an email attachment."""

    filename: str
    content_type: str
    size: int
    data: bytes


class Mail(BaseModel):
    """Class representing an email message."""

    id: str
    date: datetime
    subject: str
    sender: str
    recipients: list[str] = []
    body: str | None = None
    attachments: list[Attachment] = []


class MailFetcher:
    """Class to fetch emails from an IMAP server."""

    def __init__(self, config: MailFetcherConfiguration) -> None:
        """Initialize MailFetcher with configuration and connect to the mail server."""
        self.config = config

        self.mail = imaplib.IMAP4_SSL(self.config.imap_server, self.config.imap_port)
        login_result = self.mail.login(self.config.username, self.config.password)
        if login_result[0] != "OK":  # Check if login was successful
            raise Exception("Failed to login to the mail server")

        folder_result = self.mail.select(self.config.folder, readonly=True)
        if folder_result[0] != "OK":  # Check if folder selection was successful
            status, folders = self.mail.list()
            logger.error(
                f"Available folders: {[folder.decode() for folder in folders]}"
            )
            raise Exception(
                f"Failed to select the mail folder: {self.config.folder} Status: {folder_result[0]}"
            )

    def close(self) -> None:
        """Close the connection to the mail server."""
        self.mail.close()
        self.mail.logout()

    def fetch_basic_emails(
        self, days_ago: int = 30, max_emails: int = 10
    ) -> list[Mail]:
        """Fetch only email headers (subject, sender, date) - much faster.

        Options for fetching parts of the email:
        (RFC822) - Fetches entire email (headers + body + attachments) - slow
        (BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)]) - Fetches only specified headers - fast
        BODY.PEEK doesn't mark the email as read (vs BODY which does)

        Other useful fetch options:
        (FLAGS) - Message flags (read/unread, flagged, etc.)
        (ENVELOPE) - Parsed envelope info (from, to, subject, date)
        (BODYSTRUCTURE) - Structure without content (useful to see attachments without downloading)
        (BODY[TEXT]) - Only body content, no headers
        """
        date = self._get_date_days_ago(days_ago)
        status, messages = self.mail.search(None, f"SINCE {date}")
        email_ids = messages[0].split()

        mails = []
        for email_id in email_ids[-max_emails:]:  # Get last N emails
            # Fetch only headers we need
            mail = self._extract_basic_email(email_id)
            if mail:
                mails.append(mail)
        return mails

    def fetch_full_emails(self, days_ago: int = 30, max_emails: int = 10) -> list[Mail]:
        """Fetch emails from the IMAP server.

        Possible search criteria:
        ALL - all messages
        UNSEEN - unread messages
        ANSWERED - answered messages
        FLAGGED - flagged messages
        DELETED - deleted messages
        SEEN - read messages
        NEW - new messages
        OLD - old messages
        RECENT - recent messages
        SUBJECT "text" - messages with "text" in the subject
        FROM "text" - messages from "text"
        TO "text" - messages to "text"

        Date criteria:
        BEFORE dd-mmm-yyyy - Messages before date
        SINCE dd-mmm-yyyy - Messages since date (inclusive)
        ON dd-mmm-yyyy - Messages on specific date
        SENTBEFORE dd-mmm-yyyy - Sent before date
        SENTSINCE dd-mmm-yyyy - Sent since date

        # Unread emails from specific sender
        mail.search(None, '(UNSEEN FROM "sender@example.com")')

        # Emails since date with subject keyword
        mail.search(None, '(SINCE 01-Jan-2024 SUBJECT "invoice")')

        # Unread OR flagged
        mail.search(None, '(OR UNSEEN FLAGGED)')

        # NOT deleted
        mail.search(None, '(NOT DELETED)')

        # Complex: Unread from sender since date
        mail.search(None, '(UNSEEN FROM "boss@company.com" SINCE 15-Dec-2024)')

        # When non ascii characters are used, specify charset
        mail.search('UTF-8', 'SUBJECT "über"')

        Date criteria:
        BEFORE dd-mmm-yyyy - Messages before date
        SINCE dd-mmm-yyyy - Messages since date (inclusive)
        ON dd-mmm-yyyy - Messages on specific date
        SENTBEFORE dd-mmm-yyyy - Sent before date
        SENTSINCE dd-mmm-yyyy - Sent since date
        """
        date = self._get_date_days_ago(days_ago)
        status, messages = self.mail.search(None, f"SINCE {date}")
        email_ids = messages[0].split()

        # Fetch and process emails
        mails = []
        for email_id in email_ids[-max_emails:]:  # Get last N emails
            mail = self._extract_full_email(email_id)
            if mail:
                mails.append(mail)
        return mails

    def _get_date_days_ago(self, days: int) -> str:
        """Get date string for 'days' ago in format dd-MMM-YYYY."""
        return (datetime.now(tz=timezone.utc) - timedelta(days=days)).strftime(
            "%d-%b-%Y"
        )

    # Can be used to decode headers like subject or filenames
    def _decode_header(self, header) -> str:
        """Decode email header to a readable string."""
        # Decode header if needed
        decoded = decode_header(header)
        header_str = decoded[0][0]
        if isinstance(header_str, bytes):
            return header_str.decode()
        return header_str

    def _extract_basic_email(self, email_id: str) -> Mail | None:
        # Fetch only headers we need
        """Fetch basic email info (subject, sender, date) without body or attachments."""
        status, msg_data = self.mail.fetch(
            email_id, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE TO)])"
        )

        for response in msg_data:
            if isinstance(response, tuple):
                msg = email.message_from_bytes(response[1])
                return self._get_basic_email_info(email_id.decode(), msg)

        return None

    def _extract_full_email(self, email_id: str) -> Mail | None:
        """Fetch full email including body and attachments."""
        # (RFC822) fetches mail by id, fetching EVERYTHING in it (body, attachments, all headers)
        status, msg_data = self.mail.fetch(email_id, "(RFC822)")

        for response in msg_data:
            if isinstance(response, tuple):
                msg: EmailMessage[str, str] = email.message_from_bytes(response[1])

                mail = self._get_basic_email_info(email_id.decode(), msg)
                # Get body
                body = ""
                attachments = []
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition"))

                        # Get body text
                        if (
                            content_type in {"text/plain", "text/html"}
                            and "attachment" not in content_disposition
                        ):
                            body = part.get_payload(decode=True).decode()
                        elif "attachment" in content_disposition:
                            attachment = self._extract_attachment(
                                part,
                                content_type,
                            )
                            if attachment:
                                attachments.append(attachment)
                else:
                    body = msg.get_payload(decode=True).decode()

                mail.body = body
                mail.attachments = attachments
                return mail

        return None

    def _get_basic_email_info(self, mail_id: str, msg: EmailMessage) -> Mail:
        """Extract basic email info from message object."""
        # Get subject
        subject = decode_header(msg["Subject"])[0][0]
        if isinstance(subject, bytes):
            subject = self._decode_bytes_to_str(subject)

        # Get sender
        from_ = msg.get("From")
        # Get recipients
        to_ = msg.get("To")
        # Get date
        date_ = msg.get("Date")

        return Mail(
            id=mail_id,
            date=self._convert_str_date_to_datetime(date_),
            subject=subject,
            sender=from_,
            recipients=to_.split(", "),
        )

    def _extract_attachment(
        self,
        part: EmailMessage,
        content_type: str,
    ) -> Attachment | None:
        """Return attachment object from email part."""
        filename = part.get_filename()
        if filename:
            attachment_data = part.get_payload(decode=True)
            return Attachment(
                filename=filename,
                content_type=content_type,
                size=len(attachment_data),
                data=attachment_data,
            )
        return None

    def _convert_str_date_to_datetime(self, date_str: str) -> datetime:
        """Convert email date string to datetime object."""
        try:
            return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z (%Z)")
        except ValueError as e:
            try:
                return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
            except ValueError:
                logger.error(f"Failed to parse date: {date_str} Error: {str(e)}")
                raise

    def _decode_bytes_to_str(self, byte_str: bytes) -> str:
        """Decode bytes to string, handling different encodings."""
        try:
            return byte_str.decode("utf-8")
        except UnicodeDecodeError:
            return byte_str.decode("latin-1")
