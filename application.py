"""FastAPI application for fetching and processing emails."""

import logging
import os
import traceback
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request

from service.database.azure_nosql_repo import AzureRepository
from service.file.azure_blob_repo import AzureBlobRepository
from service.mail.mail_fetcher import (
    Attachment,
    Mail,
    MailFetcher,
    MailFetcherConfiguration,
)
from service.mail.mail_processor import MailProcessor
from service.text import NewsletterCleaner
from service.text.text_processor import HtmlProcessor, TextProcessorWrapper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""

    # Startup: Initialize mail fetcher
    try:
        config = MailFetcherConfiguration(
            imap_server=os.getenv("IMAP_SERVER", "imap.gmail.com"),
            imap_port=int(os.getenv("IMAP_PORT", "993")),
            username=os.getenv("EMAIL_USERNAME", ""),
            password=os.getenv("EMAIL_PASSWORD", ""),
            folder=os.getenv("EMAIL_FOLDER", "inbox"),
        )
        if not config.username or not config.password:
            raise ValueError(
                "EMAIL_USERNAME and EMAIL_PASSWORD must be set in .env file"
            )

        mail_fetcher = MailFetcher(config)
        app.state.mail_fetcher = mail_fetcher

        cosmos_connection_string = os.getenv("AZURE_NOSQL_CONNECTION_STRING", "")
        db_name = os.getenv("DB_NAME", "MailParserDb")
        audit_container = os.getenv("AUDIT_CONTAINER", "Audit")
        config_container = os.getenv("CONFIG_CONTAINER", "Config")
        audit_repo = AzureRepository(
            connection_string=cosmos_connection_string,
            database_name=db_name,
            container_name=audit_container,
        )
        config_repo = AzureRepository(
            connection_string=cosmos_connection_string,
            database_name=db_name,
            container_name=config_container,
        )
        approved_mails = config_repo.read_item("approved_mails").get("mails", [])
        logger.info(f"✓ Loaded {len(approved_mails)} approved mails from config repo")
        blob_repo = AzureBlobRepository(os.getenv("AZURE_BLOB_CONNECTION_STRING", ""))
        blob_container = os.getenv("BLOB_CONTAINER", "processed-emails")
        mail_processor = MailProcessor(
            fetcher=mail_fetcher,
            audit_repo=audit_repo,
            blob_repo=blob_repo,
            blob_container=blob_container,
            approved_mails=approved_mails,
            text_processor_wrapper=TextProcessorWrapper(
                [HtmlProcessor(), NewsletterCleaner()]
            ),
        )
        app.state.mail_processor = mail_processor
        logger.info(f"✓ Connected to {config.imap_server}")
    except Exception as e:
        logger.error(f"✗ Failed to initialize mail fetcher: {e}")
        raise

    yield

    # Shutdown: Close mail connection
    if mail_fetcher:
        mail_fetcher.close()
        logger.info("✓ Disconnected from mail server")


app = FastAPI(
    title="Email Parser & Aggregator",
    description="API for fetching and processing emails",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check(request: Request) -> dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "mail_fetcher": (
            "connected" if request.app.state.mail_fetcher else "disconnected"
        ),
    }


@app.get("/full-email", response_model=Mail | None)
async def get_full_email(request: Request, email_id: str) -> Mail | None:
    """Get full email from the configured IMAP server by email ID (GET method).

    Args:
        email_id: ID of the email to fetch
    Returns:
        The fetched email with its metadata and content
    """
    if not request.app.state.mail_fetcher:
        raise HTTPException(status_code=503, detail="Mail fetcher not initialized")

    try:
        return request.app.state.mail_fetcher.fetch_full_email_by_id(email_id)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch emails: {str(e)}")


@app.get("/basic-emails", response_model=list[Mail])
async def get_basic_emails(request: Request, max_emails: int = 10) -> list[Mail]:
    """Get basic emails from the configured IMAP server (GET method).

    Args:
        max_emails: Maximum number of emails to fetch (default: 10)

    Returns:
        List of fetched emails with their metadata and content
    """
    if not request.app.state.mail_fetcher:
        raise HTTPException(status_code=503, detail="Mail fetcher not initialized")

    try:
        return request.app.state.mail_fetcher.fetch_basic_emails(max_emails=max_emails)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch emails: {str(e)}")


@app.get("/process-emails", response_model=int)
async def process_emails(request: Request, days: int = 7) -> int:
    """Process emails from the last 'days' days."""
    if not request.app.state.mail_processor:
        raise HTTPException(status_code=503, detail="Mail processor not initialized")

    try:
        mail_processor: MailProcessor = request.app.state.mail_processor
        return mail_processor.process_emails(days=days)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Failed to process emails: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
