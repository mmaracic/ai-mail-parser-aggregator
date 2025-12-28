"""Wrapper for Large Language Model (LLM) interactions."""

import json
import logging

from litellm import Choices, ModelResponse, Usage, completion
from pydantic import BaseModel

from service.database.knowledge_database import KnowledgeConcept

logger = logging.getLogger(__name__)


class KnowledgeConceptResponse(BaseModel):
    """A model representing the response containing knowledge concepts."""

    concepts: list[KnowledgeConcept] = []


class MeteredKnowledgeConceptResponse(KnowledgeConceptResponse):
    """A model representing the metered response containing knowledge concepts."""

    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int
    model: str
    provider: str


class KnowledgeExtractionLLM:
    """A wrapper class for interacting with a large language model (LLM)."""

    def __init__(
        self,
        model: str,
        api_key: str,
        prompt: str,
    ) -> None:
        """Initialize the LLM wrapper with API key and prompt."""
        self.model = model
        self.api_key = api_key
        self.prompt = prompt

    def get_response(self, query: str) -> MeteredKnowledgeConceptResponse:
        """Get a response from the LLM for a given query."""
        response: ModelResponse = completion(
            model=self.model,
            messages=[
                {"content": self.prompt, "role": "system"},
                {"content": query, "role": "user"},
            ],
            stream=False,
            api_key=self.api_key,
            response_format=KnowledgeConceptResponse,
        )
        choices: Choices = response.choices[0]
        structured_response: KnowledgeConceptResponse = KnowledgeConceptResponse(
            **json.loads(
                choices.message.content,
            )
        )
        usage: Usage = response.usage
        model = response.model
        provider: str = response.provider
        return MeteredKnowledgeConceptResponse(
            concepts=structured_response.concepts,
            total_tokens=usage.total_tokens,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cached_tokens=usage.prompt_tokens_details.cached_tokens,
            model=model,
            provider=provider,
        )
