import subprocess

from alo.agentic_loops.core.tools import ToolRegistry


def test_tool_registry_file_ops(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_a = workspace / "a.txt"
    file_a.write_text("hello\nworld\n")

    registry = ToolRegistry(workspace_root=str(workspace))

    files = registry.list_files()
    assert "a.txt" in files

    content = registry.read_file("a.txt")
    assert "hello" in content

    registry.write_file("b.txt", "data")
    assert (workspace / "b.txt").read_text() == "data"

    grep_results = registry.grep_search("world")
    assert any("a.txt" in hit["path"] for hit in grep_results)


def test_tool_registry_run_command(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    registry = ToolRegistry(workspace_root=str(workspace))

    result = registry.run_command("echo 'hi'")
    assert result["returncode"] == 0
    assert "hi" in result["stdout"]

    bad = registry.run_command("ls does_not_exist")
    assert bad["returncode"] != 0
    assert bad["stderr"]
