#!/usr/bin/env python3
"""
Test script to verify devotional rotation is working correctly
"""

import json
import logging
from pathlib import Path
from src.devotional_manager import DevotionalManager

def test_devotional_rotation():
    """Test the devotional rotation system."""
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("Testing Devotional Rotation System")
    print("=" * 50)
    
    # Initialize devotional manager
    manager = DevotionalManager()
    
    # Check cache stats
    stats = manager.get_devotional_stats()
    print(f"Devotional Database Stats:")
    print(f"  Total cached entries: {stats['total_cached']}")
    print(f"  Rotation interval: {stats['rotation']['interval_minutes']} minutes")
    print(f"  Total slots per day: {stats['rotation']['slots_per_day']}")
    print(f"  Current slot: {stats['rotation']['current_slot']}")
    print(f"  Next change at: {stats['rotation']['next_change_at']}")
    print()
    
    # Test getting rotating devotional
    print("Current Rotating Devotional:")
    print("-" * 30)
    
    devotional = manager.get_rotating_devotional()
    if devotional:
        print(f"Title: {devotional['title']}")
        print(f"Scripture: {devotional['scripture_reference']}")
        print(f"Author: {devotional['author']}")
        print(f"Theme: {devotional.get('theme', 'N/A')}")
        print(f"Entry Number: {devotional.get('entry_number', 'N/A')}")
        print(f"Rotation Slot: {devotional['rotation_slot']}")
        print(f"Cache Position: {devotional.get('cache_position', 'N/A')}")
        print(f"Next Change: {devotional['next_change_at']}")
        print(f"\nDevotional Text:")
        print(devotional['devotional_text'][:300] + "..." if len(devotional['devotional_text']) > 300 else devotional['devotional_text'])
        print()
    else:
        print("No devotional found!")
        return
    
    # Test rotation by simulating different time slots
    print("Testing Rotation Across Time Slots:")
    print("-" * 40)
    
    test_slots = [0, 24, 48, 72, 96]  # Different rotation slots
    seen_devotionals = set()
    
    for slot in test_slots:
        test_devotional = manager._get_random_devotional_from_cache(slot)
        if test_devotional:
            devotional_id = test_devotional.get('entry_number', test_devotional['title'])
            seen_devotionals.add(devotional_id)
            print(f"Slot {slot:3d}: {test_devotional['title']} (Entry #{test_devotional.get('entry_number', '?')})")
    
    print(f"\nUnique devotionals in test: {len(seen_devotionals)} out of {len(test_slots)} slots")
    
    # Test different rotation intervals
    print("\nTesting Different Rotation Intervals:")
    print("-" * 42)
    
    intervals = [5, 10, 15, 30, 60]
    for interval in intervals:
        manager.set_rotation_interval(interval)
        test_devotional = manager.get_rotating_devotional()
        if test_devotional:
            slots_per_day = 1440 // interval
            print(f"{interval:2d} min intervals: {slots_per_day:2d} slots/day - Next change: {test_devotional['next_change_at']}")
    
    # Reset to default
    manager.set_rotation_interval(15)
    
    # Show some sample devotionals
    print("\nSample Devotionals from Database:")
    print("-" * 35)
    
    cache_keys = list(manager.devotional_cache.keys())[:5]  # Show first 5
    for i, key in enumerate(cache_keys, 1):
        devotional = manager.devotional_cache[key]
        print(f"{i}. {devotional['title']}")
        print(f"   Scripture: {devotional['scripture_reference']}")
        print(f"   Theme: {devotional.get('theme', 'N/A')}")
        print(f"   Text: {devotional['devotional_text'][:100]}...")
        print()
    
    print("Devotional rotation test completed successfully!")

if __name__ == "__main__":
    test_devotional_rotation()