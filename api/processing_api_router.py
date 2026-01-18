"""API router for processing-related endpoints."""

import traceback
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from api.application_model import AppState, get_services
from service.mail.mail_fetcher import Mail

router = APIRouter()


@router.get("/full-email", response_model=Mail | None)
async def get_full_email(
    services: Annotated[AppState, Depends(get_services)],
    email_id: str,
) -> Mail | None:
    """Get full email from the configured IMAP server by email ID (GET method).

    Args:
        email_id: ID of the email to fetch
        services: Application services dependency

    Returns:
        The fetched email with its metadata and content

    """
    try:
        return services.mail_fetcher.fetch_full_email_by_id(email_id)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch emails: {str(e)}",
        ) from e


@router.get("/basic-emails")
async def get_basic_emails(
    services: Annotated[AppState, Depends(get_services)],
    max_emails: int = 10,
) -> list[Mail]:
    """Get basic emails from the configured IMAP server (GET method).

    Args:
        services: Application services dependency
        max_emails: Maximum number of emails to fetch (default: 10)

    Returns:
        List of fetched emails with their metadata and content

    """
    try:
        return services.mail_fetcher.fetch_basic_emails(max_emails=max_emails)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch emails: {str(e)}",
        ) from e


@router.get("/process-emails-range")
async def process_emails_in_range(
    services: Annotated[AppState, Depends(get_services)],
    after_date: date,
    before_date: date,
) -> int:
    """Process emails in the specified date range."""
    try:
        return services.mail_processor.process_emails_in_range(
            after_date=after_date,
            before_date=before_date,
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process emails: {str(e)}",
        ) from e


@router.get("/process-emails")
async def process_emails(
    services: Annotated[AppState, Depends(get_services)],
    days: int = 7,
) -> int:
    """Process emails from the last 'days' days."""
    try:
        return services.mail_processor.process_emails(days=days)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process emails: {str(e)}",
        ) from e
