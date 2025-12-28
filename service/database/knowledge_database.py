"""Module for managing a knowledge database."""

import logging

from gqlalchemy import Memgraph, match, merge
from pydantic import BaseModel

logger = logging.getLogger(__name__)

CONCEPT_LABEL = "Concept"
KEYWORD_LABEL = "Keyword"
URL_LABEL = "URL"
WEBSITE_LABEL = "Website"
EMAIL_LABEL = "Email"
SOURCE_LABEL = "Source"

NAME_PROPERTY = "name"
URL_PROPERTY = "url"

REPRESENTS_RELATIONSHIP = "REPRESENTS"
DESCRIBES_RELATIONSHIP = "DESCRIBES"
CONTAINS_RELATIONSHIP = "CONTAINS"
HOSTS_RELATIONSHIP = "HOSTS"
SENDS_RELATIONSHIP = "SENDS"


class KnowledgeConcept(BaseModel):
    """A model representing a knowledge concept.

    Common Cypher queries:
    - Count all nodes: MATCH (n) RETURN count(n)
    - Delete all nodes: MATCH (n) DETACH DELETE n
    - Return all nodes (limited): MATCH (n) RETURN n LIMIT 200
    - Return all nodes with relationships (limited): MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 200
    """

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
        logger.info("Connecting to knowledge database with encrypted=%s", encrypted)
        self.memgraph = Memgraph(
            host=host,
            port=port,
            username=username,
            password=password,
            encrypted=encrypted,
        )
        # Test the connection
        # Equivalent to: MATCH (n) RETURN count(n);
        result = next(
            match(connection=self.memgraph)
            .node(variable="n")
            .return_({"count(n)": "count"})
            .execute()
        )
        logger.info("%s nodes in the knowledge database", result)

    def add_knowledge(
        self,
        concepts: list[KnowledgeConcept],
        email_id: str,
        source: str,
    ) -> None:
        """Add a piece of knowledge to the database."""
        for concept in concepts:
            merge(connection=self.memgraph).node(
                labels=CONCEPT_LABEL,
                name=concept.name,
            ).execute()
            for url in concept.urls:
                website = self._extract_website_from_url(url)
                merge(connection=self.memgraph).node(
                    labels=URL_LABEL,
                    name=url,
                ).execute()
                merge(connection=self.memgraph).node(
                    labels=WEBSITE_LABEL,
                    name=website,
                ).execute()

                match(connection=self.memgraph).node(
                    labels=CONCEPT_LABEL,
                    name=concept.name,
                    variable="ud",
                ).match().node(
                    labels=URL_LABEL,
                    name=url,
                    variable="us",
                ).match().node(
                    labels=WEBSITE_LABEL,
                    name=website,
                    variable="ws",
                ).merge().node(
                    variable="us",
                ).to(
                    relationship_type=DESCRIBES_RELATIONSHIP,
                ).node(
                    variable="ud",
                ).merge().node(
                    variable="ws",
                ).to(
                    relationship_type=HOSTS_RELATIONSHIP,
                ).node(
                    variable="us",
                ).execute()

            for keyword in concept.keywords:
                merge(connection=self.memgraph).node(
                    labels=KEYWORD_LABEL,
                    name=keyword,
                ).execute()
                merge(connection=self.memgraph).node(
                    labels=EMAIL_LABEL,
                    name=email_id,
                ).execute()
                merge(connection=self.memgraph).node(
                    labels=SOURCE_LABEL,
                    name=source,
                ).execute()

                match(connection=self.memgraph).node(
                    labels=CONCEPT_LABEL,
                    name=concept.name,
                    variable="kd",
                ).match().node(
                    labels=KEYWORD_LABEL,
                    name=keyword,
                    variable="ks",
                ).match().node(
                    labels=EMAIL_LABEL,
                    name=email_id,
                    variable="es",
                ).match().node(
                    labels=SOURCE_LABEL,
                    name=source,
                    variable="ss",
                ).merge().node(
                    variable="ks",
                ).to(
                    relationship_type=REPRESENTS_RELATIONSHIP,
                ).node(
                    variable="kd",
                ).merge().node(
                    variable="es",
                ).to(
                    relationship_type=CONTAINS_RELATIONSHIP,
                ).node(
                    variable="ks",
                ).merge().node(
                    variable="ss",
                ).to(
                    relationship_type=SENDS_RELATIONSHIP,
                ).node(
                    variable="es",
                ).execute()

    def _extract_website_from_url(self, url: str) -> str:
        """Extract the website from a URL."""
        if url.startswith("http://"):
            url = url[len("http://") :]
        elif url.startswith("https://"):
            url = url[len("https://") :]
        return url.split("/")[0]
