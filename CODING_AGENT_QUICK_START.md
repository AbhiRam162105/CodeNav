# CodeNav Coding Agent - Quick Start Guide 🚀

## You Now Have a Full Coding Agent!

CodeNav has been upgraded with **GitHub Copilot-style task decomposition** and comprehensive file editing capabilities.

## What Can It Do?

### ✅ File Operations
- **Create** new files
- **Edit** existing code
- **Delete** files
- **Move/rename** files
- **List** directory contents

### ✅ Code Analysis
- **Search** codebase with natural language
- **Retrieve** relevant context
- **Understand** project structure

### ✅ Task Management
- **Break down** complex requests into atomic tasks
- **Elaborate** prompts with clarifying questions
- **Execute** tasks sequentially

### ✅ Execution
- **Run** shell commands
- **Execute** tests
- **Verify** changes

## How to Use

### Simple Example

**You:** "What Python files are in the src directory?"

**Agent:**
```
1. Uses list_directory tool
2. Filters for .py files
3. Returns formatted list
```

### Complex Example

**You:** "Add authentication to all API endpoints"

**Agent:**
1. **Plans** the implementation:
   - Search for API route files
   - Read existing auth code
   - Create auth middleware
   - Update routes to use middleware
   - Add tests
   - Run tests

2. **Executes** each task
3. **Verifies** the result

## Try It Now!

### Test 1: List Files
```
"Show me all the files in the server directory"
```

### Test 2: Understand Code
```
"What does the agent loop do?"
```

### Test 3: Make Simple Change
```
"Add a comment to the main.py file explaining what it does"
```

### Test 4: Complex Task
```
"Add error handling to all API endpoints with proper HTTP status codes"
```

The agent will:
1. Create a task plan (3-8 atomic steps)
2. Show you the plan
3. Ask if you want to proceed
4. Execute each step
5. Provide a summary

## Features

### 🔍 Automatic Task Decomposition

The agent detects complex requests and automatically:
- Analyzes requirements
- Asks clarifying questions
- Breaks into atomic tasks
- Creates execution plan
- Shows progress

### 📝 Safe File Editing

All file operations:
- Validate paths (prevent path traversal)
- Use atomic writes (temporary file + rename)
- Stay within project root
- Support undo via Git

### 🎯 Context-Aware

The agent:
- Searches before editing
- Reads files before changing
- Verifies after editing
- Runs tests when needed

## Configuration

Open VS Code settings and search for "codenav":

```json
{
  "codenav.enableTaskPlanning": true,  // Enable task decomposition
  "codenav.maxIterations": 10,         // Max iterations per task
  "codenav.maxTokens": 2048            // Tokens per LLM call
}
```

## Available Tools

### Analysis
- `search_codebase` - Find code with natural language
- `retrieve_context` - Get related code with call graph
- `list_directory` - List files and directories

### Reading
- `read_lines` - Read specific lines from files

### Editing
- `write_file` - Create or overwrite files
- `apply_diff` - Edit existing code
- `create_file` - Create new files
- `delete_file` - Delete files
- `move_file` - Rename/move files

### Execution
- `run_command` - Execute shell commands
- `ask_user` - Ask clarifying questions
- `finish` - Complete task

## Example Workflows

### Add New Feature

**Request:** "Add a logging system"

**Agent Plan:**
```
T1: Search for existing logging usage
T2: Create logger.py with Logger class
T3: Add logging to main entry points
T4: Create logging config file
T5: Update README
```

### Fix Bug

**Request:** "Fix the authentication validation bug"

**Agent Plan:**
```
T1: Search for auth validation code
T2: Read the validation function
T3: Identify the bug
T4: Apply the fix
T5: Add test for the bug
T6: Run tests
```

### Refactor Code

**Request:** "Refactor database connections to use pooling"

**Agent Plan:**
```
T1: Search for DB connection code
T2: Read current implementation
T3: Create connection pool manager
T4: Update existing connections
T5: Add pool tests
T6: Verify no regressions
```

## Best Practices

### Do's ✅
- **Be specific**: "Add JWT authentication" vs "Add auth"
- **Commit first**: Use git before major changes
- **Review plans**: Check task breakdown before executing
- **Start simple**: Test with small requests first
- **Verify results**: Read files after changes

### Don'ts ❌
- **Don't be vague**: "Make it better" → What specifically?
- **Don't skip planning**: Complex tasks need decomposition
- **Don't ignore errors**: Agent will stop on failures
- **Don't forget tests**: Always verify changes
- **Don't modify .git**: Keep version control safe

## Troubleshooting

### "Task too complex"
→ Break into smaller requests

### "File not found"
→ Use `list_directory` first to find files

### "Planning failed"
→ Retry with simpler, more specific request

### "Changes didn't apply"
→ Check if file was modified externally

## Tips & Tricks

### Get Better Results

1. **Provide context**: Mention file names, functions, or modules
2. **Specify requirements**: Include edge cases and constraints
3. **Set expectations**: Mention testing, documentation needs
4. **Use iterations**: Start with MVP, then enhance

### Example Requests

**Good:**
```
"Add input validation to the login function in auth.py.
Validate email format and password length (min 8 chars).
Return proper error messages."
```

**Bad:**
```
"Fix auth"
```

### Iterate on Complex Tasks

Instead of:
```
"Build a complete user management system"
```

Do:
```
1. "Create user model with basic fields"
2. "Add user registration endpoint"
3. "Add login endpoint with JWT"
4. "Add password reset functionality"
```

## Next Steps

1. **Test basic operations** - Try list, read, search
2. **Try simple edits** - Add comments, fix typos
3. **Attempt complex tasks** - Add features, refactor
4. **Review the code** - Understand how it works
5. **Customize prompts** - Adjust to your needs

## Learn More

- **Full Documentation**: `PHASE_8_CODING_AGENT_COMPLETE.md`
- **Tool Reference**: Check agent/prompts.py
- **Examples**: See Phase 8 documentation

## Support

If something isn't working:
1. Check the Output panel (View → Output → CodeNav)
2. Review the task plan in the sidebar
3. Check git status for unexpected changes
4. Open an issue with details

---

**Happy Coding!** The agent is ready to help you build, refactor, and maintain your projects. Start with simple tasks and work your way up to complex implementations.

Your coding assistant is now as powerful as GitHub Copilot! 🎉
