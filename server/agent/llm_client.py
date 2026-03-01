"""
Gemini LLM client wrapper.
"""
import os
import time
import logging
from typing import List, Dict, Generator, Optional

logger = logging.getLogger(__name__)

# Singleton instance
_client_instance = None


class GeminiClient:
    """Wrapper around Google Generative AI for Gemini models."""

    def __init__(self, model_name: str = None):
        """
        Initialize the Gemini client.

        Args:
            model_name: Model to use (defaults to env var MODEL_NAME)
        """
        try:
            import google.generativeai as genai
            self.genai = genai
        except ImportError:
            logger.error("google-generativeai not installed")
            raise

        # Configure API key
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set in environment")

        genai.configure(api_key=api_key)

        # Set model
        self.model_name = model_name or os.getenv("MODEL_NAME", "gemini-2.0-flash-exp")
        self.model = genai.GenerativeModel(self.model_name)

        logger.info(f"Initialized Gemini client with model: {self.model_name}")

    def invoke(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.2
    ) -> str:
        """
        Send a request to Gemini and get the response.

        Args:
            system_prompt: System instruction
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Response text
        """
        # Retry configuration
        max_retries = 3
        retry_delays = [1, 2, 4]  # seconds

        for attempt in range(max_retries):
            try:
                # Create chat with system instruction
                chat = self.model.start_chat(
                    history=[]
                )

                # Build the prompt: system + conversation
                full_prompt = f"{system_prompt}\n\n"

                # Add conversation history
                for msg in messages:
                    role = msg["role"]
                    content = msg["content"]

                    if role == "user":
                        full_prompt += f"User: {content}\n\n"
                    elif role == "assistant" or role == "model":
                        full_prompt += f"Assistant: {content}\n\n"

                # Generate response
                response = chat.send_message(
                    full_prompt,
                    generation_config=self.genai.types.GenerationConfig(
                        max_output_tokens=max_tokens,
                        temperature=temperature,
                    )
                )

                return response.text

            except Exception as e:
                error_str = str(e).lower()

                # Check if it's a rate limit error
                if "resource" in error_str or "quota" in error_str or "429" in error_str:
                    if attempt < max_retries - 1:
                        delay = retry_delays[attempt]
                        logger.warning(f"Rate limited, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                        continue

                # Log and re-raise
                logger.error(f"Error calling Gemini: {e}")
                raise

        raise Exception("Max retries exceeded")

    def invoke_stream(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.2
    ) -> Generator[str, None, None]:
        """
        Stream response from Gemini.

        Args:
            system_prompt: System instruction
            messages: List of message dicts
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Yields:
            Response text chunks
        """
        try:
            # Create chat
            chat = self.model.start_chat(history=[])

            # Build prompt
            full_prompt = f"{system_prompt}\n\n"
            for msg in messages:
                role = msg["role"]
                content = msg["content"]

                if role == "user":
                    full_prompt += f"User: {content}\n\n"
                elif role == "assistant" or role == "model":
                    full_prompt += f"Assistant: {content}\n\n"

            # Generate with streaming
            response = chat.send_message(
                full_prompt,
                generation_config=self.genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                ),
                stream=True
            )

            # Yield chunks
            for chunk in response:
                if chunk.text:
                    yield chunk.text

        except Exception as e:
            logger.error(f"Error streaming from Gemini: {e}")
            raise


def get_client() -> GeminiClient:
    """
    Get or create the singleton Gemini client.

    Returns:
        GeminiClient instance
    """
    global _client_instance

    if _client_instance is None:
        _client_instance = GeminiClient()

    return _client_instance
