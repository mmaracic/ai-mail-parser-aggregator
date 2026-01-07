"""Azure Functions entry point for the FastAPI application."""

import logging
import os
from datetime import UTC, datetime, timedelta

import azure.functions as func
from fastapi import Request
from starlette.types import Scope

from application import app as fastapi_app
from application import lifespan, process_emails_in_range

logging.basicConfig(level=logging.INFO)
logging.getLogger("azure.cosmos").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)
logger = logging.getLogger(__name__)

app = func.AsgiFunctionApp(app=fastapi_app, http_auth_level=func.AuthLevel.FUNCTION)


@app.timer_trigger(
    schedule="0 0 1 * * *",  # Every day at 1 AM
    arg_name="mytimer",
    run_on_startup=False,
    use_monitor=False,
)
async def scheduled_mail_processor(mytimer: func.TimerRequest) -> None:
    """Azure Function to trigger email processing on a schedule."""
    logger.info("Scheduled Mail Processor function executed.")
    scheduler_enabled = os.getenv("SCHEDULER_ENABLED", "False").lower() == "true"
    if scheduler_enabled:
        after_date = datetime.now(tz=UTC).date() - timedelta(days=1)
        before_date = datetime.now(tz=UTC).date()
        logger.info(
            f"Scheduler is enabled. Processing emails from {after_date} to {before_date}..."
        )
        # Ensure lifespan events are handled within the context
        async with lifespan(fastapi_app):
            # Create a properly formatted ASGI scope for the Request object
            scope: Scope = {
                "type": "http",
                "method": "GET",
                "path": "/",
                "query_string": b"",
                "headers": [],
                "app": fastapi_app,
            }
            processed_mail_count = await process_emails_in_range(
                request=Request(scope=scope),
                after_date=after_date,
                before_date=before_date,
            )
            logger.info(f"Processed {processed_mail_count} emails.")
    else:
        logger.info("Scheduler is disabled. Skipping email processing.")
