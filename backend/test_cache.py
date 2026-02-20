"""
Test for the AI response cache module.
Run: python test_cache.py (from the backend directory)
"""
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_database
from cache import generate_cache_key, get_cached_response, set_cached_response, get_cache_stats, cleanup_expired_cache


def test_cache_key_determinism():
    """Same input should always produce the same cache key"""
    key1 = generate_cache_key("evaluate_pseudocode", "def bubble_sort(arr): ...")
    key2 = generate_cache_key("evaluate_pseudocode", "def bubble_sort(arr): ...")
    key3 = generate_cache_key("evaluate_pseudocode", "def quick_sort(arr): ...")
    
    assert key1 == key2, f"Same input produced different keys: {key1} vs {key2}"
    assert key1 != key3, "Different inputs should produce different keys"
    print("✅ Cache key determinism: PASSED")


def test_cache_miss():
    """Non-existent key should return None"""
    key = generate_cache_key("test_miss", "nonexistent_content_12345")
    result = get_cached_response("test_miss", key)
    assert result is None, f"Expected None for cache miss, got {result}"
    print("✅ Cache miss: PASSED")


def test_cache_store_and_hit():
    """Stored response should be retrievable"""
    call_type = "test_store"
    content = "test_content_for_caching"
    mock_response = {"total_score": 85, "breakdown": [{"criterion": "Correctness", "score": 42}]}
    
    key = generate_cache_key(call_type, content)
    set_cached_response(call_type, key, mock_response)
    
    # Retrieve it
    cached = get_cached_response(call_type, key)
    assert cached is not None, "Cache should return stored response"
    assert cached["total_score"] == 85, f"Unexpected score: {cached['total_score']}"
    assert cached["breakdown"][0]["criterion"] == "Correctness"
    print("✅ Cache store and hit: PASSED")


def test_cache_stats():
    """Stats should show entries and hits"""
    stats = get_cache_stats()
    assert "total_entries" in stats, "Stats missing total_entries"
    assert "active_entries" in stats, "Stats missing active_entries"
    assert "total_cache_hits" in stats, "Stats missing total_cache_hits"
    assert stats["active_entries"] > 0, "Should have at least one active entry from previous test"
    print(f"✅ Cache stats: PASSED (entries={stats['active_entries']}, hits={stats['total_cache_hits']})")


def test_different_call_types():
    """Same content but different call types should have different cache entries"""
    content = "shared_test_content"
    response_a = {"type": "A", "score": 90}
    response_b = {"type": "B", "score": 70}
    
    key_a = generate_cache_key("type_a", content)
    key_b = generate_cache_key("type_b", content)
    
    set_cached_response("type_a", key_a, response_a)
    set_cached_response("type_b", key_b, response_b)
    
    cached_a = get_cached_response("type_a", key_a)
    cached_b = get_cached_response("type_b", key_b)
    
    assert cached_a["score"] == 90, f"Type A should return 90, got {cached_a['score']}"
    assert cached_b["score"] == 70, f"Type B should return 70, got {cached_b['score']}"
    print("✅ Different call types isolation: PASSED")


if __name__ == "__main__":
    print("\n=== Running AI Response Cache Tests ===\n")
    
    # Ensure database is initialized
    init_database()
    
    test_cache_key_determinism()
    test_cache_miss()
    test_cache_store_and_hit()
    test_cache_stats()
    test_different_call_types()
    
    # Cleanup test entries
    cleanup_expired_cache()
    
    print("\n=== All tests PASSED ✅ ===\n")
