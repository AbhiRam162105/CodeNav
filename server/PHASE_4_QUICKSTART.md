# Phase 4 Quick Start Guide

## Prerequisites

1. **Gemini API Key:** Ensure your `.env` file has:
   ```bash
   GEMINI_API_KEY=AIzaSyC1GCaKdYZhNakdSSJoMlAmRJMPvS4I-eo
   ```

2. **Python Dependencies:** Install if not already done:
   ```bash
   cd server
   pip install -r requirements.txt
   ```

## Quick Test

### 1. Start the Server

```bash
cd server
python main.py
```

The server will start on `http://localhost:8765`

### 2. Open a Project

```bash
curl -X POST "http://localhost:8765/project/open" \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/your/project"}'
```

### 3. Start Indexing

```bash
curl -X POST "http://localhost:8765/index/start"
```

Wait for indexing to complete (check status):

```bash
curl "http://localhost:8765/index/status"
```

### 4. Test Agent Query (Synchronous)

```bash
curl -X POST "http://localhost:8765/agent/query" \
  -H "Content-Type: application/json" \
  -d 'task=Find all authentication functions&max_iterations=5'
```

Response format:
```json
{
  "status": "complete",
  "response": "I found 3 authentication functions: ...",
  "tool_calls_made": [
    {
      "tool": "search_codebase",
      "params": {"query": "authentication functions"},
      "result": "Search results for 'authentication functions':\n1. ..."
    }
  ],
  "tokens_used": 842
}
```

### 5. Test Agent Stream (WebSocket)

Create a test script `test_agent_stream.py`:

```python
import asyncio
import websockets
import json

async def test_agent():
    uri = "ws://localhost:8765/agent/stream"

    async with websockets.connect(uri) as websocket:
        # Send task
        task_data = {
            "task": "Search for all functions that handle file reading",
            "max_iterations": 5,
            "max_tokens": 2048
        }

        await websocket.send(json.dumps(task_data))

        # Receive events
        print("Receiving agent events...")
        print("-" * 50)

        async for message in websocket:
            event = json.loads(message)
            event_type = event["type"]
            data = event["data"]

            if event_type == "start":
                print(f"🚀 Starting task: {data['task']}")

            elif event_type == "iteration":
                print(f"\n🔄 Iteration {data['iteration']}/{data['max_iterations']}")

            elif event_type == "chunk":
                print(data["text"], end="", flush=True)

            elif event_type == "thinking":
                print(f"\n💭 {data['text']}")

            elif event_type == "tool_call":
                print(f"\n🔧 Tool: {data['tool']}")
                print(f"   Params: {data['params']}")

            elif event_type == "tool_result":
                print(f"✅ Result: {data['result'][:100]}...")

            elif event_type == "complete":
                print(f"\n\n✨ Complete!")
                print(f"Response: {data['response']}")
                print(f"Tools used: {len(data['tool_calls_made'])}")
                print(f"Tokens: {data['tokens_used']}")
                break

            elif event_type == "needs_input":
                print(f"\n❓ Question: {data['question']}")
                break

            elif event_type == "error":
                print(f"\n❌ Error: {data['message']}")
                break

if __name__ == "__main__":
    asyncio.run(test_agent())
```

Run it:
```bash
python test_agent_stream.py
```

## Example Tasks to Try

### 1. Search Task
```bash
curl -X POST "http://localhost:8765/agent/query?task=Find%20all%20functions%20that%20use%20async/await"
```

### 2. Read and Analyze
```bash
curl -X POST "http://localhost:8765/agent/query?task=Read%20the%20main.py%20file%20and%20summarize%20what%20it%20does"
```

### 3. Code Modification
```bash
curl -X POST "http://localhost:8765/agent/query?task=Add%20error%20handling%20to%20the%20read_file%20function"
```

Note: The agent will search, read, and generate a diff, but won't apply it automatically (you'd need to approve first in a real implementation).

## Testing the Agent Loop

Run the automated tests:

```bash
cd server
pytest tests/test_agent.py -v
```

Expected output:
```
tests/test_agent.py::TestToolParser::test_parse_tool_call_valid PASSED
tests/test_agent.py::TestToolParser::test_parse_tool_call_no_tool PASSED
tests/test_agent.py::TestToolExecutor::test_execute_read_lines PASSED
tests/test_agent.py::TestToolExecutor::test_execute_apply_diff PASSED
tests/test_agent.py::TestHistoryManager::test_add_messages PASSED
tests/test_agent.py::TestHistoryManager::test_trim_to_budget PASSED
tests/test_agent.py::TestAgentLoop::test_run_agent_finish PASSED
...
```

## Verifying Each Component

### 1. LLM Client
```python
from agent.llm_client import get_client

client = get_client()
response = client.invoke(
    system_prompt="You are a helpful assistant.",
    messages=[{"role": "user", "content": "Say hello!"}],
    max_tokens=100
)
print(response)
```

### 2. Tool Parser
```python
from agent.tool_parser import parse_tool_call

text = '<tool_call>{"name": "search_codebase", "params": {"query": "auth"}}</tool_call>'
tool_call = parse_tool_call(text)
print(tool_call)
```

### 3. Tool Executor
```python
from agent.tool_executor import execute_tool
from state import app_state

# Assuming project is open and indexed
tool_call = {
    "name": "search_codebase",
    "params": {"query": "authentication", "top_k": 3}
}
result = execute_tool(tool_call, app_state)
print(result)
```

### 4. History Manager
```python
from agent.history import HistoryManager

history = HistoryManager()
history.add_user("Find auth functions")
history.add_model("Let me search...")
history.add_tool_result("search_codebase", "Results: ...")

messages = history.get_messages()
for msg in messages:
    print(f"{msg['role']}: {msg['content'][:50]}...")
```

## Troubleshooting

### Issue: "Index not ready"
**Solution:** Make sure you've started indexing and it's complete:
```bash
curl "http://localhost:8765/index/status"
```

### Issue: "Gemini API error"
**Solution:** Check your API key in `.env` and verify it's valid:
```bash
cat .env | grep GEMINI_API_KEY
```

Test the key manually:
```python
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-2.0-flash-exp")
response = model.generate_content("Say hello")
print(response.text)
```

### Issue: "No project opened"
**Solution:** Open a project first:
```bash
curl -X POST "http://localhost:8765/project/open" \
  -H "Content-Type: application/json" \
  -d '{"path": "'"$(pwd)"'"}'
```

### Issue: Tests failing with import errors
**Solution:** Ensure all dependencies are installed:
```bash
pip install -r requirements.txt
```

## What's Working

✅ Agent can search codebase semantically
✅ Agent can read specific files and line ranges
✅ Agent can retrieve context via graph traversal
✅ Agent can generate and apply diffs
✅ Agent can create new files
✅ Agent can ask clarifying questions
✅ Agent can finish tasks with responses
✅ Multi-turn conversations with history management
✅ Token budget enforcement
✅ Streaming WebSocket interface
✅ Synchronous REST interface

## What's Not Yet Implemented

⏳ Command execution (`run_command` tool) - Phase 5
⏳ Session persistence - Phase 5
⏳ Task cancellation - Phase 5
⏳ Multi-user support - Later phase

## Next Steps

Once you've verified Phase 4 is working:
1. Try some real coding tasks
2. Test the streaming interface
3. Observe token usage and efficiency
4. Move on to Phase 5 (Execution Layer)

---

**Happy Testing! 🚀**
