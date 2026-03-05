#!/usr/bin/env python3
"""
WordPress Hosting Viability Test Script

Upload this script to your WordPress host and run:
    python3 test_hosting.py

For full dependency testing:
    python3 test_hosting.py --full
"""

import sys
import os
import subprocess

def print_header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_result(test_name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {test_name}")
    if details:
        print(f"       {details}")

def check_python_version():
    print_header("Python Version Check")
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    passed = version.major == 3 and version.minor >= 9
    print_result(
        "Python 3.9+",
        passed,
        f"Found: Python {version_str}"
    )
    print(f"       Executable: {sys.executable}")
    return passed

def check_pip():
    print_header("pip Availability Check")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            text=True
        )
        passed = result.returncode == 0
        print_result("pip available", passed, result.stdout.strip() if passed else result.stderr.strip())
        return passed
    except Exception as e:
        print_result("pip available", False, str(e))
        return False

def check_package_import(package_name, import_name=None):
    if import_name is None:
        import_name = package_name
    try:
        __import__(import_name)
        print_result(f"Import {package_name}", True)
        return True
    except ImportError as e:
        print_result(f"Import {package_name}", False, str(e))
        return False

def check_outbound_https():
    print_header("Outbound HTTPS Connectivity")

    try:
        import requests
    except ImportError:
        print("❌ Cannot test HTTPS - 'requests' package not installed")
        print("   Run: pip3 install --user requests")
        return False

    endpoints = [
        ("GitHub API", "https://api.github.com/rate_limit"),
        ("Anthropic API", "https://api.anthropic.com/"),
        ("Telegram API", "https://api.telegram.org/"),
    ]

    all_passed = True
    for name, url in endpoints:
        try:
            response = requests.get(url, timeout=10)
            passed = response.status_code in [200, 401, 403, 405]
            print_result(
                f"Connect to {name}",
                passed,
                f"Status: {response.status_code}"
            )
            if not passed:
                all_passed = False
        except requests.exceptions.RequestException as e:
            print_result(f"Connect to {name}", False, str(e))
            all_passed = False

    return all_passed

def check_write_permissions():
    print_header("File Write Permissions")

    test_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".write_test")
    try:
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        print_result("Write to script directory", True)
        return True
    except Exception as e:
        print_result("Write to script directory", False, str(e))
        return False

def check_full_dependencies():
    print_header("Full Dependency Check")

    dependencies = [
        ("requests", "requests"),
        ("anthropic", "anthropic"),
        ("mysql-connector-python", "mysql.connector"),
    ]

    all_passed = True
    for package_name, import_name in dependencies:
        if not check_package_import(package_name, import_name):
            all_passed = False
            print(f"       Install with: pip3 install --user {package_name}")

    return all_passed

def check_environment_info():
    print_header("Environment Information")

    print(f"  Working Directory: {os.getcwd()}")
    print(f"  Script Location:   {os.path.dirname(os.path.abspath(__file__))}")
    print(f"  User:              {os.environ.get('USER', os.environ.get('USERNAME', 'unknown'))}")
    print(f"  Home Directory:    {os.path.expanduser('~')}")
    print(f"  PATH:              {os.environ.get('PATH', 'not set')[:100]}...")

def main():
    print("\n" + "#" * 60)
    print("#  WordPress Hosting Viability Test")
    print("#" * 60)

    full_test = "--full" in sys.argv

    results = {}

    results["python"] = check_python_version()
    results["pip"] = check_pip()
    results["write"] = check_write_permissions()

    check_environment_info()

    if check_package_import("requests", "requests"):
        results["https"] = check_outbound_https()
    else:
        print_header("Outbound HTTPS Connectivity")
        print("⚠️  Skipped - install 'requests' first:")
        print("   pip3 install --user requests")
        print("   Then re-run this script")
        results["https"] = None

    if full_test:
        results["dependencies"] = check_full_dependencies()

    print_header("Summary")

    all_passed = True
    for test, passed in results.items():
        if passed is None:
            print(f"⚠️  {test}: SKIPPED")
        elif passed:
            print(f"✅ {test}: PASSED")
        else:
            print(f"❌ {test}: FAILED")
            all_passed = False

    print("\n" + "-" * 60)
    if all_passed and results.get("https") is not None:
        print("🎉 All checks passed! Your host appears viable.")
    elif results.get("https") is None:
        print("⚠️  Install 'requests' package and re-run to complete testing.")
    else:
        print("❌ Some checks failed. Review the issues above.")

    if not full_test:
        print("\n💡 Run with --full to test all required dependencies:")
        print("   python3 test_hosting.py --full")

    print()
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
