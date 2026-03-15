"""
Root conftest.py — ensures the project root is on sys.path for all tests.
This allows `from shared.X import ...` and `from backend.X import ...`
to resolve correctly both locally and in CI.
"""
import sys
import os

# Insert the project root at the front of sys.path
sys.path.insert(0, os.path.dirname(__file__))
