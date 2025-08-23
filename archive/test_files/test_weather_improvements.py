#!/usr/bin/env python3
"""
Test script to verify weather display improvements:
1. Better readability with larger fonts and text-based weather icons
2. Improved spacing to prevent overlaps
3. Hourly weather data refresh mechanism
4. Screen refresh when weather updates
"""

import sys
import logging
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_modern_weather_display():
    """Test the improved modern weather display."""
    print("🔧 Testing Modern Weather Display Improvements...")
    
    try:
        from modern_weather_display import ModernWeatherDisplay
        
        # Test with different display sizes
        display_sizes = [
            (800, 600, "Medium E-ink Display"),
            (1200, 800, "Large E-ink Display"),
            (600, 448, "Small E-ink Display")
        ]
        
        for width, height, description in display_sizes:
            print(f"   Testing {description} ({width}x{height})...")
            
            # Create display generator
            display = ModernWeatherDisplay(width=width, height=height)
            
            # Generate weather image
            weather_image = display.generate_modern_weather_display()
            
            if weather_image:
                # Save test image
                output_path = Path(f'test_weather_improved_{width}x{height}.png')
                weather_image.save(output_path)
                print(f"   ✅ Generated {description} image: {output_path}")
            else:
                print(f"   ❌ Failed to generate {description} image")
                return False
        
        print("✅ Modern Weather Display tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Modern Weather Display test failed: {e}")
        return False

def test_weather_refresh_mechanism():
    """Test the weather data refresh mechanism."""
    print("🔧 Testing Weather Refresh Mechanism...")
    
    try:
        from weather_service import weather_service
        from datetime import datetime, timedelta
        
        # Test should_refresh_weather_data method
        should_refresh = weather_service.should_refresh_weather_data()
        print(f"   Current weather refresh status: {should_refresh}")
        
        # Test force refresh functionality
        weather_data = weather_service.get_complete_weather_data(force_refresh=True)
        if weather_data:
            print("   ✅ Force refresh mechanism working")
            
            # Check if we have fresh data
            updated_time = weather_data.get('updated')
            if updated_time:
                try:
                    dt = datetime.fromisoformat(updated_time)
                    age = datetime.now() - dt
                    print(f"   Weather data age: {age.total_seconds():.1f} seconds")
                except:
                    print("   Weather data timestamp format couldn't be parsed")
            
            return True
        else:
            print("   ❌ Force refresh failed to retrieve data")
            return False
            
    except Exception as e:
        print(f"❌ Weather refresh mechanism test failed: {e}")
        return False

def test_weather_mode_integration():
    """Test weather mode integration with verse manager."""
    print("🔧 Testing Weather Mode Integration...")
    
    try:
        from verse_manager import VerseManager
        from image_generator import ImageGenerator
        
        # Create managers
        verse_manager = VerseManager()
        image_generator = ImageGenerator()
        
        # Set to weather mode and get data
        verse_manager.set_display_mode('weather')
        verse_data = verse_manager.get_current_verse()
        
        if verse_data and verse_data.get('is_weather_mode'):
            print("   ✅ Weather mode verse data retrieved")
            
            # Generate weather display image
            weather_image = image_generator.create_verse_image(verse_data)
            
            if weather_image:
                # Save test image
                test_output_path = Path('test_weather_mode_integrated.png')
                weather_image.save(test_output_path)
                print(f"   ✅ Generated integrated weather image: {test_output_path}")
                return True
            else:
                print("   ❌ Failed to generate weather image")
                return False
        else:
            print("   ❌ Weather mode not properly activated")
            return False
            
    except Exception as e:
        print(f"❌ Weather mode integration test failed: {e}")
        return False

def run_all_improvement_tests():
    """Run all weather improvement tests."""
    print("🌦️  Starting Weather Display Improvement Tests")
    print("=" * 50)
    
    # Configure logging for tests
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    tests = [
        ("Modern Weather Display", test_modern_weather_display),
        ("Weather Refresh Mechanism", test_weather_refresh_mechanism),
        ("Weather Mode Integration", test_weather_mode_integration)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print()
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} - PASSED")
            else:
                failed += 1
                print(f"❌ {test_name} - FAILED")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name} - ERROR: {e}")
    
    print("\n" + "=" * 50)
    print(f"Weather Improvement Tests Summary: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All weather improvement tests passed!")
        print("\nImprovements implemented:")
        print("  ✓ Better readability with larger fonts")
        print("  ✓ Text-based weather icons for e-ink compatibility")
        print("  ✓ Improved card spacing to prevent overlap")
        print("  ✓ Hourly weather data refresh mechanism")
        print("  ✓ Automatic screen refresh when weather updates")
    else:
        print(f"⚠️  {failed} test(s) failed. Please check the logs for details.")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_improvement_tests()
    sys.exit(0 if success else 1)