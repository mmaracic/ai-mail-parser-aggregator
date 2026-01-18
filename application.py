"""FastAPI application for fetching and processing emails."""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from imaplib import IMAP4
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request

from api.application_model import AppState
from service.database.azure_nosql_repo import AzureRepository
from service.database.azure_service import AzureService
from service.database.knowledge_database import KnowledgeDatabase
from service.database.knowledge_service import KnowledgeService
from service.file.azure_blob_repo import AzureBlobRepository
from service.llm.knowledge_extraction_llm import KnowledgeExtractionLLM
from service.mail.mail_fetcher import (
    MailFetcher,
    MailFetcherConfiguration,
)
from service.mail.mail_processor import MailProcessor
from service.text import NewsletterCleaner
from service.text.text_processor import HtmlProcessor, TextProcessorWrapper
from api.audit_api_router import router as audit_router
from api.processing_api_router import router as processing_router

logging.basicConfig(level=logging.INFO)
logging.getLogger("azure.cosmos").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[Any, Any]:
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
                "EMAIL_USERNAME and EMAIL_PASSWORD must be set in .env file",
            )

        mail_fetcher = MailFetcher(config)

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
        knowledge_service = KnowledgeService(knowledge_database)

        mail_processor = MailProcessor(
            source=os.getenv("DATA_SOURCE", "localhost"),
            fetcher=mail_fetcher,
            audit_repo=audit_repo,
            config_repo=config_repo,
            blob_repo=blob_repo,
            blob_container=blob_container,
            text_processor_wrapper=TextProcessorWrapper(
                [HtmlProcessor(), NewsletterCleaner()],
            ),
            knowledge_extraction_llm=knowledge_extraction_llm,
            knowledge_database=knowledge_database,
        )
        app_state = AppState(
            mail_fetcher=mail_fetcher,
            azure_service=azure_service,
            mail_processor=mail_processor,
            knowledge_service=knowledge_service,
        )
        app.state.services = app_state
        logger.info("✓ Connected to %s", config.imap_server)

    except Exception:
        logger.exception("✗ Failed to initialize mail fetcher")
        raise

    yield

    # Shutdown: Close mail connection
    if mail_fetcher:
        try:
            mail_fetcher.close()
            logger.info("✓ Disconnected from mail server")
        except IMAP4.abort:
            logger.exception("✗ Failed to disconnect from mail server")


app = FastAPI(
    title="Email Parser & Aggregator",
    description="API for fetching and processing emails",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router=audit_router)
app.include_router(router=processing_router)


@app.get("/health")
async def health_check(request: Request) -> dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "mail_fetcher": (
            "connected" if request.app.state.mail_fetcher else "disconnected"
        ),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
