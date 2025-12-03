"""
Knowledge graph builder for Opus Ensemble.

Builds a dependency graph of:
- Import relationships
- Call relationships (which functions call which)
- Class inheritance

Then traverses the graph from issue keywords to find relevant files.
"""

import ast
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class GraphNode:
    """A node in the knowledge graph."""
    name: str
    type: str  # "module", "class", "function", "method"
    file_path: str
    line_start: int
    line_end: int


@dataclass
class GraphEdge:
    """An edge in the knowledge graph."""
    source: str  # node name
    target: str  # node name
    type: str  # "imports", "calls", "inherits", "contains"


@dataclass
class KGSearchResult:
    """Result from knowledge graph search."""
    file_path: str
    score: float
    nodes: List[GraphNode]
    paths: List[List[str]]  # Paths that led to this file


class KnowledgeGraphBuilder:
    """
    Builds and queries a knowledge graph of code dependencies.

    The graph captures:
    - Import relationships between modules
    - Function/method call relationships
    - Class inheritance hierarchies

    Usage:
        kg = KnowledgeGraphBuilder(repo_path="/path/to/repo")
        kg.build()

        results = kg.search("authentication error", top_k=5)
    """

    def __init__(self, repo_path: str, exclude_patterns: Optional[List[str]] = None):
        """
        Initialize knowledge graph builder.

        Args:
            repo_path: Path to repository
            exclude_patterns: File patterns to exclude
        """
        self.repo_path = Path(repo_path)
        self.exclude_patterns = exclude_patterns or [
            "**/test_*.py",
            "**/*_test.py",
            "**/tests/**",
            "**/__pycache__/**",
            "**/.git/**",
            "**/venv/**",
        ]

        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self.import_graph: Dict[str, Set[str]] = defaultdict(set)  # module -> imports
        self.call_graph: Dict[str, Set[str]] = defaultdict(set)  # caller -> callees
        self.inheritance_graph: Dict[str, Set[str]] = defaultdict(set)  # class -> bases
        self.file_to_module: Dict[str, str] = {}
        self.module_to_file: Dict[str, str] = {}

        self._built = False

    def _should_exclude(self, file_path: Path) -> bool:
        """Check if file should be excluded."""
        from fnmatch import fnmatch
        rel_path = str(file_path.relative_to(self.repo_path))
        return any(fnmatch(rel_path, pattern) for pattern in self.exclude_patterns)

    def _get_python_files(self) -> List[Path]:
        """Get all Python files in the repository."""
        files = []
        for py_file in self.repo_path.rglob("*.py"):
            if not self._should_exclude(py_file):
                files.append(py_file)
        return files

    def _path_to_module(self, file_path: Path) -> str:
        """Convert file path to module name."""
        rel_path = file_path.relative_to(self.repo_path)
        parts = list(rel_path.parts)

        # Remove .py extension
        if parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]

        # Remove __init__
        if parts[-1] == "__init__":
            parts = parts[:-1]

        return ".".join(parts)

    def _extract_calls(self, node: ast.AST) -> List[str]:
        """Extract function/method calls from an AST node."""
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
        return calls

    def _analyze_file(self, file_path: Path) -> None:
        """Analyze a single Python file and update the graph."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content)
        except (SyntaxError, UnicodeDecodeError):
            return

        rel_path = str(file_path.relative_to(self.repo_path))
        module_name = self._path_to_module(file_path)

        self.file_to_module[rel_path] = module_name
        self.module_to_file[module_name] = rel_path

        # Add module node
        self.nodes[module_name] = GraphNode(
            name=module_name,
            type="module",
            file_path=rel_path,
            line_start=1,
            line_end=len(content.split("\n")),
        )

        # Analyze imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.import_graph[module_name].add(alias.name)
                    self.edges.append(GraphEdge(
                        source=module_name,
                        target=alias.name,
                        type="imports",
                    ))

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self.import_graph[module_name].add(node.module)
                    self.edges.append(GraphEdge(
                        source=module_name,
                        target=node.module,
                        type="imports",
                    ))

            elif isinstance(node, ast.ClassDef):
                class_name = f"{module_name}.{node.name}"
                self.nodes[class_name] = GraphNode(
                    name=class_name,
                    type="class",
                    file_path=rel_path,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                )

                # Class contains relationship
                self.edges.append(GraphEdge(
                    source=module_name,
                    target=class_name,
                    type="contains",
                ))

                # Inheritance
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        self.inheritance_graph[class_name].add(base.id)
                        self.edges.append(GraphEdge(
                            source=class_name,
                            target=base.id,
                            type="inherits",
                        ))
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr
                        self.inheritance_graph[class_name].add(base_name)
                        self.edges.append(GraphEdge(
                            source=class_name,
                            target=base_name,
                            type="inherits",
                        ))

                # Analyze methods
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_name = f"{class_name}.{item.name}"
                        self.nodes[method_name] = GraphNode(
                            name=method_name,
                            type="method",
                            file_path=rel_path,
                            line_start=item.lineno,
                            line_end=item.end_lineno or item.lineno,
                        )

                        # Method calls
                        calls = self._extract_calls(item)
                        for call in calls:
                            self.call_graph[method_name].add(call)
                            self.edges.append(GraphEdge(
                                source=method_name,
                                target=call,
                                type="calls",
                            ))

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Top-level function
                func_name = f"{module_name}.{node.name}"
                self.nodes[func_name] = GraphNode(
                    name=func_name,
                    type="function",
                    file_path=rel_path,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                )

                self.edges.append(GraphEdge(
                    source=module_name,
                    target=func_name,
                    type="contains",
                ))

                # Function calls
                calls = self._extract_calls(node)
                for call in calls:
                    self.call_graph[func_name].add(call)
                    self.edges.append(GraphEdge(
                        source=func_name,
                        target=call,
                        type="calls",
                    ))

    def build(self) -> int:
        """
        Build the knowledge graph.

        Returns:
            Number of nodes in the graph
        """
        self.nodes.clear()
        self.edges.clear()
        self.import_graph.clear()
        self.call_graph.clear()
        self.inheritance_graph.clear()

        python_files = self._get_python_files()

        for file_path in python_files:
            self._analyze_file(file_path)

        self._built = True
        return len(self.nodes)

    def _find_nodes_by_name(self, name: str) -> List[GraphNode]:
        """Find nodes whose name contains the given string."""
        results = []
        name_lower = name.lower()
        for node_name, node in self.nodes.items():
            if name_lower in node_name.lower():
                results.append(node)
        return results

    def _trace_dependencies(self, node_name: str, depth: int = 2) -> Set[str]:
        """
        Trace dependencies from a node.

        Args:
            node_name: Starting node
            depth: Maximum traversal depth

        Returns:
            Set of related node names
        """
        visited = set()
        to_visit = [(node_name, 0)]

        while to_visit:
            current, current_depth = to_visit.pop(0)
            if current in visited or current_depth > depth:
                continue
            visited.add(current)

            # Follow imports
            for imported in self.import_graph.get(current, []):
                to_visit.append((imported, current_depth + 1))

            # Follow calls
            for called in self.call_graph.get(current, []):
                # Try to resolve to full name
                for node_name in self.nodes:
                    if node_name.endswith(f".{called}"):
                        to_visit.append((node_name, current_depth + 1))
                        break

            # Follow inheritance
            for base in self.inheritance_graph.get(current, []):
                for node_name in self.nodes:
                    if node_name.endswith(f".{base}"):
                        to_visit.append((node_name, current_depth + 1))
                        break

        return visited

    def search(self, query: str, top_k: int = 5) -> List[KGSearchResult]:
        """
        Search for relevant files based on query keywords.

        Traverses the knowledge graph from matching nodes to find
        related code.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of KGSearchResult
        """
        if not self._built:
            self.build()

        # Extract keywords from query
        keywords = re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', query)

        file_scores: Dict[str, float] = defaultdict(float)
        file_nodes: Dict[str, List[GraphNode]] = defaultdict(list)
        file_paths: Dict[str, List[List[str]]] = defaultdict(list)

        for keyword in keywords:
            # Find matching nodes
            matching_nodes = self._find_nodes_by_name(keyword)

            for node in matching_nodes:
                # Score the direct match
                file_scores[node.file_path] += 1.0
                file_nodes[node.file_path].append(node)

                # Trace dependencies
                related = self._trace_dependencies(node.name, depth=2)
                for related_name in related:
                    if related_name in self.nodes:
                        related_node = self.nodes[related_name]
                        file_scores[related_node.file_path] += 0.3
                        file_paths[related_node.file_path].append([node.name, related_name])

        # Build results
        results = []
        for file_path, score in sorted(file_scores.items(), key=lambda x: -x[1]):
            results.append(KGSearchResult(
                file_path=file_path,
                score=score,
                nodes=file_nodes.get(file_path, []),
                paths=file_paths.get(file_path, []),
            ))

        return results[:top_k]

    def get_ranked_files(self, query: str, top_k: int = 5) -> List[KGSearchResult]:
        """
        Get ranked list of files relevant to query.

        Main interface for localization.

        Args:
            query: Issue description
            top_k: Number of results

        Returns:
            Ranked list of files
        """
        return self.search(query, top_k)

    def get_file_dependencies(self, file_path: str) -> Dict[str, Set[str]]:
        """
        Get all dependencies for a file.

        Args:
            file_path: Relative file path

        Returns:
            Dict with "imports", "calls", "inherits" keys
        """
        if not self._built:
            self.build()

        module_name = self.file_to_module.get(file_path)
        if not module_name:
            return {"imports": set(), "calls": set(), "inherits": set()}

        deps = {
            "imports": self.import_graph.get(module_name, set()),
            "calls": set(),
            "inherits": set(),
        }

        # Collect calls and inheritance from all entities in file
        for node_name, node in self.nodes.items():
            if node.file_path == file_path:
                deps["calls"].update(self.call_graph.get(node_name, set()))
                deps["inherits"].update(self.inheritance_graph.get(node_name, set()))

        return deps
