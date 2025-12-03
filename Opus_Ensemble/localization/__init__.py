"""
Localization module for Opus Ensemble.

Parallel localization using multiple strategies:
- AST-based search
- BM25 + embedding similarity
- Knowledge graph traversal
- Consensus voting across strategies
"""

from .ast_search import ASTSearcher
from .dense_sparse import DenseSparseRetriever
from .knowledge_graph import KnowledgeGraphBuilder
from .consensus import LocalizationConsensus, LocalizationResult

__all__ = [
    "ASTSearcher",
    "DenseSparseRetriever",
    "KnowledgeGraphBuilder",
    "LocalizationConsensus",
    "LocalizationResult",
]
