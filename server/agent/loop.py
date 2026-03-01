"""
Agent loop for multi-turn interactions with tool use.
"""
import logging
from typing import Dict, List

from agent.llm_client import get_client
from agent.prompts import build_system_prompt
from agent.tool_parser import parse_tool_call, extract_text_before_tool_call
from agent.tool_executor import execute_tool, SENTINEL_ASK_USER, SENTINEL_FINISH
from agent.history import HistoryManager

logger = logging.getLogger(__name__)


def run_agent(
    task: str,
    state,
    max_iterations: int = 10,
    max_tokens: int = 2048
) -> Dict:
    """
    Run the agent loop for a task.

    Args:
        task: User's task description
        state: Application state (app_state)
        max_iterations: Maximum number of turns
        max_tokens: Max tokens per LLM call

    Returns:
        Result dict with status, response, tool_calls_made, etc.
    """
    # Initialize
    client = get_client()
    history = HistoryManager()
    tool_calls_made = []
    tokens_used_estimate = 0
    iterations_log = []  # Track thinking progress for UI

    # Build system prompt
    codemap_summary = {
        "function_count": state.codemap.get("function_count", 0) if state.codemap else 0,
        "file_count": state.codemap.get("file_count", 0) if state.codemap else 0,
    }
    system_prompt = build_system_prompt(codemap_summary)

    # Add initial task
    history.add_user(task)

    # Agent loop
    for iteration in range(max_iterations):
        logger.info(f"Agent iteration {iteration + 1}/{max_iterations}")

        iteration_data = {
            "iteration": iteration + 1,
            "max_iterations": max_iterations,
            "thinking": None,
            "tool_call": None,
            "tool_result": None
        }

        # Trim history to budget
        history.trim_to_budget(max_tokens // 2)  # Leave room for response

        # Get messages
        messages = history.get_messages()

        # Call LLM
        try:
            response = client.invoke(
                system_prompt=system_prompt,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.2
            )

            tokens_used_estimate += len(response) // 4  # Rough estimate

        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return {
                "status": "error",
                "response": f"Error: {str(e)}",
                "tool_calls_made": tool_calls_made,
                "tokens_used": tokens_used_estimate,
                "iterations": iterations_log
            }

        # Add model response to history
        history.add_model(response)

        # Check for tool call
        tool_call = parse_tool_call(response)

        if tool_call:
            # Extract any text before the tool call
            text_before = extract_text_before_tool_call(response)
            if text_before:
                logger.info(f"Model said: {text_before}")
                iteration_data["thinking"] = text_before

            tool_name = tool_call["name"]
            logger.info(f"Tool call: {tool_name}")
            iteration_data["tool_call"] = {
                "name": tool_name,
                "params": tool_call.get("params", {})
            }

            # Execute tool
            try:
                result = execute_tool(tool_call, state)

                # Record tool call
                tool_calls_made.append({
                    "tool": tool_name,
                    "params": tool_call.get("params", {}),
                    "result": result[:200] + "..." if len(result) > 200 else result
                })

                # Add result to iteration log
                iteration_data["tool_result"] = result[:500] + "..." if len(result) > 500 else result

            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}")
                result = f"Error executing tool: {str(e)}"
                iteration_data["tool_result"] = result

            # Add iteration to log
            iterations_log.append(iteration_data)

            # Check for special sentinels
            if result.startswith(SENTINEL_ASK_USER):
                question = result[len(SENTINEL_ASK_USER):]
                return {
                    "status": "needs_input",
                    "question": question,
                    "tool_calls_made": tool_calls_made,
                    "tokens_used": tokens_used_estimate,
                    "iterations": iterations_log
                }

            if result.startswith(SENTINEL_FINISH):
                final_response = result[len(SENTINEL_FINISH):]
                return {
                    "status": "complete",
                    "response": final_response,
                    "tool_calls_made": tool_calls_made,
                    "tokens_used": tokens_used_estimate,
                    "iterations": iterations_log
                }

            # Add tool result to history
            history.add_tool_result(tool_name, result)

        else:
            # No tool call - model is thinking/explaining
            iteration_data["thinking"] = response
            iterations_log.append(iteration_data)

            # Check if response looks like completion
            if any(phrase in response.lower() for phrase in [
                "i've completed",
                "task is complete",
                "i've finished",
                "done",
                "successfully applied"
            ]):
                return {
                    "status": "complete",
                    "response": response,
                    "tool_calls_made": tool_calls_made,
                    "tokens_used": tokens_used_estimate,
                    "iterations": iterations_log
                }

            # Otherwise continue (model might be explaining something)
            continue

    # Max iterations reached
    logger.warning(f"Max iterations ({max_iterations}) reached")

    # Get last model response
    last_messages = history.get_last_n_messages(1)
    last_response = last_messages[0]["content"] if last_messages else "No response"

    return {
        "status": "max_iterations",
        "response": last_response,
        "tool_calls_made": tool_calls_made,
        "tokens_used": tokens_used_estimate,
        "iterations": iterations_log
    }
