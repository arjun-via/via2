"""
Dense + Sparse retrieval for Opus Ensemble.

Combines:
- BM25 (sparse retrieval) for keyword matching
- Embedding similarity (dense retrieval) for semantic matching

Note: For full embedding support, requires sentence-transformers or an embedding API.
This implementation provides BM25 + optional embedding fallback.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class RetrievalResult:
    """Result from dense/sparse retrieval."""
    file_path: str
    score: float
    bm25_score: float
    embedding_score: float
    snippet: Optional[str] = None


class BM25Index:
    """
    BM25 index for sparse retrieval.

    BM25 is a ranking function used by search engines to rank documents
    based on query terms appearing in each document.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 index.

        Args:
            k1: Term frequency saturation parameter
            b: Length normalization parameter
        """
        self.k1 = k1
        self.b = b

        self.documents: Dict[str, str] = {}  # doc_id -> content
        self.doc_lengths: Dict[str, int] = {}
        self.avg_doc_length: float = 0
        self.doc_freqs: Dict[str, int] = {}  # term -> num docs containing term
        self.term_freqs: Dict[str, Dict[str, int]] = {}  # doc_id -> term -> count
        self.N: int = 0  # Number of documents

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization: lowercase and split on non-alphanumeric."""
        text = text.lower()
        # Split on non-alphanumeric, keep underscores for code
        tokens = re.findall(r'[a-z0-9_]+', text)
        return tokens

    def add_document(self, doc_id: str, content: str):
        """Add a document to the index."""
        tokens = self._tokenize(content)

        self.documents[doc_id] = content
        self.doc_lengths[doc_id] = len(tokens)
        self.term_freqs[doc_id] = Counter(tokens)

        # Update document frequencies
        for term in set(tokens):
            self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1

        self.N = len(self.documents)
        self.avg_doc_length = sum(self.doc_lengths.values()) / max(1, self.N)

    def _idf(self, term: str) -> float:
        """Calculate IDF for a term."""
        df = self.doc_freqs.get(term, 0)
        if df == 0:
            return 0
        return math.log((self.N - df + 0.5) / (df + 0.5) + 1)

    def score(self, query: str, doc_id: str) -> float:
        """
        Calculate BM25 score for a query against a document.

        Args:
            query: Search query
            doc_id: Document ID

        Returns:
            BM25 score
        """
        if doc_id not in self.documents:
            return 0

        query_tokens = self._tokenize(query)
        doc_length = self.doc_lengths[doc_id]
        term_freqs = self.term_freqs[doc_id]

        score = 0
        for term in query_tokens:
            tf = term_freqs.get(term, 0)
            if tf == 0:
                continue

            idf = self._idf(term)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_length / self.avg_doc_length)
            score += idf * (numerator / denominator)

        return score

    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Search for documents matching the query.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of (doc_id, score) tuples sorted by score
        """
        scores = []
        for doc_id in self.documents:
            score = self.score(query, doc_id)
            if score > 0:
                scores.append((doc_id, score))

        scores.sort(key=lambda x: -x[1])
        return scores[:top_k]


class DenseSparseRetriever:
    """
    Combined dense + sparse retriever.

    Uses BM25 for sparse retrieval and optionally embedding similarity
    for dense retrieval. Results are combined using a weighted average.

    Usage:
        retriever = DenseSparseRetriever(repo_path="/path/to/repo")
        retriever.index()

        results = retriever.search("fix authentication bug", top_k=5)
    """

    def __init__(
        self,
        repo_path: str,
        bm25_weight: float = 0.5,
        embedding_weight: float = 0.5,
        exclude_patterns: Optional[List[str]] = None
    ):
        """
        Initialize retriever.

        Args:
            repo_path: Path to repository
            bm25_weight: Weight for BM25 scores (0-1)
            embedding_weight: Weight for embedding scores (0-1)
            exclude_patterns: File patterns to exclude
        """
        self.repo_path = Path(repo_path)
        self.bm25_weight = bm25_weight
        self.embedding_weight = embedding_weight
        self.exclude_patterns = exclude_patterns or [
            "**/test_*.py",
            "**/*_test.py",
            "**/tests/**",
            "**/__pycache__/**",
            "**/.git/**",
            "**/venv/**",
        ]

        self.bm25 = BM25Index()
        self.embeddings: Dict[str, List[float]] = {}  # doc_id -> embedding
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

    def index(self) -> int:
        """
        Index the repository.

        Returns:
            Number of files indexed
        """
        python_files = self._get_python_files()

        for file_path in python_files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                rel_path = str(file_path.relative_to(self.repo_path))
                self.bm25.add_document(rel_path, content)
            except Exception:
                continue

        self._indexed = True
        return len(self.bm25.documents)

    def _compute_embedding(self, text: str) -> Optional[List[float]]:
        """
        Compute embedding for text.

        This is a placeholder - in production you would use:
        - sentence-transformers
        - OpenAI embeddings API
        - etc.

        For now, returns None (BM25 only).
        """
        # TODO: Implement actual embedding computation
        # from sentence_transformers import SentenceTransformer
        # model = SentenceTransformer('all-MiniLM-L6-v2')
        # return model.encode(text).tolist()
        return None

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b:
            return 0

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0

        return dot / (norm_a * norm_b)

    def search(self, query: str, top_k: int = 10) -> List[RetrievalResult]:
        """
        Search for relevant files.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of RetrievalResult sorted by combined score
        """
        if not self._indexed:
            self.index()

        # BM25 search
        bm25_results = self.bm25.search(query, top_k=top_k * 2)

        # Normalize BM25 scores
        max_bm25 = max((score for _, score in bm25_results), default=1)

        results = []
        for doc_id, bm25_score in bm25_results:
            normalized_bm25 = bm25_score / max_bm25 if max_bm25 > 0 else 0

            # Embedding similarity (if available)
            embedding_score = 0.0
            query_emb = self._compute_embedding(query)
            if query_emb and doc_id in self.embeddings:
                embedding_score = self._cosine_similarity(query_emb, self.embeddings[doc_id])

            # Combined score
            if self.embedding_weight > 0 and embedding_score > 0:
                combined_score = (
                    self.bm25_weight * normalized_bm25 +
                    self.embedding_weight * embedding_score
                )
            else:
                combined_score = normalized_bm25

            # Get snippet
            content = self.bm25.documents.get(doc_id, "")
            snippet = self._get_snippet(content, query)

            results.append(RetrievalResult(
                file_path=doc_id,
                score=combined_score,
                bm25_score=normalized_bm25,
                embedding_score=embedding_score,
                snippet=snippet,
            ))

        results.sort(key=lambda r: -r.score)
        return results[:top_k]

    def _get_snippet(self, content: str, query: str, context_lines: int = 2) -> str:
        """Get a snippet around the first query match."""
        lines = content.split("\n")
        query_words = query.lower().split()

        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(word in line_lower for word in query_words):
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                return "\n".join(lines[start:end])

        # Return first few lines if no match
        return "\n".join(lines[:5])

    def get_ranked_files(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """
        Get ranked list of files relevant to query.

        This is the main interface for localization.

        Args:
            query: Issue description or search query
            top_k: Number of results

        Returns:
            Ranked list of files
        """
        return self.search(query, top_k)
