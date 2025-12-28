"""Abstract base class for text processing services."""

from abc import ABC, abstractmethod
from datetime import UTC, datetime

from bs4 import BeautifulSoup
from pydantic import BaseModel

from service.util import calculate_savings


class TextProcessor(ABC):
    """Abstract base class for text processing services."""

    def __str__(self) -> str:
        """Return the name of the text processor."""
        return self.__class__.__name__

    @abstractmethod
    def process_text(self, text: str, source: str) -> str:
        """Process the input text and return the processed text.

        Args:
            text (str): The input text to process.
            source (str): The source identifier of the text.

        Returns:
            str: The processed text.

        """
        ...


class ProcessingAudit(BaseModel):
    """A record of a text processing audit."""

    processor_name: str
    start_text_size: int
    end_text_size: int
    savings_percentage: float
    processing_duration_seconds: float
    tokens_used: int = 0


class TextProcessorWrapper:
    """A wrapper for text processors to add additional functionality."""

    def __init__(self, processors: list[TextProcessor]):
        self.processors = processors

    def process(self, text: str, source: str) -> tuple[str, list[ProcessingAudit]]:
        """Process the text using the wrapped processor.

        Args:
            text (str): The input text to process.
            source (str): The source identifier of the text.

        Returns:
            str: The processed text.

        """
        audits: list[ProcessingAudit] = []
        input: str = text
        for processor in self.processors:
            start_size = len(input)
            start_time = datetime.now(tz=UTC)
            output = processor.process_text(input, source)
            end_time = datetime.now(tz=UTC)
            end_size = len(output)
            audits.append(
                ProcessingAudit(
                    processor_name=str(processor),
                    start_text_size=start_size,
                    end_text_size=end_size,
                    savings_percentage=calculate_savings(start_size, end_size),
                    processing_duration_seconds=(end_time - start_time).total_seconds(),
                )
            )
            input = output
        return input, audits


class HtmlProcessor(TextProcessor):
    """A text processor that processes HTML content."""

    def process_text(self, text: str, source: str) -> str:
        """Process the input HTML text and return the processed text.

        Args:
            text (str): The input HTML text to process.
            source (str): The source identifier of the text.

        Returns:
            str: The processed text.

        """
        # Clean HTML with BeautifulSoup
        soup = BeautifulSoup(text, "html.parser")

        # Extract text content
        return soup.get_text(separator="\n", strip=True)
