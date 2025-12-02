"""
=============================================================================
SCRIPT NAME: app.py
=============================================================================

Opus Meta-Orchestrator Web Frontend

A Flask application with WebSocket support for testing the Meta-Orchestrator
with real-time visibility into each execution stage.

INPUT FILES:
- User prompts via web interface

OUTPUT FILES:
- Real-time execution logs via WebSocket
- Final results and metrics

VERSION: 1.0
LAST UPDATED: 2025-11-30

DESCRIPTION:
Simple web frontend for testing the Opus Meta-Orchestrator. Features:
- Dropdown for variant selection (opus-open, opus-optimized, etc.)
- Real-time stage-by-stage execution visibility
- Metrics display (time, tokens, cost)
- Code syntax highlighting for results

DEPENDENCIES:
- flask
- flask-socketio
- python-dotenv

USAGE:
    cd frontend
    python app.py

Then open http://localhost:5050 in your browser.

=============================================================================
"""

import os
import sys
import time
import json
import threading
import traceback
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

from dotenv import load_dotenv
load_dotenv(override=True)

# Import orchestrator components
from alo.agentic_loops.opus_orchestrator import (
    MultiProviderClient,
    OpusMetaOrchestrator,
    OpusBaselineRunner,
    get_preset,
    PRESETS,
    MODEL_REGISTRY,
    CodeExecutor,
)
from alo.agentic_loops.opus_orchestrator.presets import list_presets

app = Flask(__name__)
app.config['SECRET_KEY'] = 'opus-meta-orchestrator-frontend'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global state for tracking runs
active_runs: Dict[str, dict] = {}


@dataclass
class StageLog:
    """Log entry for a single stage."""
    timestamp: str
    stage: str
    status: str  # started, completed, error
    message: str
    details: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = None
    tokens: Optional[int] = None
    cost: Optional[float] = None


class LoggingOrchestrator(OpusMetaOrchestrator):
    """
    Wrapper around OpusMetaOrchestrator that emits WebSocket events
    for real-time UI updates.
    """

    def __init__(self, socket_id: str, *args, **kwargs):
        # Set instance variables BEFORE super().__init__() because parent may call _log()
        self.socket_id = socket_id
        self.stage_start_time = None
        self.total_tokens = 0
        self.stage_logs: List[StageLog] = []
        # Now call parent init
        super().__init__(*args, **kwargs)

    def _emit_log(self, stage: str, status: str, message: str,
                  details: dict = None, tokens: int = None, cost: float = None):
        """Emit a log event via WebSocket."""
        duration_ms = None
        if self.stage_start_time and status in ('completed', 'error'):
            duration_ms = int((time.time() - self.stage_start_time) * 1000)

        log = StageLog(
            timestamp=datetime.now().strftime("%H:%M:%S.%f")[:-3],
            stage=stage,
            status=status,
            message=message,
            details=details,
            duration_ms=duration_ms,
            tokens=tokens,
            cost=cost,
        )
        self.stage_logs.append(log)

        socketio.emit('stage_log', asdict(log), room=self.socket_id)

        if status == 'started':
            self.stage_start_time = time.time()

    def _log(self, message: str):
        """Override parent _log to emit via WebSocket."""
        # Call parent if exists
        if self.logger:
            self.logger.info(message)
        # Also emit to frontend
        socketio.emit('debug_log', {'message': message}, room=self.socket_id)

    def run(self, issue: str, repo_path: Optional[str] = None):
        """Run with WebSocket logging."""
        self._emit_log("orchestrator", "started", f"Starting task: {issue[:100]}...")

        try:
            # Override internal methods to capture stages
            original_run_context = self._run_context_agent
            original_run_engineering = self._run_feature_engineering
            original_run_review = self._run_feature_review

            def logged_context(state, plan):
                model = plan.context_model if plan else 'unknown'
                self._emit_log("context", "started", f"Gathering context...",
                             details={"model": model})
                result = original_run_context(state, plan)
                content = result.content if hasattr(result, 'content') else ''
                self._emit_log("context", "completed",
                             f"Context gathered ({len(state.context_summary)} chars)",
                             details={
                                 "model": model,
                                 "output_preview": content[:500] if content else None,
                                 "context_summary": state.context_summary[:300] if state.context_summary else None,
                             },
                             tokens=getattr(result, 'input_tokens', 0) + getattr(result, 'output_tokens', 0),
                             cost=result.cost if hasattr(result, 'cost') else None)
                return result

            def logged_engineering(state, plan, feature, accumulated):
                model = plan.engineering_model if plan else 'unknown'
                self._emit_log("engineering", "started",
                             f"Implementing: {feature.description[:80]}",
                             details={"model": model, "feature_id": feature.id})
                result = original_run_engineering(state, plan, feature, accumulated)
                content = result.content if hasattr(result, 'content') else ''
                self._emit_log("engineering", "completed",
                             f"Feature implemented",
                             details={
                                 "model": model,
                                 "feature_id": feature.id,
                                 "output_preview": content[:800] if content else None,
                             },
                             tokens=getattr(result, 'input_tokens', 0) + getattr(result, 'output_tokens', 0),
                             cost=result.cost if hasattr(result, 'cost') else None)
                return result

            def logged_review(state, plan, feature, code):
                model = plan.review_model if plan else 'unknown'
                self._emit_log("review", "started", f"Reviewing feature {feature.id}...",
                             details={"model": model, "feature_id": feature.id})
                result = original_run_review(state, plan, feature, code)
                content = result.content if hasattr(result, 'content') else str(result)
                is_approved = 'APPROVED' in content.upper() or 'LGTM' in content.upper()
                status = "approved" if is_approved else "needs revision"
                self._emit_log("review", "completed",
                             f"Review: {status}",
                             details={
                                 "model": model,
                                 "feature_id": feature.id,
                                 "approved": is_approved,
                                 "output_preview": content[:500] if content else None,
                             },
                             tokens=getattr(result, 'input_tokens', 0) + getattr(result, 'output_tokens', 0),
                             cost=result.cost if hasattr(result, 'cost') else None)
                return result

            self._run_context_agent = logged_context
            self._run_feature_engineering = logged_engineering
            self._run_feature_review = logged_review

            # Run the actual orchestration
            result = super().run(issue, repo_path)

            self._emit_log("orchestrator", "completed",
                         f"Task completed: {result.features_completed}/{result.features_total} features",
                         details={
                             "features_completed": result.features_completed,
                             "features_total": result.features_total,
                             "execution_passed": result.execution_passed,
                         },
                         cost=result.total_cost)

            return result

        except Exception as e:
            self._emit_log("orchestrator", "error", f"Error: {str(e)}")
            raise


def list_presets_info():
    """Get detailed info about all presets."""
    return [
        {
            "id": name,
            "name": preset.name,
            "description": preset.description,
            "models": preset.allowed_models,
            "default_context": preset.default_context,
            "default_engineering": preset.default_engineering,
            "default_review": preset.default_review,
        }
        for name, preset in PRESETS.items()
    ]


def list_models_info():
    """Get detailed info about all models."""
    return [
        {
            "id": name,
            "provider": config.provider.value,
            "speed_tok_s": config.speed_tok_s,
            "input_price_per_m": config.input_price_per_m,
            "output_price_per_m": config.output_price_per_m,
            "context_window": config.context_window,
            "capabilities": config.capabilities,
        }
        for name, config in MODEL_REGISTRY.items()
    ]


@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html',
                         presets=list_presets_info(),
                         models=list_models_info())


@app.route('/api/presets')
def api_presets():
    """API endpoint to get all presets."""
    return jsonify(list_presets_info())


@app.route('/api/models')
def api_models():
    """API endpoint to get all models."""
    return jsonify(list_models_info())


@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection."""
    print(f"Client connected: {request.sid}")
    emit('connected', {'sid': request.sid})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection."""
    print(f"Client disconnected: {request.sid}")
    # Clean up any active runs for this client
    if request.sid in active_runs:
        del active_runs[request.sid]


@socketio.on('run_task')
def handle_run_task(data):
    """Handle task execution request."""
    sid = request.sid
    task = data.get('task', '')
    preset_name = data.get('preset', 'opus-optimized')
    repo_path = data.get('repo_path')

    if not task.strip():
        emit('error', {'message': 'Task cannot be empty'})
        return

    # Mark this run as active
    active_runs[sid] = {
        'task': task,
        'preset': preset_name,
        'started_at': time.time(),
        'status': 'running'
    }

    emit('run_started', {
        'task': task,
        'preset': preset_name,
        'started_at': datetime.now().isoformat()
    })

    # Run in background thread
    def run_orchestrator():
        try:
            client = MultiProviderClient()
            preset = get_preset(preset_name)

            orchestrator = LoggingOrchestrator(
                socket_id=sid,
                client=client,
                preset=preset,
                max_retries_per_feature=2,
                use_learned_prompt=True,
                use_learned_model_selection=True,
            )

            start_time = time.time()
            result = orchestrator.run(issue=task, repo_path=repo_path)
            elapsed = time.time() - start_time

            # Extract code if present
            executor = CodeExecutor()
            code = executor.extract_code(result.state.final_answer) if result.state.final_answer else None

            # Emit final result
            socketio.emit('run_completed', {
                'success': result.execution_passed,
                'elapsed_seconds': elapsed,
                'total_cost': result.total_cost,
                'features_completed': result.features_completed,
                'features_total': result.features_total,
                'final_answer': result.state.final_answer,
                'code': code,
                'plan': {
                    'archetype': getattr(result.plan, 'archetype', None),
                    'features': len(getattr(result.plan, 'features', [])),
                } if result.plan else None,
                'stage_logs': [asdict(log) for log in orchestrator.stage_logs],
            }, room=sid)

            active_runs[sid]['status'] = 'completed'

        except Exception as e:
            traceback.print_exc()
            socketio.emit('run_error', {
                'error': str(e),
                'traceback': traceback.format_exc()
            }, room=sid)
            active_runs[sid]['status'] = 'error'

    thread = threading.Thread(target=run_orchestrator)
    thread.daemon = True
    thread.start()


@socketio.on('run_baseline')
def handle_run_baseline(data):
    """Handle baseline (single Opus call) execution."""
    sid = request.sid
    task = data.get('task', '')

    if not task.strip():
        emit('error', {'message': 'Task cannot be empty'})
        return

    emit('run_started', {
        'task': task,
        'preset': 'baseline',
        'started_at': datetime.now().isoformat()
    })

    def run_baseline():
        try:
            client = MultiProviderClient()
            runner = OpusBaselineRunner(client)

            socketio.emit('stage_log', {
                'timestamp': datetime.now().strftime("%H:%M:%S.%f")[:-3],
                'stage': 'baseline',
                'status': 'started',
                'message': 'Running single Opus call...',
            }, room=sid)

            start_time = time.time()
            result = runner.run(task=task, max_tokens=4000)
            elapsed = time.time() - start_time

            # Extract and test code
            executor = CodeExecutor()
            code = executor.extract_code(result.content)
            exec_passed = False
            if code:
                exec_result = executor.execute(code)
                exec_passed = exec_result.success

            socketio.emit('stage_log', {
                'timestamp': datetime.now().strftime("%H:%M:%S.%f")[:-3],
                'stage': 'baseline',
                'status': 'completed',
                'message': f'Completed in {elapsed:.1f}s',
                'cost': result.cost,
                'tokens': result.input_tokens + result.output_tokens,
            }, room=sid)

            socketio.emit('run_completed', {
                'success': exec_passed,
                'elapsed_seconds': elapsed,
                'total_cost': result.cost,
                'features_completed': 1 if exec_passed else 0,
                'features_total': 1,
                'final_answer': result.content,
                'code': code,
                'plan': None,
                'stage_logs': [],
            }, room=sid)

        except Exception as e:
            traceback.print_exc()
            socketio.emit('run_error', {
                'error': str(e),
                'traceback': traceback.format_exc()
            }, room=sid)

    thread = threading.Thread(target=run_baseline)
    thread.daemon = True
    thread.start()


if __name__ == '__main__':
    print("=" * 60)
    print("OPUS META-ORCHESTRATOR FRONTEND")
    print("=" * 60)
    print(f"Available presets: {list(PRESETS.keys())}")
    print(f"Available models: {list(MODEL_REGISTRY.keys())}")
    print()
    print("Starting server at http://localhost:5050")
    print("=" * 60)

    # Disable debug/reloader to prevent constant restarts from temp file changes
    socketio.run(app, host='0.0.0.0', port=5050, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
