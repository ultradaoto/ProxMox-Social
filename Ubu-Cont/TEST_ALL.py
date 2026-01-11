"""
Comprehensive Test Suite for Ubuntu Controller

Runs all module tests in sequence and generates a report.
"""
import subprocess
import sys
from pathlib import Path

def run_test(name, command, timeout=45):
    """Run a single test and capture results."""
    print(f"\n{'='*70}")
    print(f"Testing: {name}")
    print(f"{'='*70}\n")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired as e:
        print(f"[TIMEOUT] Test exceeded {timeout} seconds")
        if e.stdout:
            print("STDOUT:", e.stdout.decode() if isinstance(e.stdout, bytes) else e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr)
        return False
    except Exception as e:
        print(f"[ERROR] Test failed with exception: {e}")
        return False


def main():
    """Run all tests."""
    print("="*70)
    print("UBUNTU CONTROLLER - COMPREHENSIVE TEST SUITE")
    print("="*70)
    print("Testing all modules before deployment to Ubuntu VM")
    print("")
    
    # Define tests
    python_cmd = sys.executable
    tests = [
        ("VNC Capture Module", f"{python_cmd} src/vnc_capture.py"),
        ("Vision Finder Module", f"{python_cmd} src/vision_finder.py"),
        ("Input Injector Module", f"{python_cmd} src/input_injector.py"),
        ("Base Workflow Import", f'{python_cmd} -c "from src.workflows.base_workflow import BaseWorkflow; print(\'[OK] Import successful\')"'),
        ("Instagram Workflow", f"{python_cmd} src/workflows/instagram.py"),
        ("Main Orchestrator", f"{python_cmd} src/main_orchestrator.py --test"),
    ]
    
    results = {}
    
    # Run all tests
    for name, command in tests:
        passed = run_test(name, command)
        results[name] = "PASS" if passed else "FAIL"
    
    # Print summary
    print("\n")
    print("="*70)
    print("TEST SUMMARY")
    print("="*70)
    print("")
    
    passed = sum(1 for r in results.values() if r == "PASS")
    total = len(results)
    
    for name, result in results.items():
        status = "[OK]" if result == "PASS" else "[FAIL]"
        print(f"{status:8} {name}")
    
    print("")
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("")
        print("="*70)
        print("[SUCCESS] All tests passed - ready for deployment!")
        print("="*70)
        return 0
    else:
        print("")
        print("="*70)
        print("[FAIL] Some tests failed - review errors above")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
