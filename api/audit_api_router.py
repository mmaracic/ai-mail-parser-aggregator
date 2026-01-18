"""API router for audit-related endpoints."""

import traceback
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from api.application_model import AppState, get_services
from service.database.azure_service import BasicProcessingAudit

router = APIRouter()


@router.get("/get-recent-audits")
async def get_recent_audits(
    services: Annotated[AppState, Depends(get_services)],
    limit: int = 10,
) -> list[BasicProcessingAudit]:
    """Get recent processing audits from Azure Cosmos DB.

    Args:
        services: Application services dependency
        limit: Maximum number of audits to retrieve (default: 10)

    Returns:
        List of recent processing audits

    """
    try:
        return services.azure_service.read_most_recent_items(limit=limit)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch audits: {str(e)}",
        ) from e
