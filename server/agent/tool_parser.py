"""
Tool call parser for extracting structured tool calls from LLM responses.
"""
import re
import json
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


def parse_tool_call(text: str) -> Optional[Dict]:
    """
    Parse a tool call from text.

    Looks for XML-like tags: <tool_call>{"name": "...", "params": {...}}</tool_call>

    Args:
        text: Text potentially containing a tool call

    Returns:
        Dict with 'name' and 'params' keys, or None if no tool call found
    """
    # Pattern to match <tool_call>...</tool_call>
    pattern = r'<tool_call>(.*?)</tool_call>'

    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None

    # Extract the JSON content
    json_str = match.group(1).strip()

    try:
        # Parse JSON
        data = json.loads(json_str)

        # Validate structure
        if not isinstance(data, dict):
            logger.warning(f"Tool call is not a dict: {data}")
            return None

        if "name" not in data or "params" not in data:
            logger.warning(f"Tool call missing 'name' or 'params': {data}")
            return None

        return data

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse tool call JSON: {e}")
        logger.debug(f"Invalid JSON: {json_str}")
        return None


def extract_text_before_tool_call(text: str) -> str:
    """
    Extract the text that appears before the tool call.

    Args:
        text: Full text

    Returns:
        Text before the tool call, or entire text if no tool call
    """
    pattern = r'<tool_call>.*?</tool_call>'
    match = re.search(pattern, text, re.DOTALL)

    if match:
        return text[:match.start()].strip()

    return text.strip()


def extract_text_after_tool_call(text: str) -> str:
    """
    Extract text that appears after the tool call.

    Args:
        text: Full text

    Returns:
        Text after the tool call, or empty string if no tool call
    """
    pattern = r'<tool_call>.*?</tool_call>'
    match = re.search(pattern, text, re.DOTALL)

    if match:
        return text[match.end():].strip()

    return ""
