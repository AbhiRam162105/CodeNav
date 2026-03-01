# Quick Start Guide

Get CodeNav running in 3 minutes.

## Step 1: Install Dependencies (30 seconds)

```bash
# In the codenav/ directory
cd server
chmod +x setup.sh
./setup.sh
```

This creates a virtual environment and installs all Python packages.

## Step 2: Start the Server (10 seconds)

```bash
# Still in server/
source venv/bin/activate
python main.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8765
INFO:     Application startup complete.
```

## Step 3: Test It (2 minutes)

Open a new terminal and try these commands:

### 1. Health Check
```bash
curl http://localhost:8765/health
```

Expected output:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "project_root": null,
  "index_status": "idle"
}
```

### 2. Open a Project

Point it to any Python/JavaScript project on your machine:

```bash
curl -X POST http://localhost:8765/project/open \
  -H "Content-Type: application/json" \
  -d '{"path": "/Users/yourname/projects/some-project"}'
```

Or use the CodeNav project itself:

```bash
# Replace with your actual path
curl -X POST http://localhost:8765/project/open \
  -H "Content-Type: application/json" \
  -d '{"path": "/Users/abhiram/Desktop/CodeNav/codenav/server"}'
```

### 3. Index the Project

```bash
curl -X POST http://localhost:8765/index/start
```

Expected output:
```json
{
  "status": "started",
  "message": "Indexing started in background"
}
```

### 4. Check Progress

```bash
curl http://localhost:8765/index/status
```

Keep running this. You'll see:

```json
{
  "status": "indexing",
  "progress": 50,
  "function_count": 0,
  "file_count": 0
}
```

Then after a few seconds:

```json
{
  "status": "ready",
  "progress": 100,
  "function_count": 42,
  "file_count": 7
}
```

### 5. View the Codemap

```bash
# Check the .codenav directory was created
ls -la /path/to/your/project/.codenav/

# View the codemap
cat /path/to/your/project/.codenav/codemap.json | head -50
```

You should see a JSON file with all functions and their call relationships!

## Step 4: Try File Operations

### Get File Tree
```bash
curl http://localhost:8765/files/tree | jq '.'
```

### Read a File
```bash
curl "http://localhost:8765/files/read?path=main.py" | jq '.content'
```

### Write a File
```bash
curl -X POST http://localhost:8765/files/write \
  -H "Content-Type: application/json" \
  -d '{"path": "test.py", "content": "def hello():\n    print(\"Hello from CodeNav!\")\n"}'
```

## Step 5: Test File Watching

With the server still running:

1. Make a change to any Python file in the indexed project
2. Wait 2 seconds (debounce period)
3. Check the server logs - you should see:
   ```
   INFO: Processing 1 changed files
   INFO: Updated codemap for path/to/file.py
   ```

The codemap automatically updates!

## Troubleshooting

### "Module not found" errors

Make sure you're in the virtual environment:
```bash
cd server
source venv/bin/activate
which python  # Should show server/venv/bin/python
```

### "No such file or directory" when opening project

Use absolute paths:
```bash
pwd  # Get current directory
# Then use full path in the curl command
```

### Server won't start

Check if port 8765 is in use:
```bash
lsof -i :8765
# If something is using it, kill it or change SERVER_PORT in .env
```

## What's Next?

The call tree engine is working! Next phases will add:

- **Phase 3:** Semantic search with FAISS (find relevant functions by natural language)
- **Phase 4:** Gemini agent integration (AI-powered code analysis)
- **Phase 5:** Execution layer (run tests, execute commands)
- **Phase 6+:** VS Code extension with UI

But right now, you have a fully functional call graph extractor that:
- ✅ Parses Python and JavaScript/TypeScript
- ✅ Extracts all function definitions and calls
- ✅ Resolves call relationships
- ✅ Watches for changes and updates incrementally
- ✅ Provides a REST API for all operations

Try it on your own projects and see the call graph it generates!

## Interactive Testing with Swagger UI

Visit http://localhost:8765/docs in your browser for an interactive API explorer. You can:
- Try all endpoints with a nice UI
- See request/response schemas
- Test file operations visually

Much easier than curl!
