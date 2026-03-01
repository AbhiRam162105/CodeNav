"""
Task decomposition and planning for CodeNav agent.
"""
import logging
from typing import List, Dict, Any
from agent.llm_client import LLMClient

logger = logging.getLogger(__name__)


class TaskPlanner:
    """
    Decomposes user prompts into atomic tasks and elaborates requirements.
    Similar to how GitHub Copilot breaks down complex requests.
    """

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def elaborate_prompt(self, user_prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Elaborate a user prompt by asking clarifying questions and
        understanding requirements better.

        Args:
            user_prompt: The original user prompt
            context: Project context (codemap summary, etc.)

        Returns:
            Dict with elaborated requirements and questions
        """
        system_prompt = """You are a requirements analyst for a coding task.
Your job is to analyze user requests and identify:
1. What needs to be done
2. What information is missing
3. What clarifying questions to ask
4. Potential edge cases to consider

Be thorough but concise."""

        user_message = f"""User request: "{user_prompt}"

Project context:
- {context.get('function_count', 0)} functions across {context.get('file_count', 0)} files

Analyze this request and provide:
1. Main objective
2. Clarifying questions (if any)
3. Assumptions to verify
4. Success criteria

Format as JSON."""

        response = self.llm_client.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=1024
        )

        # Parse response (simplified - in production, use structured output)
        try:
            # Extract questions and requirements
            import json
            # Try to parse JSON from response
            elaboration = {
                "original_prompt": user_prompt,
                "analysis": response,
                "needs_clarification": "?" in response or "clarif" in response.lower()
            }
        except:
            elaboration = {
                "original_prompt": user_prompt,
                "analysis": response,
                "needs_clarification": False
            }

        return elaboration

    def decompose_into_tasks(self,
                            user_prompt: str,
                            elaboration: Dict[str, Any],
                            context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Decompose a user prompt into atomic tasks.

        Args:
            user_prompt: Original user prompt
            elaboration: Elaborated requirements
            context: Project context

        Returns:
            List of task dictionaries with:
            - id: Task ID
            - description: What to do
            - dependencies: Task IDs this depends on
            - type: Task type (search, read, edit, create, test, etc.)
            - estimated_complexity: low/medium/high
        """
        system_prompt = """You are a task planning expert for coding projects.
Break down complex requests into atomic, sequential tasks.

Each task should be:
- Small and focused (one clear action)
- Independent or have clear dependencies
- Testable/verifiable

Task types:
- search: Find relevant code
- read: Read specific files
- analyze: Understand code structure
- plan: Design solution
- edit: Modify existing code
- create: Create new files
- test: Run tests
- verify: Check results
- cleanup: Remove unnecessary code
"""

        user_message = f"""User request: "{user_prompt}"

Project context:
- {context.get('function_count', 0)} functions across {context.get('file_count', 0)} files

Analysis:
{elaboration.get('analysis', 'N/A')}

Break this down into atomic tasks. Output as JSON array with format:
[
  {{
    "id": "T1",
    "description": "Search for authentication-related functions",
    "dependencies": [],
    "type": "search",
    "estimated_complexity": "low"
  }},
  ...
]

Aim for 3-10 tasks. Be specific and actionable."""

        response = self.llm_client.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=2048
        )

        # Parse tasks from response
        tasks = self._parse_tasks(response)

        logger.info(f"Decomposed request into {len(tasks)} tasks")
        return tasks

    def _parse_tasks(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse tasks from LLM response.

        Args:
            response: LLM response containing tasks

        Returns:
            List of task dictionaries
        """
        import json
        import re

        # Try to extract JSON array from response
        try:
            # Look for JSON array in response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                tasks = json.loads(json_match.group(0))
                return tasks
        except json.JSONDecodeError:
            logger.warning("Failed to parse tasks as JSON, using fallback")

        # Fallback: Create simple task list from response lines
        tasks = []
        lines = response.strip().split('\n')
        task_id = 1

        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('-')):
                # Extract task description
                desc = re.sub(r'^[\d\-\.\)]+\s*', '', line)
                if desc:
                    tasks.append({
                        "id": f"T{task_id}",
                        "description": desc,
                        "dependencies": [] if task_id == 1 else [f"T{task_id-1}"],
                        "type": "general",
                        "estimated_complexity": "medium"
                    })
                    task_id += 1

        # Ensure at least one task
        if not tasks:
            tasks = [{
                "id": "T1",
                "description": response[:200],  # Use response as task
                "dependencies": [],
                "type": "general",
                "estimated_complexity": "medium"
            }]

        return tasks

    def create_execution_plan(self,
                             user_prompt: str,
                             context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a complete execution plan for a user request.
        This is the main entry point that combines elaboration and decomposition.

        Args:
            user_prompt: User's request
            context: Project context

        Returns:
            Execution plan with elaboration, tasks, and metadata
        """
        logger.info(f"Creating execution plan for: {user_prompt}")

        # Step 1: Elaborate the prompt
        elaboration = self.elaborate_prompt(user_prompt, context)

        # Step 2: Decompose into tasks
        tasks = self.decompose_into_tasks(user_prompt, elaboration, context)

        # Step 3: Build execution plan
        plan = {
            "user_prompt": user_prompt,
            "elaboration": elaboration,
            "tasks": tasks,
            "total_tasks": len(tasks),
            "status": "pending",
            "current_task_index": 0,
            "completed_tasks": [],
            "failed_tasks": []
        }

        logger.info(f"Created plan with {len(tasks)} tasks")
        return plan
