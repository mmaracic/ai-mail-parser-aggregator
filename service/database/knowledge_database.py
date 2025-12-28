"""Module for managing a knowledge database."""

from gqlalchemy import Memgraph, create, match, merge
from pydantic import BaseModel

CONCEPT_LABEL = "Concept"
KEYWORD_LABEL = "Keyword"
URL_LABEL = "URL"
EMAIL_LABEL = "Email"
SOURCE_LABEL = "Source"

NAME_PROPERTY = "name"

REPRESENTS_RELATIONSHIP = "REPRESENTS"
DESCRIBES_RELATIONSHIP = "DESCRIBES"
CONTAINS_RELATIONSHIP = "CONTAINS"
HOSTS_RELATIONSHIP = "HOSTS"
SENDS_RELATIONSHIP = "SENDS"


class KnowledgeConcept(BaseModel):
    """A model representing a knowledge concept."""

    name: str
    urls: list[str]
    keywords: list[str]


class KnowledgeDatabase:
    """A simple knowledge database class."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        encrypted: bool,
    ) -> None:
        """Initialize the knowledge database."""
        self.memgraph = Memgraph(
            host=host,
            port=port,
            username=username,
            password=password,
            encrypted=encrypted,
        )

    def add_knowledge(
        self,
        concepts: list[KnowledgeConcept],
        email_id: str,
        source: str,
    ) -> None:
        """Add a piece of knowledge to the database."""
        for concept in concepts:
            merge(self.memgraph).node(labels=CONCEPT_LABEL, name=concept.name).execute()
            for url in concept.urls:
                merge(self.memgraph).node(labels=URL_LABEL, name=url).execute()

                match(self.memgraph).node(
                    labels=CONCEPT_LABEL,
                    name=concept.name,
                    variable="d",
                ).match().node(labels=URL_LABEL, name=url, variable="s").create().node(
                    variable="s",
                ).to(
                    relationship_type=DESCRIBES_RELATIONSHIP,
                ).node(
                    variable="d",
                ).execute()

            for keyword in concept.keywords:
                merge(self.memgraph).node(labels=KEYWORD_LABEL, name=keyword).execute()

                match(self.memgraph).node(
                    labels=CONCEPT_LABEL,
                    name=concept.name,
                    variable="d",
                ).match().node(
                    labels=KEYWORD_LABEL, name=keyword, variable="s"
                ).create().node(
                    variable="s",
                ).to(
                    relationship_type=REPRESENTS_RELATIONSHIP,
                ).node(
                    variable="d",
                ).execute()
