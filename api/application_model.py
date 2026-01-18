"""Application model definitions."""

from dataclasses import dataclass

from fastapi import Request

from service.database.azure_service import AzureService
from service.database.knowledge_service import KnowledgeService
from service.mail.mail_fetcher import MailFetcher
from service.mail.mail_processor import MailProcessor


@dataclass
class AppState:
    """Application state holding various services and processors."""

    mail_fetcher: MailFetcher
    azure_service: AzureService
    mail_processor: MailProcessor
    knowledge_service: KnowledgeService


def get_services(request: Request) -> AppState:
    """Dependency to get application services from request."""
    return request.app.state.services
