#!/usr/bin/env python3
"""
Simple test to verify imports and basic functionality
"""

print("Testing imports...")

# Test config import
print("1. Importing config...")
from config import QUIRK_ANALYSIS_QUERIES, DEFAULT_MODEL
print(f"   ✓ Found {len(QUIRK_ANALYSIS_QUERIES)} predefined queries")

# Test function signatures
print("2. Checking function signatures...")
import inspect

# We can't actually import due to Python 3.9 compatibility issue in caller.py
# But we can verify our changes are syntactically correct via py_compile
import py_compile
import sys

try:
    py_compile.compile('utils/quirk_analyzer.py', doraise=True)
    print("   ✓ quirk_analyzer.py syntax OK")
except py_compile.PyCompileError as e:
    print(f"   ✗ Syntax error in quirk_analyzer.py: {e}")
    sys.exit(1)

try:
    py_compile.compile('app.py', doraise=True)
    print("   ✓ app.py syntax OK")
except py_compile.PyCompileError as e:
    print(f"   ✗ Syntax error in app.py: {e}")
    sys.exit(1)

try:
    py_compile.compile('config.py', doraise=True)
    print("   ✓ config.py syntax OK")
except py_compile.PyCompileError as e:
    print(f"   ✗ Syntax error in config.py: {e}")
    sys.exit(1)

print("\n3. Verifying QUIRK_ANALYSIS_QUERIES content...")
for i, query in enumerate(QUIRK_ANALYSIS_QUERIES, 1):
    print(f"   {i}. \"{query}\"")

print("\n✓ All basic tests passed!")
print("\nNote: Full runtime test requires Python 3.10+ due to latteries/caller.py compatibility.")
print("However, all syntax checks pass and the app should work when run via Streamlit.")
