"""
Test script for Simplified OSP
Verifies dependencies and basic functionality
"""

import sys
import os
from pathlib import Path

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    RESET = '\033[0m'

def print_header(text):
    print(f"\n{Colors.CYAN}{'='*50}{Colors.RESET}")
    print(f"{Colors.CYAN}{text:^50}{Colors.RESET}")
    print(f"{Colors.CYAN}{'='*50}{Colors.RESET}\n")

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")

def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")

def test_dependencies():
    """Test if all required dependencies are installed."""
    print_header("Testing Dependencies")
    
    all_good = True
    
    # Test tkinter (built-in)
    try:
        import tkinter
        print_success("tkinter is available")
    except ImportError as e:
        print_error(f"tkinter not available: {e}")
        all_good = False
    
    # Test pyperclip
    try:
        import pyperclip
        print_success("pyperclip is installed")
        
        # Test clipboard operations
        test_text = "OSP Test"
        pyperclip.copy(test_text)
        result = pyperclip.paste()
        if result == test_text:
            print_success("Clipboard operations work")
        else:
            print_error(f"Clipboard test failed: expected '{test_text}', got '{result}'")
            all_good = False
    except ImportError as e:
        print_error(f"pyperclip not installed: {e}")
        all_good = False
    except Exception as e:
        print_error(f"Clipboard test failed: {e}")
        all_good = False
    
    # Test requests
    try:
        import requests
        print_success("requests is installed")
    except ImportError as e:
        print_error(f"requests not installed: {e}")
        all_good = False
    
    # Test Pillow
    try:
        from PIL import Image
        print_success("Pillow (PIL) is installed")
    except ImportError as e:
        print_error(f"Pillow not installed: {e}")
        all_good = False
    
    return all_good

def test_file_structure():
    """Test if required files and directories exist."""
    print_header("Testing File Structure")
    
    all_good = True
    
    # Check osp_simple.py
    if os.path.exists("osp_simple.py"):
        print_success("osp_simple.py exists")
    else:
        print_error("osp_simple.py not found")
        all_good = False
    
    # Check requirements file
    if os.path.exists("requirements_osp_simple.txt"):
        print_success("requirements_osp_simple.txt exists")
    else:
        print_warning("requirements_osp_simple.txt not found (optional)")
    
    # Check/Create PostQueue directory
    postqueue_dir = Path("C:/PostQueue")
    if postqueue_dir.exists():
        print_success("C:/PostQueue directory exists")
    else:
        print_warning("C:/PostQueue directory not found - creating it")
        try:
            postqueue_dir.mkdir(parents=True, exist_ok=True)
            print_success("Created C:/PostQueue directory")
        except Exception as e:
            print_error(f"Failed to create C:/PostQueue: {e}")
            all_good = False
    
    return all_good

def test_api_connection():
    """Test connection to the Social Dashboard API."""
    print_header("Testing API Connection")
    
    try:
        import requests
        
        api_url = "https://social.sterlingcooley.com/api/gui_post_queue/pending"
        print(f"Testing connection to: {api_url}")
        
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            print_success(f"API connection successful (status: {response.status_code})")
            
            try:
                data = response.json()
                if isinstance(data, list):
                    print_success(f"API returned valid data (list with {len(data)} items)")
                    return True
                else:
                    print_warning(f"API returned unexpected data type: {type(data)}")
                    return True  # Still considered success if we got a response
            except Exception as e:
                print_warning(f"Could not parse JSON response: {e}")
                return True  # Connection worked, parsing is secondary
        else:
            print_error(f"API returned status code: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print_error("API connection timed out")
        return False
    except requests.exceptions.ConnectionError:
        print_error("Could not connect to API (connection error)")
        return False
    except Exception as e:
        print_error(f"API test failed: {e}")
        return False

def test_image_clipboard():
    """Test if PowerShell image clipboard operations work."""
    print_header("Testing Image Clipboard")
    
    try:
        import subprocess
        
        # Create a simple test image
        from PIL import Image
        import tempfile
        
        # Create a small test image
        img = Image.new('RGB', (100, 100), color='red')
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp_path = tmp.name
            img.save(tmp_path)
        
        print(f"Created test image at: {tmp_path}")
        
        # Try to copy to clipboard using PowerShell
        ps_script = f'''
        Add-Type -AssemblyName System.Windows.Forms
        $image = [System.Drawing.Image]::FromFile("{tmp_path}")
        [System.Windows.Forms.Clipboard]::SetImage($image)
        '''
        
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            timeout=10
        )
        
        # Clean up
        os.unlink(tmp_path)
        
        if result.returncode == 0:
            print_success("PowerShell image clipboard operations work")
            return True
        else:
            print_error(f"PowerShell command failed: {result.stderr.decode()}")
            return False
            
    except Exception as e:
        print_error(f"Image clipboard test failed: {e}")
        return False

def main():
    """Run all tests."""
    print_header("OSP Simplified Test Suite")
    
    results = {
        "Dependencies": test_dependencies(),
        "File Structure": test_file_structure(),
        "API Connection": test_api_connection(),
        "Image Clipboard": test_image_clipboard()
    }
    
    print_header("Test Results Summary")
    
    all_passed = True
    for test_name, passed in results.items():
        if passed:
            print_success(f"{test_name}: PASSED")
        else:
            print_error(f"{test_name}: FAILED")
            all_passed = False
    
    print()
    if all_passed:
        print_success("All tests passed! OSP is ready to use.")
        print(f"\n{Colors.CYAN}To start the OSP, run:{Colors.RESET}")
        print(f"{Colors.YELLOW}  python osp_simple.py{Colors.RESET}\n")
        return 0
    else:
        print_error("Some tests failed. Please fix the issues above.")
        print(f"\n{Colors.CYAN}To install dependencies, run:{Colors.RESET}")
        print(f"{Colors.YELLOW}  pip install -r requirements_osp_simple.txt{Colors.RESET}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
