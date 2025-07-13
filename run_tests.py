#!/usr/bin/env python
"""
Test runner script για το hierarchical leave approval system
"""
import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner

if __name__ == "__main__":
    # Ensure we're in the correct directory
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdede_leaves.settings')
    django.setup()
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    
    # Define test modules to run
    test_modules = [
        'accounts.tests.test_models',
        'leaves.tests.test_templatetags',
        'leaves.tests.test_models',
        'leaves.tests.test_views',
        'leaves.tests.test_integration',
    ]
    
    print("=" * 80)
    print("HIERARCHICAL LEAVE APPROVAL SYSTEM - TEST SUITE")
    print("=" * 80)
    print()
    
    # Run each test module separately for better organization
    total_failures = 0
    
    for module in test_modules:
        print(f"Running tests for: {module}")
        print("-" * 50)
        
        failures = test_runner.run_tests([module], verbosity=2)
        total_failures += failures
        
        print()
        
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    if total_failures == 0:
        print("✅ All tests passed successfully!")
        print()
        print("The hierarchical leave approval system is working correctly:")
        print("- User hierarchy and approval chain logic ✓")
        print("- Template permission logic ✓")
        print("- Leave request model methods ✓")
        print("- View permissions and workflows ✓")
        print("- End-to-end integration workflows ✓")
        print()
        print("System is ready for production use!")
    else:
        print(f"❌ {total_failures} test(s) failed.")
        print("Please review the failures above and fix any issues.")
        
    print("=" * 80)
    
    sys.exit(total_failures)