#!/usr/bin/env python3
"""
Test script to show both weather pages (simulating 30-second rotation)
"""

import sys
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_both_weather_pages():
    """Test both weather pages by simulating different times."""
    print("🔧 Testing Both Weather Pages (30-second rotation)...")
    
    try:
        from modern_weather_display import ModernWeatherDisplay
        
        # Test both pages by mocking different times
        display = ModernWeatherDisplay(width=1872, height=1404)
        
        # Test Page 1 (0-29 seconds) - Current Location
        print("   Testing Page 1: Current Location...")
        with patch('modern_weather_display.datetime') as mock_datetime:
            # Mock time that gives page 0 (e.g., 15 seconds past minute)
            mock_now = datetime(2025, 8, 21, 15, 0, 15)  # 15 seconds = page 0
            mock_datetime.now.return_value = mock_now
            
            # Generate page 1
            weather_image_1 = display.generate_modern_weather_display()
            
            if weather_image_1:
                output_path_1 = Path('test_weather_page_1_current_location.png')
                weather_image_1.save(output_path_1)
                print(f"   ✅ Generated Page 1 (Current Location): {output_path_1}")
            else:
                print("   ❌ Failed to generate Page 1")
                return False
        
        # Test Page 2 (30-59 seconds) - Jerusalem
        print("   Testing Page 2: Jerusalem...")
        with patch('modern_weather_display.datetime') as mock_datetime:
            # Mock time that gives page 1 (e.g., 45 seconds past minute)
            mock_now = datetime(2025, 8, 21, 15, 0, 45)  # 45 seconds = page 1
            mock_datetime.now.return_value = mock_now
            
            # Generate page 2
            weather_image_2 = display.generate_modern_weather_display()
            
            if weather_image_2:
                output_path_2 = Path('test_weather_page_2_jerusalem.png')
                weather_image_2.save(output_path_2)
                print(f"   ✅ Generated Page 2 (Jerusalem): {output_path_2}")
            else:
                print("   ❌ Failed to generate Page 2")
                return False
        
        print("✅ Both weather pages generated successfully!")
        print("\n📋 Page Rotation Details:")
        print("   • Page 1 (0-29 seconds): Shows current location from settings")
        print("   • Page 2 (30-59 seconds): Shows Jerusalem, Israel")
        print("   • Automatic rotation: Every 30 seconds")
        print("   • Page indicator: ● ○ or ○ ● at bottom")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_both_weather_pages()
    if success:
        print("\n🎉 Page-flipping weather display test completed!")
        print("The display will automatically rotate between locations every 30 seconds.")
    else:
        print("❌ Test failed - check the errors above")
    
    sys.exit(0 if success else 1)