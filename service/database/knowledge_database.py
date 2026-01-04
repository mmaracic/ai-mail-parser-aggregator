"""Module for managing a knowledge database."""

import logging
from datetime import datetime

from gqlalchemy import Memgraph, match, merge
from gqlalchemy.query_builders.memgraph_query_builder import Operator
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
        self.create_constraints_and_indexes()

    def create_constraints_and_indexes(self) -> None:
        """Create constraints and indexes for the knowledge database."""
        logger.info("Creating constraints and indexes for the knowledge database")
        # Create uniqueness constraints
        self.memgraph.execute(
            f"CREATE CONSTRAINT ON (c:{CONCEPT_LABEL}) ASSERT c.{NAME_PROPERTY} IS UNIQUE;"
        )
        self.memgraph.execute(
            f"CREATE CONSTRAINT ON (k:{KEYWORD_LABEL}) ASSERT k.{NAME_PROPERTY} IS UNIQUE;"
        )
        self.memgraph.execute(
            f"CREATE CONSTRAINT ON (u:{URL_LABEL}) ASSERT u.{NAME_PROPERTY} IS UNIQUE;"
        )
        self.memgraph.execute(
            f"CREATE CONSTRAINT ON (w:{WEBSITE_LABEL}) ASSERT w.{NAME_PROPERTY} IS UNIQUE;"
        )
        self.memgraph.execute(
            f"CREATE CONSTRAINT ON (e:{EMAIL_LABEL}) ASSERT e.{NAME_PROPERTY} IS UNIQUE;"
        )
        self.memgraph.execute(
            f"CREATE CONSTRAINT ON (s:{SOURCE_LABEL}) ASSERT s.{NAME_PROPERTY} IS UNIQUE;"
        )
        # Create indexes
        self.memgraph.execute(f"CREATE INDEX ON :{CONCEPT_LABEL}({NAME_PROPERTY});")
        self.memgraph.execute(f"CREATE INDEX ON :{KEYWORD_LABEL}({NAME_PROPERTY});")
        self.memgraph.execute(f"CREATE INDEX ON :{URL_LABEL}({NAME_PROPERTY});")
        self.memgraph.execute(f"CREATE INDEX ON :{WEBSITE_LABEL}({NAME_PROPERTY});")
        self.memgraph.execute(f"CREATE INDEX ON :{EMAIL_LABEL}({NAME_PROPERTY});")
        self.memgraph.execute(f"CREATE INDEX ON :{SOURCE_LABEL}({NAME_PROPERTY});")
        logger.info("Constraints and indexes created")

    def add_knowledge(
        self,
        concepts: list[KnowledgeConcept],
        email_id: str,
        email_datetime: datetime,
        source: str,
    ) -> None:
        """Add a piece of knowledge to the database."""
        for concept in concepts:
            merge(connection=self.memgraph).node(
                labels=[CONCEPT_LABEL, self.database],
                name=concept.name,
                topic=concept.topic,
                variable="n",
            ).add_custom_cypher(CUSTOM_CQL_ON_CREATE).set_(
                item=f"n.{CREATED_AT_PROPERTY}",
                operator=Operator.ASSIGNMENT,
                literal=f"{email_datetime.isoformat()}",
            ).execute()
            for url in concept.urls:
                website = self._extract_website_from_url(url)
                merge(connection=self.memgraph).node(
                    labels=[URL_LABEL, self.database],
                    name=url,
                    variable="n",
                ).add_custom_cypher(CUSTOM_CQL_ON_CREATE).set_(
                    item=f"n.{CREATED_AT_PROPERTY}",
                    operator=Operator.ASSIGNMENT,
                    literal=f"{email_datetime.isoformat()}",
                ).execute()
                merge(connection=self.memgraph).node(
                    labels=[WEBSITE_LABEL, self.database],
                    name=website,
                    variable="n",
                ).add_custom_cypher(CUSTOM_CQL_ON_CREATE).set_(
                    item=f"n.{CREATED_AT_PROPERTY}",
                    operator=Operator.ASSIGNMENT,
                    literal=f"{email_datetime.isoformat()}",
                ).execute()

                match(connection=self.memgraph).node(
                    labels=[CONCEPT_LABEL, self.database],
                    name=concept.name,
                    variable="ud",
                ).match().node(
                    labels=[URL_LABEL, self.database],
                    name=url,
                    variable="us",
                ).match().node(
                    labels=[WEBSITE_LABEL, self.database],
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
                    labels=[KEYWORD_LABEL, self.database],
                    name=keyword,
                    variable="n",
                ).add_custom_cypher(CUSTOM_CQL_ON_CREATE).set_(
                    item=f"n.{CREATED_AT_PROPERTY}",
                    operator=Operator.ASSIGNMENT,
                    literal=f"{email_datetime.isoformat()}",
                ).execute()
                merge(connection=self.memgraph).node(
                    labels=[EMAIL_LABEL, self.database],
                    name=email_id,
                    variable="n",
                ).add_custom_cypher(CUSTOM_CQL_ON_CREATE).set_(
                    item=f"n.{CREATED_AT_PROPERTY}",
                    operator=Operator.ASSIGNMENT,
                    literal=f"{email_datetime.isoformat()}",
                ).execute()
                merge(connection=self.memgraph).node(
                    labels=[SOURCE_LABEL, self.database],
                    name=source,
                    variable="n",
                ).add_custom_cypher(CUSTOM_CQL_ON_CREATE).set_(
                    item=f"n.{CREATED_AT_PROPERTY}",
                    operator=Operator.ASSIGNMENT,
                    literal=f"{email_datetime.isoformat()}",
                ).execute()

                match(connection=self.memgraph).node(
                    labels=[CONCEPT_LABEL, self.database],
                    name=concept.name,
                    variable="kd",
                ).match().node(
                    labels=[KEYWORD_LABEL, self.database],
                    name=keyword,
                    variable="ks",
                ).match().node(
                    labels=[EMAIL_LABEL, self.database],
                    name=email_id,
                    variable="es",
                ).match().node(
                    labels=[SOURCE_LABEL, self.database],
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
