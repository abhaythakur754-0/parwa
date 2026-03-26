"""
PARWA HyDE (Hypothetical Document Embeddings) Generator.

Implements HyDE technique for improved retrieval by generating
hypothetical documents that would answer the user's query,
then using those for similarity search.
"""
from typing import Optional, Dict, Any, List, Callable
from uuid import UUID
from datetime import datetime, timezone
import json

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class HyDEResult(BaseModel):
    """
    Result from HyDE generation.
    """
    query: str
    hypothetical_document: str
    embedding: Optional[List[float]] = None
    generation_model: Optional[str] = None
    tokens_used: int = Field(default=0)

    model_config = ConfigDict(
        use_enum_values=True)


class HyDEConfig(BaseModel):
    """
    Configuration for HyDE Generator.
    """
    max_hypothetical_length: int = Field(default=500, ge=50, le=2000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    include_query_context: bool = Field(default=True)
    generation_style: str = Field(default="detailed")  # detailed, concise, technical

    model_config = ConfigDict(
        use_enum_values=True)


class HyDEGenerator:
    """
    HyDE (Hypothetical Document Embeddings) Generator.

    Features:
    - Generate hypothetical documents from queries
    - Multiple generation styles
    - Company-specific context injection
    - Token usage tracking
    - Fallback for generation failures
    """

    DEFAULT_SYSTEM_PROMPT = """You are an expert document generator. Given a user query, generate a hypothetical document that would perfectly answer that query. The document should be informative, accurate, and written in a professional tone."""

    GENERATION_TEMPLATES = {
        "detailed": """Based on the query: "{query}"

Generate a comprehensive document that answers this query. Include:
1. A clear introduction to the topic
2. Key points and details
3. Relevant examples if applicable
4. A conclusion or summary

Document:""",
        "concise": """Query: "{query}"

Generate a brief, focused document that directly addresses this query:

Document:""",
        "technical": """Technical Query: "{query}"

Generate a technical document with specifications, procedures, or detailed explanations:

Technical Document:""",
    }

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        embedding_fn: Optional[Callable[[str], List[float]]] = None,
        config: Optional[HyDEConfig] = None,
        company_context: Optional[str] = None
    ) -> None:
        """
        Initialize HyDE Generator.

        Args:
            llm_client: LLM client for generation (e.g., OpenAI, LangChain)
            embedding_fn: Function to generate embeddings
            config: HyDE configuration
            company_context: Company-specific context to include
        """
        self.llm_client = llm_client
        self.embedding_fn = embedding_fn
        self.config = config or HyDEConfig()
        self.company_context = company_context

        self._generation_count = 0
        self._total_tokens_used = 0

        logger.info({
            "event": "hyde_generator_initialized",
            "generation_style": self.config.generation_style,
            "has_llm_client": llm_client is not None,
            "has_embedding_fn": embedding_fn is not None,
        })

    def generate(
        self,
        query: str,
        style: Optional[str] = None
    ) -> HyDEResult:
        """
        Generate a hypothetical document for the query.

        Args:
            query: User query
            style: Generation style (overrides config)

        Returns:
            HyDEResult with generated document

        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        style = style or self.config.generation_style

        # Build prompt
        prompt = self._build_prompt(query, style)

        # Generate hypothetical document
        hypothetical_doc = self._generate_document(prompt, query)

        # Generate embedding for the hypothetical document
        embedding = None
        if self.embedding_fn:
            try:
                embedding = self.embedding_fn(hypothetical_doc)
            except Exception as e:
                logger.error({
                    "event": "hyde_embedding_failed",
                    "error": str(e),
                })

        self._generation_count += 1

        logger.info({
            "event": "hyde_generated",
            "query_length": len(query),
            "document_length": len(hypothetical_doc),
            "style": style,
            "has_embedding": embedding is not None,
        })

        return HyDEResult(
            query=query,
            hypothetical_document=hypothetical_doc,
            embedding=embedding,
            generation_model=getattr(self.llm_client, "model_name", None) if self.llm_client else None,
            tokens_used=len(hypothetical_doc.split())  # Approximate
        )

    def generate_batch(
        self,
        queries: List[str],
        style: Optional[str] = None
    ) -> List[HyDEResult]:
        """
        Generate hypothetical documents for multiple queries.

        Args:
            queries: List of queries
            style: Generation style (overrides config)

        Returns:
            List of HyDEResult
        """
        results: List[HyDEResult] = []

        for query in queries:
            try:
                result = self.generate(query, style=style)
                results.append(result)
            except Exception as e:
                logger.error({
                    "event": "hyde_batch_error",
                    "query": query[:50],
                    "error": str(e),
                })
                # Append a minimal result for failed generations
                results.append(HyDEResult(
                    query=query,
                    hypothetical_document="",
                    tokens_used=0
                ))

        return results

    def get_embedding_for_query(self, query: str) -> Optional[List[float]]:
        """
        Get HyDE embedding for a query.

        Generates hypothetical document and returns its embedding.
        Useful for direct similarity search without storing the document.

        Args:
            query: User query

        Returns:
            Embedding vector if successful, None otherwise
        """
        result = self.generate(query)
        return result.embedding

    def get_stats(self) -> Dict[str, Any]:
        """
        Get HyDE generator statistics.

        Returns:
            Dict with generator stats
        """
        return {
            "generation_count": self._generation_count,
            "total_tokens_used": self._total_tokens_used,
            "average_tokens_per_generation": (
                self._total_tokens_used / self._generation_count
                if self._generation_count > 0 else 0
            ),
            "config": self.config.model_dump(),
            "has_llm_client": self.llm_client is not None,
            "has_embedding_fn": self.embedding_fn is not None,
        }

    def _build_prompt(self, query: str, style: str) -> str:
        """
        Build the generation prompt.

        Args:
            query: User query
            style: Generation style

        Returns:
            Formatted prompt
        """
        template = self.GENERATION_TEMPLATES.get(
            style, self.GENERATION_TEMPLATES["detailed"]
        )

        prompt = template.format(query=query)

        # Add company context if available
        if self.company_context and self.config.include_query_context:
            prompt = f"Company Context: {self.company_context}\n\n{prompt}"

        return prompt

    def _generate_document(self, prompt: str, original_query: str) -> str:
        """
        Generate the hypothetical document.

        Args:
            prompt: Generation prompt
            original_query: Original query for fallback

        Returns:
            Generated document text
        """
        # If LLM client available, use it
        if self.llm_client:
            try:
                return self._call_llm(prompt)
            except Exception as e:
                logger.warning({
                    "event": "hyde_llm_call_failed",
                    "error": str(e),
                    "using_fallback": True,
                })

        # Fallback: Generate a simple hypothetical document
        return self._fallback_generation(original_query)

    def _call_llm(self, prompt: str) -> str:
        """
        Call the LLM to generate document.

        Args:
            prompt: Generation prompt

        Returns:
            Generated text
        """
        if hasattr(self.llm_client, "generate"):
            # LangChain-style interface
            response = self.llm_client.generate(prompt)
            return response

        if hasattr(self.llm_client, "invoke"):
            # LangChain Runnable interface
            response = self.llm_client.invoke(prompt)
            return response.content if hasattr(response, "content") else str(response)

        if hasattr(self.llm_client, "chat") and hasattr(self.llm_client.chat, "completions"):
            # OpenAI-style interface
            response = self.llm_client.chat.completions.create(
                model=getattr(self.llm_client, "model_name", "gpt-3.5-turbo"),
                messages=[
                    {"role": "system", "content": self.DEFAULT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config.max_hypothetical_length,
                temperature=self.config.temperature
            )
            return response.choices[0].message.content

        # Generic callable
        if callable(self.llm_client):
            return str(self.llm_client(prompt))

        raise ValueError("Unsupported LLM client interface")

    def _fallback_generation(self, query: str) -> str:
        """
        Fallback document generation when LLM is unavailable.

        Args:
            query: Original query

        Returns:
            Simple hypothetical document
        """
        # Create a basic document structure based on the query
        doc_parts = [
            f"Information regarding: {query}",
            "",
            "This document addresses the query about the mentioned topic.",
            "Key points include relevant details, context, and specific information",
            "that would help answer the user's question comprehensively.",
            "",
            "The topic has been researched and the following details are provided:",
            f"- Context and background information about {query}",
            "- Specific details and relevant data points",
            "- Recommendations and next steps if applicable",
            "",
            "This information is intended to provide a complete answer to the query."
        ]

        return "\n".join(doc_parts)
