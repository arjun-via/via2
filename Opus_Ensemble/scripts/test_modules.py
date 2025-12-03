#!/usr/bin/env python3
"""
Quick test script to verify all Opus Ensemble modules can be imported.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    """Test that all modules can be imported."""
    print("Testing Opus Ensemble module imports...\n")

    modules = []

    # Core modules
    print("1. Core modules:")
    try:
        from config import get_config, ModelMode
        print("   - config: OK")
        modules.append("config")
    except Exception as e:
        print(f"   - config: FAILED - {e}")

    try:
        from data_types import PatchCandidate, Strategy, EnsembleResult
        print("   - data_types: OK")
        modules.append("data_types")
    except Exception as e:
        print(f"   - data_types: FAILED - {e}")

    try:
        from api_client import EnsembleAPIClient
        print("   - api_client: OK")
        modules.append("api_client")
    except Exception as e:
        print(f"   - api_client: FAILED - {e}")

    try:
        from parallel_generator import ParallelGenerator
        print("   - parallel_generator: OK")
        modules.append("parallel_generator")
    except Exception as e:
        print(f"   - parallel_generator: FAILED - {e}")

    try:
        from verification import Verifier
        print("   - verification: OK")
        modules.append("verification")
    except Exception as e:
        print(f"   - verification: FAILED - {e}")

    try:
        from orchestrator import OpusEnsemble
        print("   - orchestrator: OK")
        modules.append("orchestrator")
    except Exception as e:
        print(f"   - orchestrator: FAILED - {e}")

    # Docker executor
    print("\n2. Docker executor:")
    try:
        from docker_executor import DockerExecutor, ContainerPool, get_swebench_image
        print("   - docker_executor: OK")
        modules.append("docker_executor")
    except Exception as e:
        print(f"   - docker_executor: FAILED - {e}")

    # Localization
    print("\n3. Localization:")
    try:
        from localization import (
            ASTSearcher,
            DenseSparseRetriever,
            KnowledgeGraphBuilder,
            LocalizationConsensus,
        )
        print("   - localization.ast_search: OK")
        print("   - localization.dense_sparse: OK")
        print("   - localization.knowledge_graph: OK")
        print("   - localization.consensus: OK")
        modules.append("localization")
    except Exception as e:
        print(f"   - localization: FAILED - {e}")

    # Reproduction
    print("\n4. Reproduction:")
    try:
        from reproduction import ReproductionGenerator, ReproductionResult
        print("   - reproduction.test_generator: OK")
        modules.append("reproduction")
    except Exception as e:
        print(f"   - reproduction: FAILED - {e}")

    # Correction
    print("\n5. Self-correction:")
    try:
        from correction import SelfCorrectionLoop, CorrectionResult
        print("   - correction.self_correction: OK")
        modules.append("correction")
    except Exception as e:
        print(f"   - correction: FAILED - {e}")

    # SWE-bench orchestrator
    print("\n6. SWE-bench orchestrator:")
    try:
        from swebench_orchestrator import SWEBenchOrchestrator, SWEBenchTask
        print("   - swebench_orchestrator: OK")
        modules.append("swebench_orchestrator")
    except Exception as e:
        print(f"   - swebench_orchestrator: FAILED - {e}")

    # Summary
    print("\n" + "="*50)
    print(f"SUMMARY: {len(modules)}/10 modules loaded successfully")
    print("="*50)

    if len(modules) == 10:
        print("\nAll modules OK! Opus Ensemble is ready.")
        return True
    else:
        print("\nSome modules failed to load. Check errors above.")
        return False


def test_localization_quick():
    """Quick test of localization on current directory."""
    print("\n" + "="*50)
    print("Quick Localization Test")
    print("="*50)

    try:
        from localization import LocalizationConsensus

        # Test on Opus_Ensemble directory
        repo_path = str(Path(__file__).parent.parent)
        consensus = LocalizationConsensus(repo_path=repo_path)

        print(f"\nIndexing {repo_path}...")
        counts = consensus.index()
        print(f"Indexed: AST={counts.get('ast', 0)}, BM25={counts.get('bm25', 0)}, KG={counts.get('kg', 0)}")

        # Test search
        query = "parallel generation strategy"
        print(f"\nSearching for: '{query}'")
        results = consensus.localize(query, top_k=3)

        print("\nTop results:")
        for r in results:
            print(f"  {r.file_path}: score={r.score:.2f}, confidence={r.confidence:.0%}")

    except Exception as e:
        print(f"Localization test failed: {e}")


def test_docker_executor():
    """Test Docker executor (image name generation)."""
    print("\n" + "="*50)
    print("Docker Executor Test")
    print("="*50)

    try:
        from docker_executor import get_swebench_image

        test_instances = [
            "django__django-12345",
            "requests__requests-5678",
            "sympy__sympy-9999",
        ]

        print("\nSWE-bench image name mapping:")
        for instance_id in test_instances:
            image = get_swebench_image(instance_id)
            print(f"  {instance_id} -> {image}")

    except Exception as e:
        print(f"Docker executor test failed: {e}")


if __name__ == "__main__":
    success = test_imports()

    if success:
        test_localization_quick()
        test_docker_executor()
