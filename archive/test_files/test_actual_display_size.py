#!/usr/bin/env python3
"""
Test weather display with actual hardware dimensions: 1872x1404
"""

import sys
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_actual_display_weather():
    """Test with actual hardware dimensions."""
    print("🔧 Testing with actual display size: 1872x1404...")
    
    try:
        from modern_weather_display import ModernWeatherDisplay
        
        # Test with actual hardware dimensions
        display = ModernWeatherDisplay(width=1872, height=1404)
        print(f"   Display scale factor: {display.scale_factor}")
        print(f"   Font sizes: {display.font_sizes}")
        print(f"   Card dimensions: padding={display.card_padding}, margin={display.card_margin}")
        
        # Generate weather image
        weather_image = display.generate_modern_weather_display()
        
        if weather_image:
            # Save test image
            output_path = Path('test_weather_actual_hardware_1872x1404.png')
            weather_image.save(output_path)
            print(f"   ✅ Generated actual hardware size image: {output_path}")
            return True
        else:
            print("   ❌ Failed to generate weather image")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_actual_display_weather()
    if success:
        print("\n🎯 Check the generated image to see the layout issues!")
        print("This shows what your actual display is seeing.")
    else:
        print("❌ Could not generate test image")