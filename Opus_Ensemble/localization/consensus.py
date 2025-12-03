"""
Consensus localization for Opus Ensemble.

Combines results from multiple localization strategies:
- AST-based search
- BM25 + embedding retrieval
- Knowledge graph traversal

Uses weighted voting to produce final ranked list.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .ast_search import ASTSearcher, SearchResult as ASTResult
from .dense_sparse import DenseSparseRetriever, RetrievalResult
from .knowledge_graph import KnowledgeGraphBuilder, KGSearchResult


@dataclass
class LocalizationResult:
    """Final result from consensus localization."""
    file_path: str
    score: float
    confidence: float  # How many strategies agreed
    ast_score: float = 0.0
    bm25_score: float = 0.0
    kg_score: float = 0.0
    context: Optional[str] = None


@dataclass
class LocalizationConfig:
    """Configuration for localization consensus."""
    ast_weight: float = 0.4
    bm25_weight: float = 0.35
    kg_weight: float = 0.25
    top_k_per_strategy: int = 10
    final_top_k: int = 5
    min_confidence: float = 0.0  # Minimum agreement threshold


class LocalizationConsensus:
    """
    Combines multiple localization strategies using weighted voting.

    Usage:
        consensus = LocalizationConsensus(repo_path="/path/to/repo")

        results = consensus.localize(
            "Fix authentication bug in user login",
            top_k=5
        )

        for result in results:
            print(f"{result.file_path}: {result.score:.2f} (confidence: {result.confidence:.0%})")
    """

    def __init__(
        self,
        repo_path: str,
        config: Optional[LocalizationConfig] = None,
        exclude_patterns: Optional[List[str]] = None
    ):
        """
        Initialize consensus localizer.

        Args:
            repo_path: Path to repository
            config: Optional configuration
            exclude_patterns: File patterns to exclude
        """
        self.repo_path = Path(repo_path)
        self.config = config or LocalizationConfig()
        self.exclude_patterns = exclude_patterns

        # Initialize searchers
        self.ast_searcher = ASTSearcher(
            repo_path=repo_path,
            exclude_patterns=exclude_patterns
        )
        self.bm25_retriever = DenseSparseRetriever(
            repo_path=repo_path,
            exclude_patterns=exclude_patterns
        )
        self.kg_builder = KnowledgeGraphBuilder(
            repo_path=repo_path,
            exclude_patterns=exclude_patterns
        )

        self._indexed = False

    def index(self) -> Dict[str, int]:
        """
        Index the repository with all strategies.

        Returns:
            Dict with count per strategy
        """
        counts = {}

        # Run indexing in parallel
        with ThreadPoolExecutor(max_workers=3) as pool:
            ast_future = pool.submit(self.ast_searcher.index)
            bm25_future = pool.submit(self.bm25_retriever.index)
            kg_future = pool.submit(self.kg_builder.build)

            counts["ast"] = ast_future.result()
            counts["bm25"] = bm25_future.result()
            counts["kg"] = kg_future.result()

        self._indexed = True
        return counts

    def _normalize_scores(self, scores: List[float]) -> List[float]:
        """Normalize scores to 0-1 range."""
        if not scores:
            return []
        max_score = max(scores)
        if max_score == 0:
            return [0] * len(scores)
        return [s / max_score for s in scores]

    def localize(
        self,
        query: str,
        top_k: Optional[int] = None
    ) -> List[LocalizationResult]:
        """
        Localize relevant files for a query.

        Args:
            query: Issue description or search query
            top_k: Number of results (default: config.final_top_k)

        Returns:
            Ranked list of LocalizationResult
        """
        if not self._indexed:
            self.index()

        top_k = top_k or self.config.final_top_k
        k_per = self.config.top_k_per_strategy

        # Get results from each strategy
        ast_results = self.ast_searcher.get_ranked_files(query, top_k=k_per)
        bm25_results = self.bm25_retriever.get_ranked_files(query, top_k=k_per)
        kg_results = self.kg_builder.get_ranked_files(query, top_k=k_per)

        # Collect all file scores
        file_scores: Dict[str, Dict[str, float]] = {}

        # Process AST results
        ast_scores = [r.score for r in ast_results]
        ast_normalized = self._normalize_scores(ast_scores)
        for result, norm_score in zip(ast_results, ast_normalized):
            if result.file_path not in file_scores:
                file_scores[result.file_path] = {"ast": 0, "bm25": 0, "kg": 0}
            file_scores[result.file_path]["ast"] = norm_score

        # Process BM25 results
        bm25_scores = [r.score for r in bm25_results]
        bm25_normalized = self._normalize_scores(bm25_scores)
        for result, norm_score in zip(bm25_results, bm25_normalized):
            if result.file_path not in file_scores:
                file_scores[result.file_path] = {"ast": 0, "bm25": 0, "kg": 0}
            file_scores[result.file_path]["bm25"] = norm_score

        # Process KG results
        kg_scores = [r.score for r in kg_results]
        kg_normalized = self._normalize_scores(kg_scores)
        for result, norm_score in zip(kg_results, kg_normalized):
            if result.file_path not in file_scores:
                file_scores[result.file_path] = {"ast": 0, "bm25": 0, "kg": 0}
            file_scores[result.file_path]["kg"] = norm_score

        # Calculate weighted scores and confidence
        results = []
        for file_path, scores in file_scores.items():
            # Weighted combination
            weighted_score = (
                self.config.ast_weight * scores["ast"] +
                self.config.bm25_weight * scores["bm25"] +
                self.config.kg_weight * scores["kg"]
            )

            # Confidence = how many strategies found this file
            num_strategies = sum(1 for s in scores.values() if s > 0)
            confidence = num_strategies / 3.0

            # Skip if below minimum confidence
            if confidence < self.config.min_confidence:
                continue

            results.append(LocalizationResult(
                file_path=file_path,
                score=weighted_score,
                confidence=confidence,
                ast_score=scores["ast"],
                bm25_score=scores["bm25"],
                kg_score=scores["kg"],
            ))

        # Sort by score
        results.sort(key=lambda r: (-r.score, -r.confidence))
        return results[:top_k]

    def get_file_content(self, file_path: str) -> str:
        """
        Get the content of a file.

        Args:
            file_path: Relative path to file

        Returns:
            File content
        """
        full_path = self.repo_path / file_path
        return full_path.read_text(encoding="utf-8", errors="replace")

    def get_relevant_context(
        self,
        query: str,
        top_k: int = 5,
        max_tokens: int = 8000
    ) -> Tuple[str, List[LocalizationResult]]:
        """
        Get relevant code context for a query.

        Returns the content of top-k files, truncated to max_tokens.

        Args:
            query: Issue description
            top_k: Number of files to include
            max_tokens: Approximate token limit (chars / 4)

        Returns:
            Tuple of (combined_context, localization_results)
        """
        results = self.localize(query, top_k=top_k)

        context_parts = []
        total_chars = 0
        max_chars = max_tokens * 4  # Rough char to token ratio

        for result in results:
            try:
                content = self.get_file_content(result.file_path)
            except Exception:
                continue

            # Add file header
            header = f"\n# FILE: {result.file_path}\n# Score: {result.score:.2f}, Confidence: {result.confidence:.0%}\n\n"

            # Check if we can fit this file
            if total_chars + len(header) + len(content) > max_chars:
                # Try to include truncated version
                remaining = max_chars - total_chars - len(header) - 100
                if remaining > 1000:
                    content = content[:remaining] + "\n\n... [truncated]"
                else:
                    break

            context_parts.append(header + content)
            total_chars += len(header) + len(content)

        return "\n".join(context_parts), results


def test_localization():
    """Quick test of localization consensus."""
    import tempfile
    import os

    # Create a temporary repo
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some test files
        Path(tmpdir, "auth.py").write_text("""
class AuthManager:
    def login(self, username, password):
        '''Handle user login.'''
        if not self.validate(username, password):
            raise AuthError("Invalid credentials")
        return self.create_session(username)

    def validate(self, username, password):
        '''Validate user credentials.'''
        user = self.get_user(username)
        return user and user.check_password(password)
""")

        Path(tmpdir, "user.py").write_text("""
class User:
    def __init__(self, username, password_hash):
        self.username = username
        self.password_hash = password_hash

    def check_password(self, password):
        '''Check if password matches.'''
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest() == self.password_hash
""")

        Path(tmpdir, "errors.py").write_text("""
class AuthError(Exception):
    '''Authentication error.'''
    pass

class ValidationError(Exception):
    '''Validation error.'''
    pass
""")

        # Test consensus
        consensus = LocalizationConsensus(repo_path=tmpdir)
        counts = consensus.index()
        print(f"Indexed: {counts}")

        results = consensus.localize("fix login authentication bug", top_k=3)
        print("\nLocalization results:")
        for r in results:
            print(f"  {r.file_path}: score={r.score:.2f}, confidence={r.confidence:.0%}")
            print(f"    AST={r.ast_score:.2f}, BM25={r.bm25_score:.2f}, KG={r.kg_score:.2f}")


if __name__ == "__main__":
    test_localization()
