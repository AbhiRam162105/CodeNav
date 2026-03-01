# Phase 2: Call Tree Engine ✓

## Completed Tasks

### 2.1 - Python AST Walker Base Class ✓
- Created `CallTreeBuilder(ast.NodeVisitor)` in `core/call_tree.py`
- Tracks current function context during traversal
- Stores function locations and call relationships
- Test: verified empty AST handling

### 2.2 - Function Definition Visitor ✓
- `visit_FunctionDef()` extracts qualified names (`file::function`)
- Stores function metadata: file, name, line_start, line_end
- Handles async functions via `visit_AsyncFunctionDef()`
- Properly manages nested function contexts
- Test: regular functions, nested functions, async functions

### 2.3 - Call Expression Visitor ✓
- `visit_Call()` extracts function calls
- Handles simple calls (`foo()`) and method calls (`obj.method()`)
- Records callee name and line number
- Test: simple calls, method calls, chained calls, calls in comprehensions

### 2.4 - Single File Parser ✓
- `parse_file()` reads file, parses AST, runs CallTreeBuilder
- Returns dict with "functions" and "calls" keys
- Handles SyntaxError and UnicodeDecodeError gracefully
- Test: multi-function file with call chains

### 2.5 - Repo Walker ✓
- `build_codemap()` walks directory tree
- Filters excluded directories: __pycache__, .git, node_modules, venv, dist, build, etc.
- Processes all `.py` files (extended to `.js/.ts` in 2.10)
- Returns codemap with metadata: version, root, functions, calls, file_count, function_count
- Test: multi-file project structure, excluded directories

### 2.6 - Handle Duplicate Function Names ✓
- `resolve_callees()` post-processes codemap
- Maps short callee names to all matching qualified names
- Adds `resolved_to` field with list of candidates
- Handles ambiguous calls (multiple files define same function)
- Test: unique resolution, ambiguous resolution, unresolved external calls

### 2.7 - Codemap Serialization ✓
- Created `core/serialization.py`
- `save_codemap()` writes to `.codenav/codemap.json` with source hash
- `load_codemap()` reads from disk, returns None if not found
- `compute_source_hash()` generates MD5 from file paths and mtimes
- `is_codemap_stale()` detects if source files changed
- Test: save/load roundtrip, staleness detection

### 2.8 - Incremental Update ✓
- `update_codemap_for_file()` updates single changed file
- Removes old entries from that file
- Re-parses the file
- Merges new entries back in
- Updates function count
- Test: modify one file, verify others unchanged

### 2.9 - JavaScript/TypeScript Parser ✓
- Created `core/js_parser.py` using tree-sitter
- `JSCallTreeBuilder` class with same interface as Python parser
- Queries for: function_declaration, arrow_function, method_definition, call_expression
- Handles TypeScript and JavaScript
- Returns identical format to Python parser
- Added tree-sitter dependencies to requirements.txt
- Test: JS functions, arrow functions, class methods, async functions

### 2.10 - Language Router ✓
- `parse_file_any_language()` routes based on extension
- `.py` → Python AST parser
- `.js/.jsx/.ts/.tsx` → tree-sitter parser
- Other extensions → empty dict
- Updated `build_codemap()` to support all languages
- Test: mixed Python+TypeScript repo

### 2.11 - Index Endpoint ✓
- `POST /index/start` triggers background indexing
- `GET /index/status` returns current status and progress
- Background thread runs: build_codemap → resolve_callees → save_codemap
- Updates app_state with progress (0 → 50 → 100)
- Sets index_status: idle → indexing → ready/error
- Prevents concurrent indexing
- Test: full workflow, concurrent prevention

### 2.12 - File Watcher Setup ✓
- Created `core/watcher.py` using watchdog
- `FileWatcher` class monitors project directory
- `CodeFileHandler` handles file modification/creation events
- 2-second debounce to batch changes
- Calls `update_codemap_for_file()` for each change
- Re-resolves callees and saves after updates
- Starts automatically after indexing completes
- Filters events to only `.py/.js/.ts/.tsx` files
- Test: file modification triggers update

## Created Files

1. `server/core/call_tree.py` - AST walker and codemap building
2. `server/core/serialization.py` - Save/load/hash/update operations
3. `server/core/js_parser.py` - JavaScript/TypeScript parsing
4. `server/core/watcher.py` - File system watching
5. `server/tests/test_call_tree.py` - Call tree extraction tests
6. `server/tests/test_serialization.py` - Serialization tests
7. `server/tests/test_indexing.py` - Integration tests for indexing

## Updated Files

1. `server/main.py` - Added index endpoints
2. `server/requirements.txt` - Added tree-sitter dependencies

## API Endpoints Summary

```
POST /index/start        - Start background indexing
GET  /index/status       - Get indexing status and progress
```

## Codemap Structure

```json
{
  "version": "1.0",
  "root": "/path/to/project",
  "source_hash": "md5_hash",
  "functions": {
    "file.py::function_name": {
      "file": "file.py",
      "name": "function_name",
      "line_start": 10,
      "line_end": 15,
      "qualified": "file.py::function_name"
    }
  },
  "calls": {
    "file.py::caller": [
      {
        "callee": "callee_name",
        "line": 12,
        "resolved_to": ["file.py::callee_name", "other.py::callee_name"]
      }
    ]
  },
  "function_count": 42,
  "file_count": 7
}
```

## Key Features

**Multi-Language Support:**
- Python via AST
- JavaScript/TypeScript via tree-sitter
- Extensible to other languages

**Efficient Updates:**
- Incremental file-level updates
- Source hash for staleness detection
- Automatic file watching
- Debounced batch processing

**Ambiguity Handling:**
- Resolves short names to all possible qualified names
- Preserves ambiguous call relationships
- Enables accurate traversal

## Testing

Phase 2 has comprehensive test coverage:
- Function extraction (simple, nested, async)
- Call extraction (simple, method, chained)
- Full codemap building
- Callee resolution (unique, ambiguous)
- Serialization (save, load, staleness)
- Incremental updates
- Directory exclusion
- Error handling (syntax errors, missing files)
- Indexing workflow
- Concurrent indexing prevention

Run tests:
```bash
cd server
source venv/bin/activate
pytest tests/test_call_tree.py -v
pytest tests/test_serialization.py -v
pytest tests/test_indexing.py -v
```

## How to Use

1. **Open a project:**
```bash
curl -X POST http://localhost:8765/project/open \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/project"}'
```

2. **Start indexing:**
```bash
curl -X POST http://localhost:8765/index/start
```

3. **Check status:**
```bash
curl http://localhost:8765/index/status
```

4. **Files are automatically watched** - any changes trigger incremental updates

## Example Output

For a project with this structure:
```
project/
  src/
    main.py
      def main():
          process()
      def process():
          load_data()
          save_data()
      def load_data():
          pass
      def save_data():
          pass
```

The codemap will capture:
- 4 functions with precise line numbers
- Call relationships: main→process, process→load_data, process→save_data
- Resolved callees linking names to qualified functions

## Next Steps: Phase 3 - Embeddings and Semantic Search

Phase 2 provides the call graph structure. Phase 3 will add semantic search:

1. **Embedder** - SentenceTransformer for function embeddings
2. **FAISS Index** - Fast similarity search
3. **Function Text Representation** - Format for embedding
4. **Snippet Extraction** - Get function code with context
5. **Search Endpoint** - Query by natural language
6. **Graph Traversal** - BFS from entry points
7. **Context Assembly** - Combine search + traversal

This enables the core value prop: Given a task like "fix the authentication bug", we semantically search for `auth/login` functions, then traverse 2-3 hops of the call graph to get just the relevant context (500-2000 tokens instead of the entire codebase).

---

**Phase 2 Status: Complete ✓**

The call tree engine is fully functional and tested. The foundation for efficient context retrieval is in place.
