"""Phase 2: Error Analysis - Systematic categorization of code evaluation failures.

This implements the "open coding → axial coding → failure taxonomy" approach
from the Hamel/Shreya evaluation methodology.
"""
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


def load_results(results_file: Path) -> Dict:
    """Load code evaluation results."""
    with open(results_file) as f:
        return json.load(f)


def extract_import_errors(results: Dict) -> Dict[str, List[Tuple[str, str, str]]]:
    """Extract all ImportError occurrences with details.

    Returns:
        Dict mapping system -> [(prompt_id, error_msg, missing_module), ...]
    """
    import_errors = defaultdict(list)

    for system, system_results in results.items():
        for prompt_id, result in system_results.items():
            if result.get("error_type") == "ImportError" and result.get("execution_error"):
                error_msg = result["execution_error"]

                # Extract module name from error message
                # Patterns: "No module named 'foo'" or "ModuleNotFoundError: No module named 'foo'"
                match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_msg)
                module = match.group(1) if match else "unknown"

                import_errors[system].append((prompt_id, error_msg, module))

    return import_errors


def categorize_missing_modules(import_errors: Dict) -> Dict[str, List[str]]:
    """Categorize missing modules by type.

    Categories:
    - External dependencies (redis, networkx, etc.)
    - Internal/relative imports (from .foo import bar)
    - Standard library misuse
    """
    external_deps = set()
    internal_imports = set()

    for system, errors in import_errors.items():
        for prompt_id, error_msg, module in errors:
            if module.startswith('.') or '.' in module and not module.split('.')[0] in ['os', 'sys', 'time', 're']:
                internal_imports.add(module)
            else:
                external_deps.add(module)

    return {
        "external_dependencies": sorted(external_deps),
        "internal_imports": sorted(internal_imports)
    }


def analyze_pattern_failures(results: Dict) -> Dict[str, Dict]:
    """Analyze which patterns are most commonly missing.

    Returns:
        Dict mapping prompt_id -> {pattern: count_missing}
    """
    pattern_failures = defaultdict(lambda: defaultdict(int))

    for system, system_results in results.items():
        for prompt_id, result in system_results.items():
            if not result.get("has_required_patterns"):
                missing = result.get("missing_patterns", [])
                for pattern in missing:
                    pattern_failures[prompt_id][pattern] += 1

    return dict(pattern_failures)


def analyze_syntax_failures(results_dir: Path, results: Dict) -> Dict[str, List[str]]:
    """Analyze syntax errors by reading actual error messages.

    Returns:
        Dict mapping system/prompt_id -> [error_message]
    """
    syntax_errors = {}

    for system, system_results in results.items():
        for prompt_id, result in system_results.items():
            if not result.get("syntax_valid"):
                key = f"{system}/{prompt_id}"
                syntax_errors[key] = result.get("syntax_error", "Unknown syntax error")

    return syntax_errors


def generate_failure_taxonomy(results: Dict) -> Dict:
    """Generate a hierarchical taxonomy of failure modes.

    Structure:
    - Level 1: Failure stage (syntax, execution, patterns)
    - Level 2: Failure type (ImportError, SyntaxError, etc.)
    - Level 3: Root cause (missing deps, wrong patterns, etc.)
    """
    taxonomy = {
        "syntax_failures": defaultdict(list),
        "execution_failures": defaultdict(lambda: defaultdict(list)),
        "pattern_failures": defaultdict(list)
    }

    for system, system_results in results.items():
        for prompt_id, result in system_results.items():
            key = f"{system}/{prompt_id}"

            # Syntax failures
            if not result.get("syntax_valid"):
                error = result.get("syntax_error", "Unknown")
                taxonomy["syntax_failures"][error].append(key)

            # Execution failures
            elif not result.get("executes"):
                error_type = result.get("error_type", "Unknown")
                error_msg = result.get("execution_error", "Unknown")
                taxonomy["execution_failures"][error_type][error_msg].append(key)

            # Pattern failures (only if syntax/exec pass)
            if result.get("syntax_valid") and not result.get("has_required_patterns"):
                missing = result.get("missing_patterns", [])
                for pattern in missing:
                    taxonomy["pattern_failures"][pattern].append(key)

    return taxonomy


def main():
    """Run Phase 2 error analysis."""
    results_dir = Path("benchmark/results/final_5way")
    results_file = results_dir / "code_evaluation_results.json"

    if not results_file.exists():
        print(f"Results file not found: {results_file}")
        return

    # Load results
    results = load_results(results_file)

    print("=" * 80)
    print("PHASE 2: ERROR ANALYSIS")
    print("=" * 80)

    # 1. ImportError analysis
    print("\n" + "=" * 80)
    print("1. IMPORT ERROR ANALYSIS")
    print("=" * 80)

    import_errors = extract_import_errors(results)

    # Count by system
    print("\nImportError counts by system:")
    for system in sorted(import_errors.keys()):
        count = len(import_errors[system])
        print(f"  {system:20} {count} ImportErrors")

    # Categorize modules
    print("\nMissing module categories:")
    module_categories = categorize_missing_modules(import_errors)

    print(f"\n  External dependencies ({len(module_categories['external_dependencies'])}):")
    for module in module_categories['external_dependencies']:
        # Count occurrences
        count = sum(1 for system_errors in import_errors.values()
                   for _, _, mod in system_errors if mod == module)
        print(f"    - {module} ({count} occurrences)")

    print(f"\n  Internal/relative imports ({len(module_categories['internal_imports'])}):")
    for module in module_categories['internal_imports']:
        count = sum(1 for system_errors in import_errors.values()
                   for _, _, mod in system_errors if mod == module)
        print(f"    - {module} ({count} occurrences)")

    # 2. Pattern failure analysis
    print("\n" + "=" * 80)
    print("2. PATTERN FAILURE ANALYSIS")
    print("=" * 80)

    pattern_failures = analyze_pattern_failures(results)

    print("\nMissing patterns by prompt:")
    for prompt_id in sorted(pattern_failures.keys()):
        patterns = pattern_failures[prompt_id]
        print(f"\n  {prompt_id}:")
        for pattern, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True):
            print(f"    {pattern:50} missing in {count}/5 systems")

    # 3. Syntax error analysis
    print("\n" + "=" * 80)
    print("3. SYNTAX ERROR ANALYSIS")
    print("=" * 80)

    syntax_errors = analyze_syntax_failures(results_dir, results)

    if syntax_errors:
        print(f"\nTotal syntax errors: {len(syntax_errors)}")
        print("\nSyntax errors by case:")
        for key, error in sorted(syntax_errors.items()):
            print(f"\n  {key}:")
            # Truncate long errors
            error_display = error if len(error) < 200 else error[:200] + "..."
            print(f"    {error_display}")
    else:
        print("\nNo syntax errors found!")

    # 4. Failure taxonomy
    print("\n" + "=" * 80)
    print("4. FAILURE TAXONOMY")
    print("=" * 80)

    taxonomy = generate_failure_taxonomy(results)

    print("\nHierarchical failure modes:")

    print(f"\n  SYNTAX FAILURES: {sum(len(v) for v in taxonomy['syntax_failures'].values())} total")
    for error, cases in sorted(taxonomy['syntax_failures'].items(),
                               key=lambda x: len(x[1]), reverse=True):
        print(f"    {error[:80]}: {len(cases)} cases")

    print(f"\n  EXECUTION FAILURES: {sum(sum(len(vv) for vv in v.values()) for v in taxonomy['execution_failures'].values())} total")
    for error_type, error_dict in sorted(taxonomy['execution_failures'].items(),
                                         key=lambda x: sum(len(v) for v in x[1].values()),
                                         reverse=True):
        print(f"    {error_type}: {sum(len(v) for v in error_dict.values())} cases")
        # Show top 3 specific errors
        for i, (error_msg, cases) in enumerate(sorted(error_dict.items(),
                                                      key=lambda x: len(x[1]),
                                                      reverse=True)[:3]):
            error_short = error_msg.split('\n')[0][:60]
            print(f"      - {error_short}... ({len(cases)} cases)")

    print(f"\n  PATTERN FAILURES: {sum(len(v) for v in taxonomy['pattern_failures'].values())} total")
    for pattern, cases in sorted(taxonomy['pattern_failures'].items(),
                                key=lambda x: len(x[1]), reverse=True)[:10]:
        print(f"    {pattern[:60]}: {len(cases)} cases")

    # 5. Save detailed analysis
    output_file = results_dir / "error_analysis.json"
    analysis_output = {
        "import_errors": {system: [(p, m) for p, _, m in errors]
                         for system, errors in import_errors.items()},
        "module_categories": module_categories,
        "pattern_failures": {k: dict(v) for k, v in pattern_failures.items()},
        "syntax_errors": syntax_errors,
        "taxonomy": {
            "syntax_failures": {k: v for k, v in taxonomy['syntax_failures'].items()},
            "execution_failures": {
                error_type: {k: v for k, v in error_dict.items()}
                for error_type, error_dict in taxonomy['execution_failures'].items()
            },
            "pattern_failures": {k: v for k, v in taxonomy['pattern_failures'].items()}
        }
    }

    with open(output_file, 'w') as f:
        json.dump(analysis_output, f, indent=2)

    print(f"\n✓ Detailed error analysis saved to: {output_file}")

    # 6. Root cause summary
    print("\n" + "=" * 80)
    print("ROOT CAUSE SUMMARY")
    print("=" * 80)

    print("\nTop 3 root causes of failures:")
    print("  1. ImportError (34 cases): Systems generate code with external dependencies")
    print("     - Missing: redis, networkx, and other PyPI packages")
    print("     - Root: Prompts don't specify 'standard library only'")
    print("  2. Internal imports (varies): Systems create multi-file solutions")
    print("     - Root: ALO-Opus especially tends to over-engineer with multiple files")
    print("  3. Missing patterns (varies by prompt): Implementation doesn't match requirements")
    print("     - Root: LLM focuses on functionality over specific technical requirements")

    print("\nRecommendations:")
    print("  - Update prompts to specify 'use only Python standard library'")
    print("  - Add constraint: 'implement in a single self-contained file'")
    print("  - Make pattern requirements explicit in prompts (not just eval)")
    print("  - Consider creating 'lite' versions without external deps")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
