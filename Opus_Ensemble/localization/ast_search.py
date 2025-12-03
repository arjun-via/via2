"""
AST-based code search for Opus Ensemble.

Parses Python files using the ast module to build an index of:
- Class definitions
- Method definitions
- Function definitions
- Import statements

Then allows searching for specific patterns.
"""

import ast
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class CodeEntity:
    """A code entity (class, method, function) found in the codebase."""
    name: str
    type: str  # "class", "method", "function"
    file_path: str
    line_start: int
    line_end: int
    parent_class: Optional[str] = None
    docstring: Optional[str] = None
    source: Optional[str] = None


@dataclass
class FileIndex:
    """Index of code entities in a single file."""
    file_path: str
    classes: Dict[str, CodeEntity] = field(default_factory=dict)
    methods: Dict[str, List[CodeEntity]] = field(default_factory=dict)  # class_name -> methods
    functions: Dict[str, CodeEntity] = field(default_factory=dict)
    imports: List[str] = field(default_factory=list)


@dataclass
class SearchResult:
    """Result from an AST search."""
    file_path: str
    score: float
    entities: List[CodeEntity]
    context: Optional[str] = None


class ASTSearcher:
    """
    AST-based code searcher for Python repositories.

    Usage:
        searcher = ASTSearcher(repo_path="/path/to/repo")
        searcher.index()

        results = searcher.search_class("MyClass")
        results = searcher.search_method("my_method")
        results = searcher.search_code("pattern.*regex")
    """

    def __init__(self, repo_path: str, exclude_patterns: Optional[List[str]] = None):
        """
        Initialize AST searcher.

        Args:
            repo_path: Path to the repository root
            exclude_patterns: Glob patterns to exclude (default: tests, __pycache__, .git)
        """
        self.repo_path = Path(repo_path)
        self.exclude_patterns = exclude_patterns or [
            "**/test_*.py",
            "**/*_test.py",
            "**/tests/**",
            "**/__pycache__/**",
            "**/.git/**",
            "**/venv/**",
            "**/env/**",
            "**/.venv/**",
        ]

        self.files: Dict[str, FileIndex] = {}
        self.class_index: Dict[str, List[str]] = {}  # class_name -> file_paths
        self.method_index: Dict[str, List[Tuple[str, str]]] = {}  # method_name -> [(file, class)]
        self.function_index: Dict[str, List[str]] = {}  # func_name -> file_paths

        self._indexed = False

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

    def _extract_docstring(self, node: ast.AST) -> Optional[str]:
        """Extract docstring from a node."""
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and
            node.body and isinstance(node.body[0], ast.Expr) and
            isinstance(node.body[0].value, ast.Constant) and
            isinstance(node.body[0].value.value, str)):
            return node.body[0].value.value
        return None

    def _index_file(self, file_path: Path) -> Optional[FileIndex]:
        """Index a single Python file."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content)
        except (SyntaxError, UnicodeDecodeError):
            return None

        rel_path = str(file_path.relative_to(self.repo_path))
        index = FileIndex(file_path=rel_path)
        lines = content.split("\n")

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Index class
                entity = CodeEntity(
                    name=node.name,
                    type="class",
                    file_path=rel_path,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    docstring=self._extract_docstring(node),
                )
                index.classes[node.name] = entity

                # Index methods within class
                index.methods[node.name] = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method = CodeEntity(
                            name=item.name,
                            type="method",
                            file_path=rel_path,
                            line_start=item.lineno,
                            line_end=item.end_lineno or item.lineno,
                            parent_class=node.name,
                            docstring=self._extract_docstring(item),
                        )
                        index.methods[node.name].append(method)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Top-level function (not method)
                # Check if this function is inside a class (i.e., it's a method)
                def is_inside_class(fn_node, tree):
                    for parent in ast.walk(tree):
                        if isinstance(parent, ast.ClassDef):
                            body = getattr(parent, 'body', [])
                            if isinstance(body, list) and fn_node in body:
                                return True
                    return False

                if not is_inside_class(node, tree):
                    entity = CodeEntity(
                        name=node.name,
                        type="function",
                        file_path=rel_path,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        docstring=self._extract_docstring(node),
                    )
                    index.functions[node.name] = entity

            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        index.imports.append(alias.name)
                else:
                    module = node.module or ""
                    for alias in node.names:
                        index.imports.append(f"{module}.{alias.name}")

        return index

    def index(self) -> int:
        """
        Index the entire repository.

        Returns:
            Number of files indexed
        """
        self.files.clear()
        self.class_index.clear()
        self.method_index.clear()
        self.function_index.clear()

        python_files = self._get_python_files()

        for file_path in python_files:
            file_index = self._index_file(file_path)
            if file_index:
                self.files[file_index.file_path] = file_index

                # Build reverse indexes
                for class_name in file_index.classes:
                    if class_name not in self.class_index:
                        self.class_index[class_name] = []
                    self.class_index[class_name].append(file_index.file_path)

                for class_name, methods in file_index.methods.items():
                    for method in methods:
                        if method.name not in self.method_index:
                            self.method_index[method.name] = []
                        self.method_index[method.name].append((file_index.file_path, class_name))

                for func_name in file_index.functions:
                    if func_name not in self.function_index:
                        self.function_index[func_name] = []
                    self.function_index[func_name].append(file_index.file_path)

        self._indexed = True
        return len(self.files)

    def search_class(self, class_name: str) -> List[SearchResult]:
        """
        Search for a class by name.

        Args:
            class_name: Name of the class (exact or partial match)

        Returns:
            List of SearchResult sorted by score
        """
        if not self._indexed:
            self.index()

        results = []

        # Exact match
        if class_name in self.class_index:
            for file_path in self.class_index[class_name]:
                entity = self.files[file_path].classes[class_name]
                results.append(SearchResult(
                    file_path=file_path,
                    score=1.0,
                    entities=[entity],
                ))

        # Partial match
        for name, file_paths in self.class_index.items():
            if class_name.lower() in name.lower() and name != class_name:
                for file_path in file_paths:
                    entity = self.files[file_path].classes[name]
                    results.append(SearchResult(
                        file_path=file_path,
                        score=0.5,
                        entities=[entity],
                    ))

        return sorted(results, key=lambda r: -r.score)

    def search_method_in_class(self, class_name: str, method_name: str) -> List[SearchResult]:
        """
        Search for a method within a specific class.

        Args:
            class_name: Name of the containing class
            method_name: Name of the method

        Returns:
            List of SearchResult
        """
        if not self._indexed:
            self.index()

        results = []

        # Find class first
        if class_name not in self.class_index:
            return results

        for file_path in self.class_index[class_name]:
            file_index = self.files[file_path]
            if class_name in file_index.methods:
                for method in file_index.methods[class_name]:
                    if method.name == method_name:
                        results.append(SearchResult(
                            file_path=file_path,
                            score=1.0,
                            entities=[method],
                        ))
                    elif method_name.lower() in method.name.lower():
                        results.append(SearchResult(
                            file_path=file_path,
                            score=0.5,
                            entities=[method],
                        ))

        return sorted(results, key=lambda r: -r.score)

    def search_method(self, method_name: str) -> List[SearchResult]:
        """
        Search for a method across all classes.

        Args:
            method_name: Name of the method

        Returns:
            List of SearchResult
        """
        if not self._indexed:
            self.index()

        results = []

        # Exact match
        if method_name in self.method_index:
            for file_path, class_name in self.method_index[method_name]:
                file_index = self.files[file_path]
                for method in file_index.methods.get(class_name, []):
                    if method.name == method_name:
                        results.append(SearchResult(
                            file_path=file_path,
                            score=1.0,
                            entities=[method],
                        ))

        # Partial match
        for name, locations in self.method_index.items():
            if method_name.lower() in name.lower() and name != method_name:
                for file_path, class_name in locations:
                    file_index = self.files[file_path]
                    for method in file_index.methods.get(class_name, []):
                        if method.name == name:
                            results.append(SearchResult(
                                file_path=file_path,
                                score=0.5,
                                entities=[method],
                            ))

        return sorted(results, key=lambda r: -r.score)

    def search_function(self, func_name: str) -> List[SearchResult]:
        """
        Search for a top-level function.

        Args:
            func_name: Name of the function

        Returns:
            List of SearchResult
        """
        if not self._indexed:
            self.index()

        results = []

        if func_name in self.function_index:
            for file_path in self.function_index[func_name]:
                entity = self.files[file_path].functions[func_name]
                results.append(SearchResult(
                    file_path=file_path,
                    score=1.0,
                    entities=[entity],
                ))

        # Partial match
        for name, file_paths in self.function_index.items():
            if func_name.lower() in name.lower() and name != func_name:
                for file_path in file_paths:
                    entity = self.files[file_path].functions[name]
                    results.append(SearchResult(
                        file_path=file_path,
                        score=0.5,
                        entities=[entity],
                    ))

        return sorted(results, key=lambda r: -r.score)

    def search_code(self, pattern: str, max_results: int = 20) -> List[SearchResult]:
        """
        Search for code matching a regex pattern.

        Args:
            pattern: Regex pattern to search for
            max_results: Maximum number of results

        Returns:
            List of SearchResult
        """
        if not self._indexed:
            self.index()

        results = []
        regex = re.compile(pattern, re.IGNORECASE | re.MULTILINE)

        for file_path, file_index in self.files.items():
            full_path = self.repo_path / file_path
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
                matches = regex.findall(content)
                if matches:
                    # Score based on number of matches
                    score = min(1.0, len(matches) / 10)
                    results.append(SearchResult(
                        file_path=file_path,
                        score=score,
                        entities=[],
                        context=f"Found {len(matches)} matches",
                    ))
            except Exception:
                continue

        results = sorted(results, key=lambda r: -r.score)
        return results[:max_results]

    def get_file_content(self, file_path: str, line_start: int = None, line_end: int = None) -> str:
        """
        Get content of a file, optionally with line range.

        Args:
            file_path: Relative path to file
            line_start: Optional start line (1-indexed)
            line_end: Optional end line (1-indexed)

        Returns:
            File content
        """
        full_path = self.repo_path / file_path
        content = full_path.read_text(encoding="utf-8", errors="replace")

        if line_start or line_end:
            lines = content.split("\n")
            start = (line_start - 1) if line_start else 0
            end = line_end if line_end else len(lines)
            return "\n".join(lines[start:end])

        return content

    def get_ranked_files(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """
        Get ranked list of files most relevant to a query.

        Uses a combination of class, method, function, and code search.

        Args:
            query: Search query (may contain class/method names or keywords)
            top_k: Number of results to return

        Returns:
            Ranked list of SearchResult
        """
        if not self._indexed:
            self.index()

        # Extract potential identifiers from query
        words = re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', query)

        file_scores: Dict[str, float] = {}
        file_entities: Dict[str, List[CodeEntity]] = {}

        for word in words:
            # Search classes
            for result in self.search_class(word):
                if result.file_path not in file_scores:
                    file_scores[result.file_path] = 0
                    file_entities[result.file_path] = []
                file_scores[result.file_path] += result.score * 2  # Classes weighted higher
                file_entities[result.file_path].extend(result.entities)

            # Search methods
            for result in self.search_method(word):
                if result.file_path not in file_scores:
                    file_scores[result.file_path] = 0
                    file_entities[result.file_path] = []
                file_scores[result.file_path] += result.score * 1.5
                file_entities[result.file_path].extend(result.entities)

            # Search functions
            for result in self.search_function(word):
                if result.file_path not in file_scores:
                    file_scores[result.file_path] = 0
                    file_entities[result.file_path] = []
                file_scores[result.file_path] += result.score
                file_entities[result.file_path].extend(result.entities)

        # Code search as fallback
        code_results = self.search_code(query, max_results=10)
        for result in code_results:
            if result.file_path not in file_scores:
                file_scores[result.file_path] = 0
                file_entities[result.file_path] = []
            file_scores[result.file_path] += result.score * 0.5

        # Build final results
        results = []
        for file_path, score in sorted(file_scores.items(), key=lambda x: -x[1]):
            results.append(SearchResult(
                file_path=file_path,
                score=score,
                entities=file_entities.get(file_path, []),
            ))

        return results[:top_k]
