# Phase 6 Quick Start Guide

## Prerequisites

- VS Code >= 1.80.0
- Node.js >= 16.0.0
- Server from Phases 0-5 working

## Installation

### 1. Install Dependencies

```bash
cd codenav
npm install
```

### 2. Compile TypeScript

```bash
npm run compile
```

### 3. Launch Extension (Development)

Press **F5** in VS Code to launch Extension Development Host.

## First Time Usage

### Automatic Mode (Recommended)

1. **Open the Extension Development Host window**
2. **Open a workspace/folder** with your project
3. **Extension activates automatically**:
   - Server starts (watch output panel)
   - Project opens
   - Indexing begins
   - Status bar updates

4. **Wait for indexing** (status bar shows progress)

5. **Use the agent** (Cmd/Ctrl + Shift + A)
   ```
   "Find all authentication functions"
   ```

### Manual Mode

If auto-start is disabled:

1. **Open Command Palette** (Cmd/Ctrl + Shift + P)
2. **Run**: `CodeNav: Start Server`
3. **Wait for "Running"** in status bar
4. **Run**: `CodeNav: Open Project`
5. **Wait for indexing** to complete
6. **Use commands**

## Testing Core Features

### Test 1: Server Management

```
# Start server
Command Palette → CodeNav: Start Server
→ Status bar should show "🟡 Starting..."
→ Then "🟢 Running"
→ Output panel shows server logs

# Check health
Command Palette → CodeNav: Check Server Health
→ Shows server status dialog

# Stop server
Click status bar (or Command Palette → Stop Server)
→ Status bar shows "🔴 Stopped"

# Restart server
Command Palette → CodeNav: Restart Server
→ Server stops and starts
```

### Test 2: Project Indexing

```
# Open project (if not auto-opened)
Command Palette → CodeNav: Open Project
→ Indexes current workspace

# Watch progress
→ Status bar shows "🔄 Indexing: 45%"
→ Updates every 2 seconds
→ Completes: "📊 1,234 functions"

# Check status
Command Palette → CodeNav: Show Index Status
→ Shows dialog with progress
```

### Test 3: Agent Query

```
# Ask agent (Cmd/Ctrl + Shift + A)
CodeNav: Ask Agent
→ Input: "Find all authentication functions"
→ Output panel shows progress
→ Notification when complete

# View results
→ Check output panel for full response
→ See tool calls used
→ See tokens used
```

### Test 4: Code Search

```
# Search code (Cmd/Ctrl + Shift + F)
CodeNav: Search Code
→ Input: "authentication"
→ Quick pick shows results
→ Select result → Opens file at location
```

## Configuration

### Settings (File → Preferences → Settings → Extensions → CodeNav)

**Basic:**
```json
{
  "codenav.autoStartServer": true,
  "codenav.autoOpenProject": true,
  "codenav.serverPort": 8765
}
```

**Custom Python:**
```json
{
  "codenav.pythonPath": "/usr/local/bin/python3.11"
}
```

**Custom Server Location:**
```json
{
  "codenav.serverPath": "/path/to/codenav/server"
}
```

**Agent Tuning:**
```json
{
  "codenav.maxTokens": 4096,
  "codenav.maxIterations": 20
}
```

## Keyboard Shortcuts

| Action | Windows/Linux | Mac |
|--------|--------------|-----|
| Ask Agent | Ctrl+Shift+A | Cmd+Shift+A |
| Search Code | Ctrl+Shift+F | Cmd+Shift+F |
| Command Palette | Ctrl+Shift+P | Cmd+Shift+P |

## Status Bar Guide

### Server Status (Left Side)

**States:**
- 🔴 `CodeNav: Stopped` - Server not running (click to start)
- 🟡 `CodeNav: Starting...` - Server starting (animated)
- 🟢 `CodeNav: Running` - Server ready (click to stop)
- 🔴 `CodeNav: Error` - Server error (click to restart)

### Index Status (Next to Server)

**States:**
- (hidden) - No project or idle
- 🔄 `Indexing: 45%` - Indexing in progress
- 📊 `1,234 functions` - Index ready
- ❌ `Index Error` - Indexing failed

## Output Panel

### Viewing Output

```
View → Output → CodeNav (from dropdown)
```

Or:
```
Command Palette → CodeNav: Show Output
```

### Example Output

```
CodeNav extension activated
Starting CodeNav server...
Server directory: /Users/you/codenav/server
Python path: python
Server port: 8765
[Server stdout] INFO:     Uvicorn running on http://0.0.0.0:8765
✅ Server started successfully
Opening project: /Users/you/workspace
✅ Project opened: MyProject
Starting indexing...
✅ Indexing started
✅ Indexing complete: 1,234 functions in 45 files

━━━ Agent Task ━━━
Task: Find all authentication functions

Status: complete
Tokens used: 842
Tool calls: 2

Response:
I found 5 authentication functions in your codebase:

1. validate_credentials() (src/auth.py:45)
   - Validates username and password against database

2. check_session() (src/auth.py:78)
   - Verifies session token is valid and not expired
...

Tool Calls:
  1. search_codebase
     Result: Search results for 'authentication functions':
1. validate_credentials (src/auth.py:45)
   Score: 0.87
...
```

## Troubleshooting

### Issue: Server Won't Start

**Check Python:**
```bash
python --version  # Should be 3.10+
```

**Set Python path:**
```json
{
  "codenav.pythonPath": "/path/to/python"
}
```

**Check server exists:**
```bash
ls ../server/main.py  # Should exist
```

**View errors:**
- View → Output → CodeNav
- Look for error messages

### Issue: Extension Not Activating

**Check activation:**
- Look for "CodeNav extension activated" in output
- If not, check Developer Tools console (Help → Toggle Developer Tools)

**Reload window:**
```
Command Palette → Reload Window
```

### Issue: Commands Not Found

**Compile TypeScript:**
```bash
npm run compile
```

**Reload window:**
```
Command Palette → Reload Window
```

**Check package.json:**
- Verify commands are listed
- Verify contributes section exists

### Issue: No Workspace Detected

**Open folder:**
```
File → Open Folder...
```

**Check workspace:**
- At least one folder must be open
- Multi-root workspaces use first folder

### Issue: Indexing Fails

**Check project size:**
- Very large projects (>10,000 files) may timeout
- Try smaller project first

**Check permissions:**
- Server needs read access to all files

**View logs:**
- Output panel shows indexing errors

### Issue: Agent Returns Error

**Check index ready:**
- Status bar must show "X functions"
- Wait for indexing to complete

**Check API key:**
- Server must have GEMINI_API_KEY in .env
- Command: CodeNav: Check Server Health

**View full error:**
- Output panel shows complete error

## Development Workflow

### Making Changes

1. **Edit TypeScript files** in `src/`
2. **Compile**: `npm run compile`
3. **Reload extension**: Cmd/Ctrl + R in Extension Host window

Or use watch mode:
```bash
npm run watch
```

### Debugging Extension

**Set breakpoints:**
- In TypeScript files
- Press F5 to launch with debugger attached

**View debug console:**
- Debug Console panel shows logs
- Use `console.log()` for debugging

**View extension logs:**
- Output → Extension Host
- Shows TypeScript compilation errors

### Debugging Server

**Server logs:**
- Output → CodeNav panel
- Shows Python server stdout/stderr

**Check server health:**
```
Command Palette → CodeNav: Check Server Health
```

**Manual server test:**
```bash
cd server
python main.py
# Should start server on port 8765
```

## Testing Agent Features

### Simple Queries

```
"Show me all functions in the codebase"
"Find error handling code"
"List all database queries"
```

### Code Understanding

```
"Explain what the authentication middleware does"
"How does the user login flow work?"
"What does the process_payment function do?"
```

### Code Modification

```
"Add error handling to the login function"
"Add type hints to auth.py"
"Refactor the database connection code"
```

### Command Execution

```
"Run pytest and show results"
"Check code formatting with black"
"Show git status"
```

## Testing Search

### Semantic Queries

```
"authentication"
"database queries"
"error handling"
"user validation"
"API endpoints"
```

### Tips for Better Results

- Use natural language
- Be specific but not too narrow
- Try multiple phrasings
- Check "Score" in results (higher is better)

## Performance Expectations

| Operation | Time | Notes |
|-----------|------|-------|
| Extension activation | <500ms | Includes all manager setup |
| Server start | 2-3s | Spawning Python process |
| Project open | <100ms | HTTP request to server |
| Indexing | 1-5s | Depends on project size |
| Agent query | 2-10s | Depends on task complexity |
| Code search | <100ms | FAISS is very fast |

## Next Steps

Once Phase 6 is working:

1. **Try different projects** - Test with various codebases
2. **Tune configuration** - Adjust maxTokens, maxIterations
3. **Explore agent** - Try complex multi-step tasks
4. **Move to Phase 7** - Build sidebar UI for better UX

---

**Phase 6 is complete!** 🎉

You now have a fully functional VS Code extension that manages the CodeNav server and provides agent-powered code assistance.
