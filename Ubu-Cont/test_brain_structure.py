#!/usr/bin/env python3
"""
Test script to verify the Ubuntu Brain Agent structure.

This script checks that all modules can be imported and have the expected classes.
Run with: python test_brain_structure.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """Test that all modules can be imported."""
    print("=" * 60)
    print("UBUNTU BRAIN AGENT - STRUCTURE TEST")
    print("=" * 60)
    print()
    
    errors = []
    
    # Test main modules
    modules = [
        ("src.fetcher", ["Fetcher", "PendingPost", "Platform"]),
        ("src.reporter", ["Reporter", "PostStatus"]),
        ("src.orchestrator", ["BrainOrchestrator"]),
    ]
    
    # Test subsystems
    modules += [
        ("src.subsystems.vnc_capture", ["VNCCapture"]),
        ("src.subsystems.vision_engine", ["VisionEngine", "FoundElement", "ScreenState"]),
        ("src.subsystems.input_injector", ["InputInjector", "MouseButton"]),
    ]
    
    # Test subroutines
    modules += [
        ("src.subroutines.windows_login", ["WindowsLoginSubroutine"]),
        ("src.subroutines.browser_focus", ["BrowserFocusSubroutine"]),
        ("src.subroutines.error_recovery", ["ErrorRecoverySubroutine"]),
    ]
    
    # Test workflows
    modules += [
        ("src.workflows.async_base_workflow", ["AsyncBaseWorkflow", "StepResult", "StepStatus", "WorkflowResult"]),
        ("src.workflows.skool_workflow", ["SkoolWorkflow"]),
    ]
    
    # Test utils
    modules += [
        ("src.utils.logger", ["setup_logging", "get_logger"]),
        ("src.utils.screenshot_saver", ["ScreenshotSaver", "save_screenshot"]),
        ("src.utils.retry_handler", ["retry_async", "RetryContext", "RetryError"]),
    ]
    
    for module_name, expected_classes in modules:
        try:
            print(f"[1/2] Importing {module_name}...", end=" ")
            module = __import__(module_name, fromlist=expected_classes)
            
            missing = []
            for cls_name in expected_classes:
                if not hasattr(module, cls_name):
                    missing.append(cls_name)
            
            if missing:
                print(f"PARTIAL - Missing: {missing}")
                errors.append(f"{module_name}: Missing {missing}")
            else:
                print("OK")
                
        except Exception as e:
            print(f"FAILED - {type(e).__name__}: {e}")
            errors.append(f"{module_name}: {e}")
    
    print()
    
    # Test Skool workflow steps
    print("Testing Skool workflow steps...")
    try:
        from src.workflows.skool_workflow import SkoolWorkflow
        from src.subsystems.vnc_capture import VNCCapture
        from src.subsystems.vision_engine import VisionEngine
        from src.subsystems.input_injector import InputInjector
        
        # Create mock instances (won't actually connect)
        workflow = SkoolWorkflow.__new__(SkoolWorkflow)
        workflow.vnc = None
        workflow.vision = None
        workflow.input = None
        
        steps = workflow.steps
        print(f"Skool workflow has {len(steps)} steps:")
        for i, step in enumerate(steps, 1):
            print(f"  {i:2}. {step}")
        
        if len(steps) == 16:
            print("OK - All 16 steps present")
        else:
            print(f"WARNING - Expected 16 steps, found {len(steps)}")
            errors.append(f"Skool workflow: Expected 16 steps, found {len(steps)}")
            
    except Exception as e:
        print(f"FAILED - {e}")
        errors.append(f"Skool workflow test: {e}")
    
    print()
    print("=" * 60)
    
    if errors:
        print(f"COMPLETED WITH {len(errors)} ERROR(S):")
        for err in errors:
            print(f"  - {err}")
        return 1
    else:
        print("ALL TESTS PASSED")
        print()
        print("Ubuntu Brain Agent structure is valid!")
        print("Deploy to Ubuntu VM and run: python main.py")
        return 0


if __name__ == "__main__":
    sys.exit(test_imports())
