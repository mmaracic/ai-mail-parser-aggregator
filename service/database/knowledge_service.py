"""Knowledge service for managing knowledge concepts."""

from service.database.knowledge_database import (
    KnowledgeConceptBasicInfo,
    KnowledgeDatabase,
)


class KnowledgeService:
    """Service for managing knowledge concepts in the database."""

    def __init__(self, knowledge_database: KnowledgeDatabase):
        self.knowledge_database = knowledge_database

    def get_all_knowledge_concepts_basic_info(self) -> list[KnowledgeConceptBasicInfo]:
        """Retrieve basic information of all knowledge concepts."""
        return self.knowledge_database.get_all_concepts_basic_info()
