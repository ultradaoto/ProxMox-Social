"""
Social Worker Health Check

Verifies all components are working correctly:
- Dashboard API connectivity
- Queue directories
- Browser automation
- Platform session status

Usage:
    python healthcheck.py           # Full health check
    python healthcheck.py --quick   # Quick connectivity check
"""

import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

# Configuration
DASHBOARD_URL = os.getenv('DASHBOARD_URL', 'https://sterlingcooley.com')
API_KEY = os.getenv('API_KEY', '')
QUEUE_DIR = Path(os.getenv('QUEUE_DIR', 'C:/PostQueue'))


class HealthChecker:
    """Performs health checks on the Social Worker system."""

    def __init__(self):
        self.results = {}
        self.overall_healthy = True

    def check(self, name: str, passed: bool, message: str = ""):
        """Record a health check result."""
        status = "PASS" if passed else "FAIL"
        self.results[name] = {
            'status': status,
            'message': message,
            'passed': passed
        }
        if not passed:
            self.overall_healthy = False

        # Color output
        color = '\033[92m' if passed else '\033[91m'
        reset = '\033[0m'
        print(f"  [{color}{status}{reset}] {name}")
        if message:
            print(f"         {message}")

    def check_environment(self):
        """Check environment configuration."""
        print("\n=== Environment ===")

        # API Key
        self.check(
            "API Key Set",
            bool(API_KEY),
            f"Length: {len(API_KEY)}" if API_KEY else "Set API_KEY in .env"
        )

        # Dashboard URL
        self.check(
            "Dashboard URL",
            bool(DASHBOARD_URL) and DASHBOARD_URL.startswith('http'),
            DASHBOARD_URL
        )

        # Queue directory
        self.check(
            "Queue Directory",
            QUEUE_DIR.exists(),
            str(QUEUE_DIR)
        )

    def check_directories(self):
        """Check queue directories exist and are writable."""
        print("\n=== Directories ===")

        dirs = ['pending', 'in_progress', 'completed', 'failed']
        for d in dirs:
            path = QUEUE_DIR / d
            exists = path.exists()
            writable = False

            if exists:
                try:
                    test_file = path / '.write_test'
                    test_file.touch()
                    test_file.unlink()
                    writable = True
                except:
                    pass

            self.check(
                f"Queue/{d}",
                exists and writable,
                "Exists and writable" if (exists and writable) else "Missing or not writable"
            )

    def check_api(self):
        """Check Dashboard API connectivity."""
        print("\n=== Dashboard API ===")

        if not API_KEY:
            self.check("API Connection", False, "No API key configured")
            return

        try:
            response = requests.get(
                f"{DASHBOARD_URL}/api/queue/pending",
                headers={'X-API-Key': API_KEY},
                timeout=10
            )

            if response.status_code == 200:
                self.check(
                    "API Connection",
                    True,
                    f"Response time: {response.elapsed.total_seconds()*1000:.0f}ms"
                )

                # Check response format
                try:
                    data = response.json()
                    self.check(
                        "API Response Format",
                        isinstance(data, list),
                        f"Got {len(data)} pending posts"
                    )
                except:
                    self.check("API Response Format", False, "Invalid JSON response")

            elif response.status_code == 401:
                self.check("API Connection", False, "Invalid API key (401)")
            elif response.status_code == 404:
                self.check("API Connection", False, "Endpoint not found (404) - is API implemented?")
            else:
                self.check("API Connection", False, f"HTTP {response.status_code}")

        except requests.exceptions.ConnectionError:
            self.check("API Connection", False, f"Cannot connect to {DASHBOARD_URL}")
        except requests.exceptions.Timeout:
            self.check("API Connection", False, "Request timed out")
        except Exception as e:
            self.check("API Connection", False, str(e))

    def check_python_deps(self):
        """Check Python dependencies are installed."""
        print("\n=== Python Dependencies ===")

        deps = [
            ('requests', 'HTTP client'),
            ('schedule', 'Task scheduler'),
            ('dotenv', 'Environment loader'),
            ('playwright', 'Browser automation'),
            ('PIL', 'Image processing'),
        ]

        for module, description in deps:
            try:
                if module == 'PIL':
                    import PIL
                elif module == 'dotenv':
                    import dotenv
                else:
                    __import__(module)
                self.check(module, True, description)
            except ImportError:
                self.check(module, False, f"pip install {module}")

    async def check_browser(self):
        """Check browser automation is working."""
        print("\n=== Browser Automation ===")

        try:
            from playwright.async_api import async_playwright

            playwright = await async_playwright().start()

            try:
                browser = await playwright.chromium.launch(headless=True)
                self.check("Chromium Launch", True, "Browser started successfully")

                page = await browser.new_page()
                await page.goto('https://www.google.com', timeout=30000)
                self.check("Navigation", True, "Page loaded")

                await browser.close()

            except Exception as e:
                self.check("Browser Test", False, str(e))

            await playwright.stop()

        except ImportError:
            self.check("Playwright", False, "Run: pip install playwright && playwright install chromium")
        except Exception as e:
            self.check("Browser", False, str(e))

    def check_queue_status(self):
        """Show current queue status."""
        print("\n=== Queue Status ===")

        for status in ['pending', 'in_progress', 'completed', 'failed']:
            path = QUEUE_DIR / status
            if path.exists():
                count = len([d for d in path.iterdir() if d.is_dir()])
                print(f"  {status.capitalize():12}: {count} jobs")

    def run_quick(self):
        """Quick connectivity check."""
        print("=" * 50)
        print("  SOCIAL WORKER QUICK HEALTH CHECK")
        print("=" * 50)

        self.check_environment()
        self.check_api()
        self.check_queue_status()

        return self.summary()

    async def run_full(self):
        """Full health check including browser."""
        print("=" * 50)
        print("  SOCIAL WORKER FULL HEALTH CHECK")
        print("=" * 50)
        print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)

        self.check_environment()
        self.check_directories()
        self.check_python_deps()
        self.check_api()
        await self.check_browser()
        self.check_queue_status()

        return self.summary()

    def summary(self):
        """Print summary and return exit code."""
        print("\n" + "=" * 50)

        passed = sum(1 for r in self.results.values() if r['passed'])
        total = len(self.results)

        if self.overall_healthy:
            print(f"  \033[92mALL CHECKS PASSED ({passed}/{total})\033[0m")
        else:
            failed = total - passed
            print(f"  \033[91m{failed} CHECK(S) FAILED ({passed}/{total} passed)\033[0m")

        print("=" * 50)

        return 0 if self.overall_healthy else 1


def main():
    parser = argparse.ArgumentParser(description='Social Worker Health Check')
    parser.add_argument('--quick', action='store_true', help='Quick connectivity check only')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    checker = HealthChecker()

    if args.quick:
        exit_code = checker.run_quick()
    else:
        exit_code = asyncio.run(checker.run_full())

    if args.json:
        print(json.dumps(checker.results, indent=2))

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
