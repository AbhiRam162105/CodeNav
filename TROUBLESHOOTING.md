# CodeNav Troubleshooting Guide

## Setup Issues

### TypeScript Compilation Failing

If `npm run compile` fails:

1. **Install dependencies first:**
   ```bash
   cd /Users/abhiram/Desktop/CodeNav/codenav
   npm install
   ```

2. **Check for TypeScript errors:**
   ```bash
   npx tsc -p . --noEmit
   ```

3. **Clean and rebuild:**
   ```bash
   rm -rf node_modules out
   npm install
   npm run compile
   ```

### Server Not Starting

If the server fails to start:

1. **Check Python environment:**
   ```bash
   cd /Users/abhiram/Desktop/CodeNav/codenav/server
   source venv/bin/activate
   python -c "import fastapi, sentence_transformers, tree_sitter; print('✅ All imports OK')"
   ```

2. **Test server manually:**
   ```bash
   cd /Users/abhiram/Desktop/CodeNav/codenav/server
   source venv/bin/activate
   python main.py
   ```

3. **Check for port conflicts:**
   ```bash
   lsof -i :8765
   # If something is using port 8765, kill it or change the port in VS Code settings
   ```

### Project Opening Failed ("fetch failed")

This was the issue we just fixed! The extension now:
1. Waits for server to be ready with health checks (10 attempts, 1 second apart)
2. Retries project opening 3 times with 2-second delays

If it still fails:

1. **Check server logs:**
   - Open VS Code Output panel (View → Output)
   - Select "CodeNav" from the dropdown
   - Look for health check messages

2. **Manually test the API:**
   ```bash
   # While server is running
   curl http://localhost:8765/health
   ```

3. **Increase retry settings:**
   - Edit `src/extension.ts`
   - Change `waitForServerReady(10)` to `waitForServerReady(20)` for more retries
   - Change `projectManager.openProject()` to use more retries

### Indexing Issues

If indexing fails or hangs:

1. **Check file count:**
   - Very large projects (>10k files) may take several minutes
   - Check server logs for progress

2. **NumPy compatibility:**
   - We already fixed this by downgrading to NumPy 1.x
   - If you see NumPy errors, run:
     ```bash
     cd server
     source venv/bin/activate
     pip uninstall numpy -y
     pip install "numpy<2.0"
     pip install --force-reinstall --no-binary :all: sentence-transformers
     ```

## Running the Extension

### Quick Setup

```bash
cd /Users/abhiram/Desktop/CodeNav/codenav
chmod +x setup-extension.sh
./setup-extension.sh
```

### Manual Steps

1. **Install extension dependencies:**
   ```bash
   cd /Users/abhiram/Desktop/CodeNav/codenav
   npm install
   ```

2. **Compile TypeScript:**
   ```bash
   npm run compile
   ```

3. **Launch in VS Code:**
   - Open the `codenav` folder in VS Code
   - Press F5 to start debugging
   - A new VS Code window will open with the extension loaded

## Testing the Fixes

### Test Health Check System

1. Start the extension (F5)
2. Open Output panel → CodeNav
3. You should see:
   ```
   Starting CodeNav server...
   Waiting for server... (attempt 1/10)
   ✅ Server health check passed
   Opening project: /your/project/path
   ✅ Project opened: YourProjectName
   ```

### Test Retry Logic

If the first attempt fails, you should see:
```
Opening project: /your/project/path
⚠️ Failed to open project (attempt 1/3), retrying...
⚠️ Failed to open project (attempt 2/3), retrying...
✅ Project opened: YourProjectName
```

## New Coding Agent Features

### Test Task Planning

1. Open Command Palette (Cmd+Shift+P)
2. Run: "CodeNav: Ask Agent"
3. Try a complex task:
   ```
   Add error handling to all API endpoints with proper HTTP status codes
   ```

4. The agent should:
   - Analyze the request
   - Break it into atomic tasks
   - Execute each task
   - Show progress

### Test File Operations

Try these commands via the agent:

**List files:**
```
"Show me all Python files in the server directory"
```

**Read code:**
```
"What does the agent loop do?"
```

**Make changes:**
```
"Add a comment to main.py explaining what it does"
```

**Complex task:**
```
"Add input validation to the login function with email format and password length checks"
```

## Common Error Messages

### "No project opened"
- Make sure you have a workspace folder open in VS Code
- The extension auto-opens the workspace on server start

### "Please wait for indexing to complete"
- Check the status bar (bottom) for indexing progress
- Wait for "X functions" to appear

### "Server not running"
- Click the status bar item to start the server
- Or run command: "CodeNav: Start Server"

### "Request timed out"
- Server might be slow on first start (downloading models)
- Check server logs for "Server started on port 8765"
- Increase timeout in apiClient.ts if needed

## Configuration

Open VS Code Settings (Cmd+,) and search for "codenav":

```json
{
  "codenav.serverPath": "",  // Auto-detected
  "codenav.pythonPath": "python",
  "codenav.serverPort": 8765,
  "codenav.autoStartServer": true,  // Start server on activation
  "codenav.autoOpenProject": true,  // Auto-open workspace
  "codenav.maxTokens": 2048,
  "codenav.maxIterations": 10,
  "codenav.enableTaskPlanning": true  // NEW: Enable Copilot-style decomposition
}
```

## Getting More Help

1. **Check the guides:**
   - `CODING_AGENT_QUICK_START.md` - Usage guide
   - `PHASE_8_CODING_AGENT_COMPLETE.md` - Technical details

2. **Examine the code:**
   - Extension: `src/extension.ts`
   - API Client: `src/apiClient.ts`
   - Project Manager: `src/projectManager.ts`
   - Agent: `server/agent/agent_loop.py`

3. **Debug mode:**
   - Launch extension with F5
   - Set breakpoints in TypeScript files
   - View console output in Debug Console

## Useful Commands

```bash
# Extension development
cd /Users/abhiram/Desktop/CodeNav/codenav
npm run compile  # Compile TypeScript
npm run watch    # Auto-compile on changes

# Server development
cd /Users/abhiram/Desktop/CodeNav/codenav/server
source venv/bin/activate
python main.py   # Run server manually

# Testing
cd /Users/abhiram/Desktop/CodeNav/codenav/server
pytest tests/    # Run Python tests

# Clean slate
rm -rf codenav/node_modules codenav/out
cd codenav && npm install && npm run compile
```
