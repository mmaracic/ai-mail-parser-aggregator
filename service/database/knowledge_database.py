"""Module for managing a knowledge database."""

import logging
from datetime import datetime

from neo4j import GraphDatabase
from pydantic import BaseModel

logger = logging.getLogger(__name__)

CONCEPT_LABEL = "Concept"
KEYWORD_LABEL = "Keyword"
URL_LABEL = "URL"
WEBSITE_LABEL = "Website"
EMAIL_LABEL = "Email"
SOURCE_LABEL = "Source"

NAME_PROPERTY = "name"
CREATED_AT_PROPERTY = "created_at"
URL_PROPERTY = "url"
TOPIC_PROPERTY = "topic"

REPRESENTS_RELATIONSHIP = "REPRESENTS"
DESCRIBES_RELATIONSHIP = "DESCRIBES"
CONTAINS_RELATIONSHIP = "CONTAINS"
HOSTS_RELATIONSHIP = "HOSTS"
SENDS_RELATIONSHIP = "SENDS"

CUSTOM_CQL_ON_CREATE = "ON CREATE"


class KnowledgeConcept(BaseModel):
    """A model representing a knowledge concept."""

    name: str
    topic: str
    urls: list[str]
    keywords: list[str]


class KnowledgeDatabase:
    """A simple knowledge database class.

    Args:
        host (str): The host of the knowledge database.
        port (int): The port of the knowledge database.
        username (str): The username for the knowledge database.
        password (str): The password for the knowledge database.
        encrypted (bool): Whether the connection is encrypted.
        database (str): The name of the database to use.

    Common Cypher queries:
    - Count all nodes: MATCH (n) RETURN count(n)
    - Delete all nodes: MATCH (n) DETACH DELETE n
    - Return all nodes (limited): MATCH (n) RETURN n LIMIT 200
    - Return all nodes with relationships (limited): MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 200
    - Return all concepts within a time range:
        MATCH (c:Concept)
        WHERE datetime(c.created_at) >= datetime('2025-12-29T00:00:00Z')
        AND datetime(c.created_at) <= datetime('2025-12-29T23:59:59Z')
        RETURN c

    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        encrypted: bool,
        database: str,
    ) -> None:
        """Initialize the knowledge database."""
        logger.info("Connecting to knowledge database with encrypted=%s", encrypted)
        self.database = database
        uri = f"bolt://{host}:{port}"
        self.client = GraphDatabase.driver(
            uri=uri,
            auth=(username, password),
            encrypted=encrypted,
            trust="TRUST_ALL_CERTIFICATES",
        )
        self.bookmark_manager = GraphDatabase.bookmark_manager()
        # Test the connection
        # Equivalent to: MATCH (n) RETURN count(n);
        with self.client.session(
            default_access_mode="READ",
            bookmark_manager=self.bookmark_manager,
        ) as session:
            result = session.run("MATCH (n) RETURN count(n);").single().value()
            logger.info("%s nodes in the knowledge database", result)
        self.create_constraints_and_indexes()

    def create_constraints_and_indexes(self) -> None:
        """Create constraints and indexes for the knowledge database."""
        logger.info("Creating constraints and indexes for the knowledge database")

        with self.client.session(
            default_access_mode="WRITE",
            bookmark_manager=self.bookmark_manager,
        ) as session:
            # Create uniqueness constraints
            session.run(
                f"CREATE CONSTRAINT ON (c:{CONCEPT_LABEL}) ASSERT c.{NAME_PROPERTY} IS UNIQUE;"
            )
            session.run(
                f"CREATE CONSTRAINT ON (k:{KEYWORD_LABEL}) ASSERT k.{NAME_PROPERTY} IS UNIQUE;"
            )
            session.run(
                f"CREATE CONSTRAINT ON (u:{URL_LABEL}) ASSERT u.{NAME_PROPERTY} IS UNIQUE;"
            )
            session.run(
                f"CREATE CONSTRAINT ON (w:{WEBSITE_LABEL}) ASSERT w.{NAME_PROPERTY} IS UNIQUE;"
            )
            session.run(
                f"CREATE CONSTRAINT ON (e:{EMAIL_LABEL}) ASSERT e.{NAME_PROPERTY} IS UNIQUE;"
            )
            session.run(
                f"CREATE CONSTRAINT ON (s:{SOURCE_LABEL}) ASSERT s.{NAME_PROPERTY} IS UNIQUE;"
            )
            # Create indexes
            session.run(f"CREATE INDEX ON :{CONCEPT_LABEL}({NAME_PROPERTY});")
            session.run(f"CREATE INDEX ON :{KEYWORD_LABEL}({NAME_PROPERTY});")
            session.run(f"CREATE INDEX ON :{URL_LABEL}({NAME_PROPERTY});")
            session.run(f"CREATE INDEX ON :{WEBSITE_LABEL}({NAME_PROPERTY});")
            session.run(f"CREATE INDEX ON :{EMAIL_LABEL}({NAME_PROPERTY});")
            session.run(f"CREATE INDEX ON :{SOURCE_LABEL}({NAME_PROPERTY});")

        logger.info("Constraints and indexes created")

    def add_knowledge(
        self,
        concepts: list[KnowledgeConcept],
        email_id: str,
        email_datetime: datetime,
        source: str,
    ) -> None:
        """Add a piece of knowledge to the database."""
        created_at_iso = email_datetime.isoformat()

        with self.client.session(
            default_access_mode="WRITE",
            bookmark_manager=self.bookmark_manager,
        ) as session:
            for concept in concepts:
                # Merge Concept node
                session.run(
                    f"""
                    MERGE (c:{CONCEPT_LABEL}:{self.database} {{{NAME_PROPERTY}: $name}})
                    ON CREATE SET c.{TOPIC_PROPERTY} = $topic, c.{CREATED_AT_PROPERTY} = $created_at
                    """,
                    name=concept.name,
                    topic=concept.topic,
                    created_at=created_at_iso,
                )

                # Process URLs
                for url in concept.urls:
                    website = self._extract_website_from_url(url)

                    # Merge URL and Website nodes, create relationships
                    session.run(
                        f"""
                        MERGE (u:{URL_LABEL}:{self.database} {{{NAME_PROPERTY}: $url}})
                        ON CREATE SET u.{CREATED_AT_PROPERTY} = $created_at
                        MERGE (w:{WEBSITE_LABEL}:{self.database} {{{NAME_PROPERTY}: $website}})
                        ON CREATE SET w.{CREATED_AT_PROPERTY} = $created_at
                        WITH u, w
                        MATCH (c:{CONCEPT_LABEL}:{self.database} {{{NAME_PROPERTY}: $concept_name}})
                        MERGE (u)-[:{DESCRIBES_RELATIONSHIP}]->(c)
                        MERGE (w)-[:{HOSTS_RELATIONSHIP}]->(u)
                        """,
                        url=url,
                        website=website,
                        concept_name=concept.name,
                        created_at=created_at_iso,
                    )

                # Process keywords
                for keyword in concept.keywords:
                    # Merge Keyword, Email, and Source nodes, create relationships
                    session.run(
                        f"""
                        MERGE (k:{KEYWORD_LABEL}:{self.database} {{{NAME_PROPERTY}: $keyword}})
                        ON CREATE SET k.{CREATED_AT_PROPERTY} = $created_at
                        MERGE (e:{EMAIL_LABEL}:{self.database} {{{NAME_PROPERTY}: $email_id}})
                        ON CREATE SET e.{CREATED_AT_PROPERTY} = $created_at
                        MERGE (s:{SOURCE_LABEL}:{self.database} {{{NAME_PROPERTY}: $source}})
                        ON CREATE SET s.{CREATED_AT_PROPERTY} = $created_at
                        WITH k, e, s
                        MATCH (c:{CONCEPT_LABEL}:{self.database} {{{NAME_PROPERTY}: $concept_name}})
                        MERGE (k)-[:{REPRESENTS_RELATIONSHIP}]->(c)
                        MERGE (e)-[:{CONTAINS_RELATIONSHIP}]->(k)
                        MERGE (s)-[:{SENDS_RELATIONSHIP}]->(e)
                        """,
                        keyword=keyword,
                        email_id=email_id,
                        source=source,
                        concept_name=concept.name,
                        created_at=created_at_iso,
                    )

    def _extract_website_from_url(self, url: str) -> str:
        """Extract the website from a URL."""
        if url.startswith("http://"):
            url = url[len("http://") :]
        elif url.startswith("https://"):
            url = url[len("https://") :]
        return url.split("/")[0]
