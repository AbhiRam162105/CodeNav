"""
Conversation history management for the agent.
"""
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class HistoryManager:
    """Manages conversation history with token budgets."""

    def __init__(self):
        """Initialize empty history."""
        self.messages: List[Dict[str, str]] = []
        self.original_task: str = ""

    def add_user(self, text: str):
        """Add a user message."""
        self.messages.append({
            "role": "user",
            "content": text
        })

        # Remember the first task
        if not self.original_task:
            self.original_task = text

    def add_model(self, text: str):
        """Add a model/assistant message."""
        self.messages.append({
            "role": "assistant",
            "content": text
        })

    def add_tool_result(self, tool_name: str, result: str):
        """
        Add a tool result as a user message.

        Args:
            tool_name: Name of the tool that was executed
            result: Result string from the tool
        """
        content = f"[Tool: {tool_name}]\n{result}"
        self.add_user(content)

    def get_messages(self) -> List[Dict[str, str]]:
        """
        Get all messages.

        Returns:
            List of message dicts
        """
        return self.messages

    def trim_to_budget(self, max_tokens: int):
        """
        Trim history to fit within token budget.

        Estimates tokens as characters / 3.5.
        Keeps the original task (first message) always.

        Args:
            max_tokens: Maximum tokens allowed
        """
        if not self.messages:
            return

        # Estimate tokens
        total_chars = sum(len(msg["content"]) for msg in self.messages)
        estimated_tokens = total_chars / 3.5

        if estimated_tokens <= max_tokens:
            return  # Already under budget

        logger.info(f"Trimming history from ~{int(estimated_tokens)} to {max_tokens} tokens")

        # Keep first message (original task) and recent messages
        if len(self.messages) <= 2:
            return  # Can't trim further

        # Remove oldest messages (except first)
        target_chars = max_tokens * 3.5
        current_chars = 0

        # Always keep first message
        kept_messages = [self.messages[0]]
        current_chars += len(self.messages[0]["content"])

        # Add recent messages from the end
        for msg in reversed(self.messages[1:]):
            msg_chars = len(msg["content"])
            if current_chars + msg_chars > target_chars:
                break

            kept_messages.insert(1, msg)  # Insert after first message
            current_chars += msg_chars

        self.messages = kept_messages
        logger.info(f"Trimmed to {len(self.messages)} messages")

    def get_last_n_messages(self, n: int) -> List[Dict[str, str]]:
        """
        Get the last N messages.

        Args:
            n: Number of messages to retrieve

        Returns:
            List of last N message dicts
        """
        if n <= 0:
            return []

        return self.messages[-n:]

    def clear(self):
        """Clear all messages."""
        self.messages = []
        self.original_task = ""

    def __len__(self) -> int:
        """Get number of messages."""
        return len(self.messages)
