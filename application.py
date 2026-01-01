"""FastAPI application for fetching and processing emails."""

import logging
import os
import traceback
from contextlib import asynccontextmanager
from datetime import date
from imaplib import IMAP4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request

from service.database.azure_nosql_repo import AzureRepository
from service.database.azure_service import AzureService, BasicProcessingAudit
from service.database.knowledge_database import KnowledgeDatabase
from service.file.azure_blob_repo import AzureBlobRepository
from service.llm.knowledge_extraction_llm import KnowledgeExtractionLLM
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
logging.getLogger("azure.cosmos").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""

    if not hasattr(app.state, "load_env") or app.state.load_env is True:
        # Load environment variables from .env file
        load_dotenv()
        logger.info("✓ Environment variables loaded from .env file")
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

        azure_service = AzureService(audit_repo)
        app.state.azure_service = azure_service

        blob_repo = AzureBlobRepository(os.getenv("AZURE_BLOB_CONNECTION_STRING", ""))
        blob_container = os.getenv("BLOB_CONTAINER", "processed-emails")

        knowledge_extraction_llm = KnowledgeExtractionLLM(
            model=os.getenv(
                "LLM_MODEL",
                "openrouter/nvidia/nemotron-3-nano-30b-a3b:free",
            ),
            api_key=os.getenv("LLM_API_KEY", ""),
        )
        knowledge_database = KnowledgeDatabase(
            host=os.getenv("MEMGRAPH_HOST", "localhost"),
            port=int(os.getenv("MEMGRAPH_PORT", "7687")),
            username=os.getenv("MEMGRAPH_USERNAME", "admin"),
            password=os.getenv("MEMGRAPH_PASSWORD", "admin_password"),
            encrypted=os.getenv("MEMGRAPH_ENCRYPTED", "True").lower() == "true",
            database=os.getenv("MEMGRAPH_DATABASE", "knowledge_db"),
        )

        mail_processor = MailProcessor(
            fetcher=mail_fetcher,
            audit_repo=audit_repo,
            config_repo=config_repo,
            blob_repo=blob_repo,
            blob_container=blob_container,
            text_processor_wrapper=TextProcessorWrapper(
                [HtmlProcessor(), NewsletterCleaner()]
            ),
            knowledge_extraction_llm=knowledge_extraction_llm,
            knowledge_database=knowledge_database,
        )
        app.state.mail_processor = mail_processor
        logger.info(f"✓ Connected to {config.imap_server}")
    except Exception as e:
        logger.error(f"✗ Failed to initialize mail fetcher: {e}")
        raise

    yield

    # Shutdown: Close mail connection
    if mail_fetcher:
        try:
            mail_fetcher.close()
            logger.info("✓ Disconnected from mail server")
        except IMAP4.abort as e:
            logger.error(f"✗ Failed to disconnect from mail server: {e}")


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


@app.get("/get-recent-audits", response_model=list[BasicProcessingAudit])
async def get_recent_audits(
    request: Request,
    limit: int = 10,
) -> list[BasicProcessingAudit]:
    """Get recent processing audits from Azure Cosmos DB.

    Args:
        limit: Maximum number of audits to retrieve (default: 10)

    Returns:
        List of recent processing audits

    """
    if not request.app.state.azure_service:
        raise HTTPException(status_code=503, detail="Azure service not initialized")

    try:
        azure_service: AzureService = request.app.state.azure_service
        return azure_service.read_most_recent_items(limit=limit)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch audits: {str(e)}")


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


@app.get("/process-emails-range", response_model=int)
async def process_emails_in_range(
    request: Request, after_date: date, before_date: date
) -> int:
    """Process emails in the specified date range."""
    if not request.app.state.mail_processor:
        raise HTTPException(status_code=503, detail="Mail processor not initialized")

    try:
        mail_processor: MailProcessor = request.app.state.mail_processor
        return mail_processor.process_emails_in_range(
            after_date=after_date, before_date=before_date
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Failed to process emails: {str(e)}"
        )


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
