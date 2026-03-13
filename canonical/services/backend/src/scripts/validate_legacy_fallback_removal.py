#!/usr/bin/env python3
"""
Validation Script for Legacy Fallback Removal

This script performs static analysis to verify that:
1. The legacy fallback method has been removed
2. All workflow modules have execute() functions
3. The contract enforcement is properly implemented
4. Documentation has been updated

This can be run without dependencies as a pre-commit validation.
"""

import ast
import sys
from pathlib import Path

# Define repository root
REPO_ROOT = Path(__file__).parent.parent.parent
BACKEND_ROOT = REPO_ROOT / "backend"


def check_legacy_code_removed():
    """Verify that legacy fallback code has been removed."""
    print("=" * 70)
    print("CHECKING: Legacy fallback code removal")
    print("=" * 70)
    
    workflow_executor_path = BACKEND_ROOT / "app" / "orchestrator" / "core" / "workflow_executor.py"
    
    if not workflow_executor_path.exists():
        print(f"❌ FAIL: workflow_executor.py not found at {workflow_executor_path}")
        return False
    
    with open(workflow_executor_path, 'r') as f:
        content = f.read()
        tree = ast.parse(content)
    
    # Check for removed method
    has_legacy_method = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name == '_execute_langgraph_custom_graph':
                has_legacy_method = True
                break
    
    if has_legacy_method:
        print("❌ FAIL: _execute_langgraph_custom_graph method still exists!")
        return False
    else:
        print("✅ PASS: _execute_langgraph_custom_graph method removed")
    
    # Check for removed import
    has_legacy_import = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == 'app.workflow_executor':
                for alias in node.names:
                    if alias.name == 'load_custom_graph':
                        has_legacy_import = True
                        break
    
    if has_legacy_import:
        print("❌ FAIL: load_custom_graph still imported!")
        return False
    else:
        print("✅ PASS: load_custom_graph import removed")
    
    # Check for error message enforcement
    if "does not implement required execute(pipeline_item)" in content:
        print("✅ PASS: Explicit error message for missing execute() found")
    else:
        print("❌ FAIL: Explicit error message not found!")
        return False
    
    # Check for contract reference in error
    if "INGESTION_EXECUTION_CONTRACT.md" in content:
        print("✅ PASS: Contract documentation reference in error message")
    else:
        print("❌ FAIL: Contract documentation reference not found!")
        return False
    
    print()
    return True


def check_workflow_compliance():
    """Verify that all workflow entry points have execute() functions."""
    print("=" * 70)
    print("CHECKING: Workflow modules compliance")
    print("=" * 70)
    
    workflows_dir = BACKEND_ROOT / "app" / "workflows"
    
    # List of main workflow entry points that should have execute()
    expected_workflows = [
        workflows_dir / "ingestion" / "ingestion_orchestrator.py",
        workflows_dir / "ingestion_graph.py",
        workflows_dir / "generate_doc_embeddings_and_store.py",
        workflows_dir / "generate_code_embeddings_and_store.py",
        workflows_dir / "preprocess_and_chunk" / "pipeline.py",
        workflows_dir / "generate_embeddings_and_store" / "embeddings_pipeline.py"
    ]
    
    all_compliant = True
    
    for workflow_path in expected_workflows:
        if not workflow_path.exists():
            print(f"⚠️  SKIP: {workflow_path.relative_to(BACKEND_ROOT)} (not found)")
            continue
        
        with open(workflow_path, 'r') as f:
            content = f.read()
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                print(f"❌ FAIL: {workflow_path.relative_to(BACKEND_ROOT)} (syntax error: {e})")
                all_compliant = False
                continue
        
        has_execute = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name == 'execute':
                    # Check signature - should accept 'item' or similar
                    has_execute = True
                    break
            # Also check for imports of execute function
            elif isinstance(node, ast.ImportFrom):
                if node.names:
                    for alias in node.names:
                        if alias.name == 'execute':
                            has_execute = True
                            break
        
        if has_execute:
            print(f"✅ PASS: {workflow_path.relative_to(BACKEND_ROOT)}")
        else:
            print(f"❌ FAIL: {workflow_path.relative_to(BACKEND_ROOT)} (missing execute() function)")
            all_compliant = False
    
    print()
    return all_compliant


def check_documentation_updated():
    """Verify that documentation has been updated."""
    print("=" * 70)
    print("CHECKING: Documentation updates")
    print("=" * 70)
    
    contract_path = REPO_ROOT / "docs" / "official" / "backend" / "INGESTION_EXECUTION_CONTRACT.md"
    
    if not contract_path.exists():
        print(f"❌ FAIL: Contract document not found at {contract_path}")
        return False
    
    with open(contract_path, 'r') as f:
        content = f.read()
    
    # Check version update
    if "3.0.0" in content or "v3.0" in content:
        print("✅ PASS: Document version updated to 3.0")
    else:
        print("❌ FAIL: Document version not updated")
        return False
    
    # Check for mandatory contract section
    if "Mandatory Execution Contract" in content or "mandatory" in content.lower():
        print("✅ PASS: Mandatory contract section present")
    else:
        print("❌ FAIL: Mandatory contract section not found")
        return False
    
    # Check that fallback/backward compatibility is removed or noted as removed
    if "No Legacy Fallback" in content or "REMOVED" in content:
        print("✅ PASS: Legacy fallback removal documented")
    else:
        print("⚠️  WARNING: Legacy fallback removal not clearly documented")
    
    # Check for execute(pipeline_item) requirement
    if "execute(pipeline_item)" in content or "execute(item: PipelineItem)" in content:
        print("✅ PASS: execute(pipeline_item) requirement documented")
    else:
        print("❌ FAIL: execute(pipeline_item) requirement not documented")
        return False
    
    print()
    return True


def check_test_coverage():
    """Verify that tests exist for contract enforcement."""
    print("=" * 70)
    print("CHECKING: Test coverage")
    print("=" * 70)
    
    test_path = BACKEND_ROOT / "tests" / "unit" / "backend" / "orchestrator" / "test_workflow_executor_contract_enforcement.py"
    
    if not test_path.exists():
        print(f"❌ FAIL: Contract enforcement test not found at {test_path}")
        return False
    
    with open(test_path, 'r') as f:
        content = f.read()
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            print(f"❌ FAIL: Test file has syntax errors: {e}")
            return False
    
    # Count test functions
    test_count = 0
    test_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name.startswith('test_'):
                test_count += 1
                test_names.append(node.name)
    
    if test_count == 0:
        print("❌ FAIL: No test functions found")
        return False
    
    print(f"✅ PASS: Found {test_count} test functions")
    
    # Check for specific critical tests
    critical_tests = [
        'test_workflow_missing_execute_function_fails',
        'test_compliant_workflow_executes_successfully',
        'test_no_execute_langgraph_custom_graph_method'
    ]
    
    for critical_test in critical_tests:
        if any(critical_test in name for name in test_names):
            print(f"  ✅ {critical_test}")
        else:
            print(f"  ⚠️  {critical_test} (not found, but may have different name)")
    
    print()
    return True


def main():
    """Run all validation checks."""
    print("\n" + "=" * 70)
    print("LEGACY FALLBACK REMOVAL VALIDATION")
    print("=" * 70)
    print()
    
    checks = [
        ("Legacy Code Removal", check_legacy_code_removed),
        ("Workflow Compliance", check_workflow_compliance),
        ("Documentation Updates", check_documentation_updated),
        ("Test Coverage", check_test_coverage)
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ ERROR in {name}: {e}")
            results.append((name, False))
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print()
    print(f"Total: {passed}/{total} checks passed")
    print("=" * 70)
    
    if passed == total:
        print("\n🎉 All validation checks passed!")
        return 0
    else:
        print("\n⚠️  Some validation checks failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
