# Advanced Tool Use Implementation Plan for Opus Orchestrator

**Date:** 2025-11-29
**Status:** Planning Phase
**Estimated Effort:** 20-30 hours

## Executive Summary

This plan details integrating Anthropic's Advanced Tool Use features into the Opus Orchestrator to achieve:
- **37% token reduction** via programmatic tool calling
- **72% → 90% accuracy improvement** via tool use examples
- **85% reduction** in tool definition overhead via tool search
- **Elimination of regex parsing** - structured tool_use blocks replace manual command extraction

---

## Current State vs Target State

### Current: Text-Based Tool Calling
```
User Prompt → LLM generates markdown → Regex parses ```bash blocks → Execute command
```
**Problems:**
- Hallucination-prone (LLM can invent outputs)
- No schema validation
- Manual output truncation/formatting
- 19+ sequential API calls for file exploration

### Target: Structured Tool Use
```
User Prompt + Tool Definitions → LLM returns tool_use block → Structured execution → tool_result block
```
**Benefits:**
- Schema-validated tool calls
- Automatic input validation
- Programmatic batching (1 call replaces 19)
- In-context examples improve accuracy

---

## Three Key Features to Implement

### Feature 1: Programmatic Tool Calling (HIGHEST PRIORITY)
**Source:** Anthropic's `claude.tools.run_python` pattern

**What it does:**
- Claude writes Python code that orchestrates multiple tools
- Single API call replaces 19+ sequential calls
- 37% token reduction measured by Anthropic

**Current Pattern (19 API calls):**
```python
# Call 1: List files
files = tool_registry.list_files()
# Call 2: Read file 1
content1 = tool_registry.read_file("file1.py")
# Call 3: Read file 2
content2 = tool_registry.read_file("file2.py")
# ... 16 more calls
```

**Target Pattern (1 API call):**
```python
response = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    tools=[{
        "name": "run_python",
        "description": "Execute Python code with tool access",
        "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}}
    }],
    messages=[{"role": "user", "content": "Explore the repository structure"}]
)

# Claude returns:
# tool_use: run_python
# code: '''
# files = list_files()
# relevant = [f for f in files if 'test' in f or 'main' in f]
# contents = {f: read_file(f) for f in relevant[:10]}
# return {"files": relevant, "contents": contents}
# '''
```

**Expected Improvement:**
- 37% fewer tokens
- 10-20x fewer API calls for exploration tasks
- Faster execution (parallel file reads)

---

### Feature 2: Tool Use Examples (HIGH PRIORITY)
**Source:** Anthropic's in-context learning pattern

**What it does:**
- Provides example tool calls in system prompt
- Model learns correct parameter patterns
- 72% → 90% accuracy improvement measured

**Current System Prompt (no examples):**
```
You can execute bash commands in ```bash blocks.
```

**Target System Prompt (with examples):**
```
You have access to tools. Here are examples of correct usage:

EXAMPLE 1: Finding relevant files
<tool_use>
{"name": "grep_search", "input": {"pattern": "def.*error", "file_pattern": "*.py"}}
</tool_use>
<tool_result>
src/handler.py:45: def handle_error(e):
src/utils.py:12: def format_error_message(msg):
</tool_result>

EXAMPLE 2: Reading a file
<tool_use>
{"name": "read_file", "input": {"path": "src/handler.py"}}
</tool_use>
<tool_result>
(file contents)
</tool_result>

EXAMPLE 3: Running tests
<tool_use>
{"name": "run_command", "input": {"command": "python -m pytest tests/ -v"}}
</tool_use>
```

**Expected Improvement:**
- 18% absolute accuracy gain (72% → 90%)
- Fewer malformed tool calls
- Better parameter inference

---

### Feature 3: Structured Tool Definitions (MEDIUM PRIORITY)
**Source:** Anthropic's native tool use API

**What it does:**
- Replace embedded prompt instructions with JSON Schema
- Native validation by Claude
- Cleaner response handling

**Current (embedded in prompt):**
```python
SYSTEM_PROMPT = """
You can use these tools:
- find files: search the codebase
- read files: get file contents
- run commands: execute bash
"""
```

**Target (JSON Schema):**
```python
TOOL_DEFINITIONS = [
    {
        "name": "read_file",
        "description": "Read file contents from workspace",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"}
            },
            "required": ["path"]
        }
    },
    # ... more tools
]

response = client.messages.create(
    tools=TOOL_DEFINITIONS,  # Native tool support
    ...
)
```

**Expected Improvement:**
- Automatic input validation
- Cleaner code (remove regex parsing)
- Better error messages

---

## Implementation Phases

### Phase 1: Foundation (4-6 hours)
**Goal:** Add structured tool definitions without breaking existing functionality

1. **Create `tool_definitions.py`** (~80 lines)
   ```python
   TOOL_DEFINITIONS = [
       {"name": "list_files", "description": "...", "input_schema": {...}},
       {"name": "read_file", "description": "...", "input_schema": {...}},
       {"name": "write_file", "description": "...", "input_schema": {...}},
       {"name": "run_command", "description": "...", "input_schema": {...}},
       {"name": "grep_search", "description": "...", "input_schema": {...}},
   ]
   ```

2. **Create `tool_executor.py`** (~150 lines)
   ```python
   class ToolExecutor:
       def __init__(self, tool_registry: ToolRegistry):
           self.registry = tool_registry

       def execute(self, tool_name: str, inputs: dict) -> dict:
           """Execute tool and return structured result."""
           if tool_name == "read_file":
               return {"content": self.registry.read_file(inputs["path"])}
           # ... other tools
   ```

3. **Update `multi_provider_client.py`** (~50 lines changed)
   - Add `tools` parameter to `complete()` method
   - Add `_handle_tool_use_response()` method
   - Update `CompletionResult` dataclass

**Files Modified:**
- NEW: `opus_orchestrator/tool_definitions.py`
- NEW: `opus_orchestrator/tool_executor.py`
- MODIFIED: `opus_orchestrator/multi_provider_client.py`

---

### Phase 2: Agentic Loop Migration (6-8 hours)
**Goal:** Replace regex parsing with structured tool use

1. **Update `agentic_loop.py`** (~200 lines changed)

   **Before (Lines 378-510):**
   ```python
   response = self.client.messages.create(
       model=self.model,
       messages=messages
   )
   thought = response.content[0].text
   action = parse_bash_command(thought)  # REGEX PARSING
   result = executor.execute(action)
   ```

   **After:**
   ```python
   response = self.client.messages.create(
       model=self.model,
       messages=messages,
       tools=TOOL_DEFINITIONS  # STRUCTURED TOOLS
   )

   for block in response.content:
       if block.type == "tool_use":
           result = tool_executor.execute(block.name, block.input)
           messages.append({"role": "user", "content": [
               {"type": "tool_result", "tool_use_id": block.id, "content": result}
           ]})
   ```

2. **Add Tool Use Examples to System Prompt**
   ```python
   TOOL_USE_EXAMPLES = """
   EXAMPLE: Search for bug location
   Tool: grep_search(pattern="ValueError", file_pattern="*.py")
   Result: Found in src/main.py:42, src/utils.py:88

   EXAMPLE: Read the problematic file
   Tool: read_file(path="src/main.py")
   Result: (file contents)
   """

   SYSTEM_PROMPT = f"""You are an expert engineer.

   {TOOL_USE_EXAMPLES}

   Use tools to understand the problem, then fix it.
   """
   ```

**Files Modified:**
- MODIFIED: `opus_orchestrator/agentic_loop.py` (major refactor)
- DELETED: `parse_bash_command()` function (replaced by structured tools)

---

### Phase 3: Programmatic Tool Calling (4-6 hours)
**Goal:** Enable Claude to write Python code that orchestrates multiple tools

1. **Add `run_python` tool definition**
   ```python
   {
       "name": "run_python",
       "description": "Execute Python code with access to workspace tools",
       "input_schema": {
           "type": "object",
           "properties": {
               "code": {
                   "type": "string",
                   "description": "Python code to execute. Has access to: list_files(), read_file(path), write_file(path, content), run_command(cmd), grep_search(pattern)"
               }
           },
           "required": ["code"]
       }
   }
   ```

2. **Create safe Python executor**
   ```python
   def execute_python_with_tools(code: str, tool_registry: ToolRegistry) -> str:
       """Execute Python code with tool access in sandbox."""
       local_scope = {
           "list_files": tool_registry.list_files,
           "read_file": tool_registry.read_file,
           "write_file": tool_registry.write_file,
           "run_command": tool_registry.run_command,
           "grep_search": tool_registry.grep_search,
       }

       exec(code, {"__builtins__": SAFE_BUILTINS}, local_scope)
       return local_scope.get("result", "")
   ```

3. **Update context agent to use programmatic calling**
   ```python
   # Context agent can now explore entire repo in 1 API call
   response = client.messages.create(
       tools=[RUN_PYTHON_TOOL],
       messages=[{
           "role": "user",
           "content": f"Analyze this repository to find files related to: {issue}"
       }]
   )

   # Claude returns code that:
   # 1. Lists all files
   # 2. Filters by relevance
   # 3. Reads important files
   # 4. Returns structured analysis
   ```

**Files Modified:**
- MODIFIED: `opus_orchestrator/tool_definitions.py` (add run_python)
- NEW: `opus_orchestrator/python_sandbox.py`
- MODIFIED: `opus_orchestrator/meta_orchestrator.py` (context agent)

---

### Phase 4: Meta-Orchestrator Integration (4-6 hours)
**Goal:** Update all agent calls to support tools

1. **Update all `client.complete()` calls** (~15 locations)
   ```python
   # Before
   result = self.client.complete(model_config, messages, max_tokens=4096)

   # After
   result = self.client.complete(
       model_config,
       messages,
       max_tokens=4096,
       tools=TOOL_DEFINITIONS if needs_tools else None
   )
   ```

2. **Add tool result processing to agents**
   ```python
   if result.tool_calls:
       for tc in result.tool_calls:
           tool_result = tool_executor.execute(tc.name, tc.input)
           # Continue conversation with tool result
   ```

**Files Modified:**
- MODIFIED: `opus_orchestrator/meta_orchestrator.py`
- MODIFIED: `opus_orchestrator/strategic_planner.py`
- MODIFIED: `opus_orchestrator/adaptive_validator.py`

---

## Expected Improvements

### Quantitative Improvements

| Metric | Current | Expected | Source |
|--------|---------|----------|--------|
| Token Usage | Baseline | -37% | Anthropic: Programmatic tool calling |
| Tool Call Accuracy | ~72% | ~90% | Anthropic: Tool use examples |
| API Calls per Exploration | 19+ | 1-3 | Programmatic batching |
| Hallucination Rate | ~15% | ~5% | Structured validation |

### Qualitative Improvements

1. **Cleaner Code**
   - Remove regex-based command parsing
   - Remove hallucination detection heuristics
   - Remove manual output formatting

2. **Better Error Handling**
   - Schema validation catches malformed inputs
   - Structured error responses
   - Automatic retry with corrected inputs

3. **Faster Execution**
   - Parallel file reads in programmatic mode
   - Fewer round-trips to API
   - Reduced context window usage

---

## Migration Checklist

### Phase 1: Foundation
- [ ] Create `tool_definitions.py` with JSON schemas
- [ ] Create `tool_executor.py` with execution mapping
- [ ] Update `CompletionResult` dataclass for tool_calls
- [ ] Add `tools` parameter to `multi_provider_client.complete()`
- [ ] Add `_handle_tool_use_response()` method
- [ ] Unit tests for tool executor

### Phase 2: Agentic Loop
- [ ] Add tool use examples to SYSTEM_PROMPT
- [ ] Update message creation to include tools
- [ ] Refactor response handling for tool_use blocks
- [ ] Remove `parse_bash_command()` function
- [ ] Update message history format
- [ ] Integration tests with mock tools

### Phase 3: Programmatic Calling
- [ ] Add `run_python` tool definition
- [ ] Create `python_sandbox.py` with safe execution
- [ ] Update context agent for programmatic exploration
- [ ] Add security restrictions to sandbox
- [ ] Benchmark: sequential vs programmatic

### Phase 4: Meta-Orchestrator
- [ ] Update all `complete()` calls with tools parameter
- [ ] Add tool result processing logic
- [ ] Update agent prompts for tool awareness
- [ ] End-to-end testing with SWE-bench instance

---

## Risk Mitigation

### Risk 1: Breaking Existing Functionality
**Mitigation:**
- Add tools as optional parameter (default=None)
- Keep text-parsing fallback for non-tool responses
- Run A/B comparison before full migration

### Risk 2: Sandbox Security
**Mitigation:**
- Restrict `__builtins__` in Python executor
- Timeout on code execution
- Only expose tool registry methods, not arbitrary imports

### Risk 3: Provider Compatibility
**Mitigation:**
- Tools parameter only sent to Anthropic models
- Non-Anthropic models continue with text-based approach
- Provider detection in `_build_payload()`

---

## Testing Strategy

### Unit Tests
```python
def test_tool_definitions_valid():
    """Verify all tool schemas are valid JSON Schema."""
    for tool in TOOL_DEFINITIONS:
        jsonschema.validate(schema=tool["input_schema"])

def test_tool_executor_read_file():
    """Test read_file tool execution."""
    executor = ToolExecutor(mock_registry)
    result = executor.execute("read_file", {"path": "test.py"})
    assert "content" in result

def test_tool_use_examples_in_prompt():
    """Verify examples are included in system prompt."""
    assert "EXAMPLE" in SYSTEM_PROMPT
    assert "grep_search" in SYSTEM_PROMPT
```

### Integration Tests
```python
def test_agentic_loop_with_tools():
    """Run agentic loop with structured tools."""
    loop = AgenticLoop(use_structured_tools=True)
    result = loop.run(test_issue)
    assert result.patch is not None

def test_programmatic_exploration():
    """Test programmatic tool calling for context."""
    agent = ContextAgent(use_programmatic_tools=True)
    context = agent.analyze(repo_path)
    assert len(context.relevant_files) > 0
```

### Benchmark Tests
```python
def test_token_reduction():
    """Measure token reduction from programmatic calling."""
    # Sequential approach
    tokens_sequential = run_sequential_exploration()

    # Programmatic approach
    tokens_programmatic = run_programmatic_exploration()

    reduction = 1 - (tokens_programmatic / tokens_sequential)
    assert reduction >= 0.30  # At least 30% reduction
```

---

## Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Foundation | 1-2 days | None |
| Phase 2: Agentic Loop | 2-3 days | Phase 1 |
| Phase 3: Programmatic | 1-2 days | Phase 2 |
| Phase 4: Integration | 1-2 days | Phase 3 |
| Testing & Validation | 2-3 days | All phases |
| **Total** | **7-12 days** | |

---

## Success Criteria

1. **Token Reduction:** ≥30% reduction in exploration tasks
2. **Accuracy:** Tool call success rate ≥85%
3. **Speed:** ≤5 API calls for initial context gathering (down from 19+)
4. **Compatibility:** All existing tests pass
5. **Maintainability:** Regex parsing code removed

---

## Files Summary

### New Files (3)
| File | Purpose | Lines |
|------|---------|-------|
| `tool_definitions.py` | JSON Schema tool definitions | ~80 |
| `tool_executor.py` | Tool execution mapping | ~150 |
| `python_sandbox.py` | Safe Python execution | ~100 |

### Modified Files (8)
| File | Changes | Lines Changed |
|------|---------|---------------|
| `multi_provider_client.py` | Add tools support | ~50 |
| `agentic_loop.py` | Major refactor for tool_use | ~200 |
| `meta_orchestrator.py` | Update complete() calls | ~100 |
| `strategic_planner.py` | Add tools parameter | ~20 |
| `adaptive_validator.py` | Add tools parameter | ~20 |
| `compounding_learner.py` | Add tools parameter | ~20 |
| `model_selection_learner.py` | Add tools parameter | ~20 |
| `prompt_evolver.py` | Add tools parameter | ~20 |

**Total New Code:** ~330 lines
**Total Modified Code:** ~450 lines
