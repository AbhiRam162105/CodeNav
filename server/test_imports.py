#!/usr/bin/env python3
"""Test imports for agent system."""

import sys
import traceback

def test_import(module_name):
    """Test importing a module."""
    try:
        __import__(module_name)
        print(f"✓ {module_name}")
        return True
    except Exception as e:
        print(f"✗ {module_name}: {e}")
        traceback.print_exc()
        return False

print("Testing agent imports...")
print("-" * 50)

# Test external dependencies
test_import("google.generativeai")
test_import("sentence_transformers")
test_import("faiss")

print("\n" + "-" * 50)
print("Testing agent modules...")
print("-" * 50)

# Test agent modules
test_import("agent.llm_client")
test_import("agent.prompts")
test_import("agent.tool_parser")
test_import("agent.tool_executor")
test_import("agent.history")
test_import("agent.loop")

print("\nDone!")
