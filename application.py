"""FastAPI application for fetching and processing emails."""

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from service.mail_fetcher import Attachment, Mail, MailFetcher, MailFetcherConfiguration

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Global mail fetcher instance
mail_fetcher: MailFetcher | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global mail_fetcher

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
        logger.info(f"✓ Connected to {config.imap_server} as {config.username}")
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
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "mail_fetcher": "connected" if mail_fetcher else "disconnected",
    }


@app.get("/full-emails", response_model=list[Mail])
async def get_full_emails(max_emails: int = 10) -> list[Mail]:
    """Get full emails from the configured IMAP server (GET method).

    Args:
        max_emails: Maximum number of emails to fetch (default: 10)

    Returns:
        List of fetched emails with their metadata and content
    """
    if not mail_fetcher:
        raise HTTPException(status_code=503, detail="Mail fetcher not initialized")

    try:
        return mail_fetcher.fetch_full_emails(max_emails=max_emails)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch emails: {str(e)}")


@app.get("/basic-emails", response_model=list[Mail])
async def get_basic_emails(max_emails: int = 10) -> list[Mail]:
    """Get basic emails from the configured IMAP server (GET method).

    Args:
        max_emails: Maximum number of emails to fetch (default: 10)

    Returns:
        List of fetched emails with their metadata and content
    """
    if not mail_fetcher:
        raise HTTPException(status_code=503, detail="Mail fetcher not initialized")

    try:
        return mail_fetcher.fetch_basic_emails(max_emails=max_emails)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch emails: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
