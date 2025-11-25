"""
=============================================================================
SCRIPT NAME: exceptions.py
=============================================================================

Custom exceptions for ALO orchestrator.

These exceptions enforce the "FAIL IS FAIL" policy - no silent fallbacks,
all errors are explicit and actionable.

VERSION: 1.0
LAST UPDATED: 2025-01-24
=============================================================================
"""


class ALOError(Exception):
    """Base exception for all ALO-related errors."""
    pass


class ClientInitializationError(ALOError):
    """Raised when a model client fails to initialize.

    This replaces the silent StubClient fallback. When an API client
    cannot be created (missing API key, invalid config, etc.), we fail
    explicitly rather than returning fake responses.
    """

    def __init__(self, client_name: str, original_error: Exception):
        self.client_name = client_name
        self.original_error = original_error
        message = (
            f"Failed to initialize '{client_name}' client: {original_error}\n"
            f"Check your API keys and configuration. "
            f"Set the appropriate environment variable or fix config/config.yaml."
        )
        super().__init__(message)


class AgentExecutionError(ALOError):
    """Raised when an agent fails to execute properly.

    This replaces silent TypeError catches. When an agent's run() method
    fails, we surface the actual error rather than trying alternate signatures.
    """

    def __init__(self, agent_name: str, original_error: Exception):
        self.agent_name = agent_name
        self.original_error = original_error
        message = (
            f"Agent '{agent_name}' failed during execution: {original_error}\n"
            f"This may indicate a bug in the agent implementation or incompatible state."
        )
        super().__init__(message)


class ToolRegistryRequiredError(ALOError):
    """Raised when tool_registry is required but not provided.

    This replaces the optimistic 'assume success' fallback. Operations that
    require tool_registry (like running repro scripts) must fail explicitly
    if the registry is not available.
    """

    def __init__(self, operation: str):
        self.operation = operation
        message = (
            f"Operation '{operation}' requires tool_registry but none was provided.\n"
            f"Either provide a tool_registry or use a mode that doesn't require it."
        )
        super().__init__(message)


class FileReadError(ALOError):
    """Raised when a file cannot be read during context gathering.

    This replaces silent 'continue' on file read errors. When we can't read
    a relevant file, we report it clearly rather than silently skipping.
    """

    def __init__(self, file_path: str, original_error: Exception):
        self.file_path = file_path
        self.original_error = original_error
        message = (
            f"Failed to read file '{file_path}': {original_error}\n"
            f"Check that the file exists and is readable."
        )
        super().__init__(message)
