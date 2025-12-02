# Opus Meta-Orchestrator Web Frontend

A simple web interface for testing the Opus Meta-Orchestrator with real-time visibility into execution stages.

## Features

- **Variant Selection**: Dropdown to choose from all available presets:
  - `opus-open` - Fast open-source models (GLM, Qwen, Kimi)
  - `opus-optimized` - Best cost/quality balance (recommended)
  - `opus-bestinclass` - Maximum quality with premium models
  - `opus-full` - Full Opus 4.5 stack
  - `baseline` - Single Opus call for comparison

- **Real-time Execution Log**: Watch each stage as it executes:
  - Orchestrator start/end
  - Context gathering
  - Feature engineering
  - Code review
  - Execution results

- **Live Metrics**:
  - Execution time (seconds)
  - Total cost ($)
  - Features completed/total
  - Pass/Fail status

- **Results Tabs**:
  - **Code**: Extracted code with syntax highlighting
  - **Full Response**: Complete model output
  - **Plan**: Execution plan and archetype

## Installation

```bash
cd frontend
pip install -r requirements.txt
```

## Usage

```bash
# From the frontend directory
python app.py

# Or from project root
python frontend/app.py
```

Then open http://localhost:5050 in your browser.

## Keyboard Shortcuts

- `Ctrl+Enter` - Run task

## Screenshots

The interface provides:
1. **Left Panel**: Configuration (preset, repo path) and task input
2. **Execution Log**: Real-time stage-by-stage logging
3. **Right Panel**: Metrics dashboard and tabbed results view

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Browser (HTML/JS)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Config Form │  │ Exec Logs   │  │ Metrics + Results   │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                           │ WebSocket
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    Flask + SocketIO                          │
│  - Serves HTML template                                      │
│  - Handles WebSocket connections                             │
│  - Wraps OpusMetaOrchestrator with logging callbacks         │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                  OpusMetaOrchestrator                        │
│  - Strategic planning (Opus)                                 │
│  - Feature decomposition                                     │
│  - Model selection per feature                               │
│  - Code execution and validation                             │
└──────────────────────────────────────────────────────────────┘
```

## API Endpoints

### REST
- `GET /` - Main web interface
- `GET /api/presets` - List all available presets
- `GET /api/models` - List all available models

### WebSocket Events

**Client → Server:**
- `run_task` - Run with orchestrator: `{task, preset, repo_path}`
- `run_baseline` - Run single Opus call: `{task}`

**Server → Client:**
- `connected` - Connection established with session ID
- `run_started` - Task execution started
- `stage_log` - Individual stage log entry
- `debug_log` - Debug messages
- `run_completed` - Final results with metrics
- `run_error` - Error occurred

## Customization

### Adding New Presets

Presets are defined in `alo/agentic_loops/opus_orchestrator/presets.py`. Add a new entry to the `PRESETS` dict and it will automatically appear in the dropdown.

### Changing Default Port

Edit `app.py` line:
```python
socketio.run(app, host='0.0.0.0', port=5050, debug=True)
```

## Troubleshooting

### "Module not found" errors
Make sure you're running from the project root or the `frontend` directory, and that the project root is in your Python path.

### WebSocket connection fails
- Check that no other service is using port 5050
- Try disabling any browser extensions that might block WebSockets
- Check firewall settings

### API key errors
Ensure your `.env` file has the required API keys:
```
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
OPENROUTER_API_KEY=...
CEREBRAS_API_KEY=...
GEMINI_API_KEY=...
```
