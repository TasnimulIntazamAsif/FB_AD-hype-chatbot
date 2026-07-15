"""
MCP Server Test Script
========================
এই স্ক্রিপ্টটি MCP সার্ভারকে সরাসরি টেস্ট করার জন্য।
CLI তে চালিয়ে দেখতে পারেন সার্ভার সঠিকভাবে কাজ করছে কিনা।

Run: python test_mcp.py
"""

import sys
import json
from pathlib import Path

# Project root যোগ করুন
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp_server import ask_ad_analytics, get_table_info, get_schema, get_quick_stats

def test_tools():
    """সব MCP টুল টেস্ট করুন"""
    print("=" * 60)
    print("🧪 Testing MCP Tools")
    print("=" * 60)

    # Test 1: get_quick_stats
    print("\n📊 Test 1: get_quick_stats()")
    print("-" * 40)
    result = get_quick_stats()
    print(result[:500] + "..." if len(result) > 500 else result)

    # Test 2: get_table_info
    print("\n\n📋 Test 2: get_table_info()")
    print("-" * 40)
    result = get_table_info()
    print(result)

    # Test 3: get_schema
    print("\n\n📋 Test 3: get_schema()")
    print("-" * 40)
    result = get_schema()
    print(result[:500] + "..." if len(result) > 500 else result)

    # Test 4: ask_ad_analytics - Specific question about PeopleDesk
    print("\n\n🗣️ Test 4: ask_ad_analytics (PeopleDesk Campaign Analysis)")
    print("-" * 40)
    question = "PeopleDesk e joto campaign choltese tar modde konta kharap choltese and konta valo choltese?"
    print(f"\n❓ Question: {question}")
    print(f"\n📝 Response:")
    print("=" * 60)
    result = ask_ad_analytics(question)
    print(result)
    print("=" * 60)

    # Test 5: ask_ad_analytics - English version
    print("\n\n🗣️ Test 5: ask_ad_analytics (English - PeopleDesk)")
    print("-" * 40)
    question = "Among all PeopleDesk campaigns, which ones are performing well and which ones are underperforming?"
    print(f"\n❓ Question: {question}")
    print(f"\n📝 Response:")
    print("=" * 60)
    result = ask_ad_analytics(question)
    print(result)
    print("=" * 60)

    print("\n\n" + "=" * 60)
    print("✅ All tests completed!")


if __name__ == "__main__":
    test_tools()