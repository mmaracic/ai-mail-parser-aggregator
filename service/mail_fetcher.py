"""Module for fetching emails from an IMAP server."""

import email
import imaplib
from datetime import datetime
from email.header import decode_header
from email.message import EmailMessage

from pydantic import BaseModel


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
    recipients: list[str]
    body: str
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

        folder_result = self.mail.select("inbox", readonly=True)
        if folder_result[0] != "EXISTS":  # Check if folder selection was successful
            raise Exception("Failed to select the mail folder")

    def close(self):
        """Close the connection to the mail server."""
        self.mail.close()
        self.mail.logout()

    def fetch_emails(self, max_emails: int = 10) -> list[Mail]:
        """Fetch emails from the IMAP server."""
        status, messages = self.mail.search(None, "ALL")  # or "UNSEEN" for unread
        email_ids = messages[0].split()

        # Fetch and process emails
        mails = []
        for email_id in email_ids:
            status, msg_data = self.mail.fetch(email_id, "(RFC822)")

            for response in msg_data:
                if isinstance(response, tuple):
                    msg: EmailMessage[str, str] = email.message_from_bytes(response[1])

                    # Get subject
                    subject = decode_header(msg["Subject"])[0][0]
                    if isinstance(subject, bytes):
                        subject = subject.decode()

                    # Get sender
                    from_ = msg.get("From")
                    # Get recipients
                    to_ = msg.get("To")
                    # Get date
                    date_ = msg.get("Date")

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

                    mail = Mail(
                        id=email_id.decode(),
                        date=datetime.strptime(date_, "%a, %d %b %Y %H:%M:%S %z"),
                        subject=subject,
                        sender=from_,
                        recipients=to_.split(", "),
                        body=body,
                        attachments=attachments,
                    )
                    mails.append(mail)
        return mails

    # Can be used to decode headers like subject or filenames
    def _decode_header(self, header) -> str:
        """Decode email header to a readable string."""
        # Decode header if needed
        decoded = decode_header(header)
        header_str = decoded[0][0]
        if isinstance(header_str, bytes):
            return header_str.decode()
        return header_str

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
