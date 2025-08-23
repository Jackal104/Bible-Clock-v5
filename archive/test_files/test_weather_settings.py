#!/usr/bin/env python3
"""
Test script for Weather Settings functionality in Bible Clock.
Tests temperature conversion, custom locations, and settings persistence.
"""

import sys
import os
import logging
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_weather_settings():
    """Test weather settings functionality."""
    logger.info("Testing Weather Settings...")
    
    try:
        from weather_settings import weather_settings
        
        # Test default settings
        logger.info("Testing default settings...")
        all_settings = weather_settings.get_all_settings()
        logger.info(f"✓ Default settings loaded: {list(all_settings.keys())}")
        
        # Test temperature unit (should default to F)
        temp_unit = weather_settings.get_temperature_unit()
        logger.info(f"✓ Default temperature unit: {temp_unit}")
        assert temp_unit == "F", f"Expected 'F', got '{temp_unit}'"
        
        # Test temperature conversion
        celsius_temp = 20.0  # 20°C
        converted_temp = weather_settings.convert_temperature(celsius_temp)
        expected_fahrenheit = 68.0  # 20°C = 68°F
        logger.info(f"✓ Temperature conversion: {celsius_temp}°C = {converted_temp}°F")
        assert abs(converted_temp - expected_fahrenheit) < 0.1, f"Expected {expected_fahrenheit}°F, got {converted_temp}°F"
        
        # Test changing to Celsius
        weather_settings.set_temperature_unit('C')
        temp_unit = weather_settings.get_temperature_unit()
        logger.info(f"✓ Changed temperature unit to: {temp_unit}")
        assert temp_unit == "C", f"Expected 'C', got '{temp_unit}'"
        
        # Test temperature conversion in Celsius
        converted_temp = weather_settings.convert_temperature(celsius_temp)
        logger.info(f"✓ Temperature conversion (Celsius): {celsius_temp}°C = {converted_temp}°C")
        assert abs(converted_temp - celsius_temp) < 0.1, f"Expected {celsius_temp}°C, got {converted_temp}°C"
        
        # Test temperature symbol
        temp_symbol = weather_settings.get_temperature_symbol()
        logger.info(f"✓ Temperature symbol: {temp_symbol}")
        assert temp_symbol == "°C", f"Expected '°C', got '{temp_symbol}'"
        
        # Test custom location
        logger.info("Testing custom location settings...")
        weather_settings.set_custom_location("New York", "United States", 40.7128, -74.0060)
        custom_location = weather_settings.get_custom_location()
        logger.info(f"✓ Custom location set: {custom_location}")
        assert custom_location['enabled'] == True
        assert custom_location['city'] == "New York"
        assert custom_location['latitude'] == 40.7128
        
        # Test second location
        logger.info("Testing second location settings...")
        weather_settings.set_second_location("Tokyo, Japan", 35.6762, 139.6503)
        second_location = weather_settings.get_second_location()
        logger.info(f"✓ Second location set: {second_location}")
        assert second_location['name'] == "Tokyo, Japan"
        assert second_location['latitude'] == 35.6762
        
        # Reset to defaults for clean state
        weather_settings.reset_to_defaults()
        logger.info("✓ Settings reset to defaults")
        
        return True
        
    except Exception as e:
        logger.error(f"Weather settings test failed: {e}")
        return False

def test_weather_service_with_settings():
    """Test weather service with temperature conversion settings."""
    logger.info("Testing Weather Service with Settings...")
    
    try:
        from weather_service import weather_service
        from weather_settings import weather_settings
        
        # Set to Fahrenheit and test
        weather_settings.set_temperature_unit('F')
        
        # Get weather data
        weather_data = weather_service.get_complete_weather_data()
        
        if weather_data and weather_data.get('current_location'):
            current_weather = weather_data['current_location']['weather']
            if current_weather:
                current = current_weather.get('current', {})
                temp = current.get('temperature', 0)
                temp_unit = current.get('temperature_unit', '')
                
                logger.info(f"✓ Weather with Fahrenheit: {temp:.1f}{temp_unit}")
                assert temp_unit == "°F", f"Expected °F, got {temp_unit}"
                assert temp > -100 and temp < 200, f"Temperature out of reasonable range: {temp}°F"
        
        # Change to Celsius and test
        weather_settings.set_temperature_unit('C')
        
        # Clear cache and get fresh data
        weather_service._weather_cache = {}
        weather_data = weather_service.get_complete_weather_data()
        
        if weather_data and weather_data.get('current_location'):
            current_weather = weather_data['current_location']['weather']
            if current_weather:
                current = current_weather.get('current', {})
                temp = current.get('temperature', 0)
                temp_unit = current.get('temperature_unit', '')
                
                logger.info(f"✓ Weather with Celsius: {temp:.1f}{temp_unit}")
                assert temp_unit == "°C", f"Expected °C, got {temp_unit}"
                assert temp > -50 and temp < 100, f"Temperature out of reasonable range: {temp}°C"
        
        # Test global temperature unit in weather data
        global_temp_unit = weather_data.get('temperature_unit', '')
        logger.info(f"✓ Global temperature unit: {global_temp_unit}")
        assert global_temp_unit == "°C", f"Expected °C, got {global_temp_unit}"
        
        # Reset to defaults
        weather_settings.reset_to_defaults()
        
        return True
        
    except Exception as e:
        logger.error(f"Weather service with settings test failed: {e}")
        return False

def test_weather_display_with_fahrenheit():
    """Test weather display generation with Fahrenheit temperatures."""
    logger.info("Testing Weather Display with Fahrenheit...")
    
    try:
        from weather_display_generator import weather_display_generator
        from weather_settings import weather_settings
        
        # Set to Fahrenheit
        weather_settings.set_temperature_unit('F')
        
        # Generate weather display
        weather_image = weather_display_generator.generate_weather_display()
        
        if weather_image:
            logger.info(f"✓ Weather display generated with Fahrenheit: {weather_image.size[0]}x{weather_image.size[1]}")
            
            # Save test image
            test_output_path = Path('test_weather_fahrenheit.png')
            weather_image.save(test_output_path)
            logger.info(f"✓ Test image saved to: {test_output_path}")
        else:
            logger.warning("✗ Weather display generation failed")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Weather display with Fahrenheit test failed: {e}")
        return False

def main():
    """Run all weather settings tests."""
    logger.info("=== Bible Clock Weather Settings Test Suite ===")
    
    tests = [
        ("Weather Settings", test_weather_settings),
        ("Weather Service with Settings", test_weather_service_with_settings),
        ("Weather Display with Fahrenheit", test_weather_display_with_fahrenheit)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n--- Running: {test_name} ---")
        try:
            result = test_func()
            results[test_name] = result
            status = "PASSED" if result else "FAILED"
            logger.info(f"--- {test_name}: {status} ---")
        except Exception as e:
            logger.error(f"--- {test_name}: ERROR - {e} ---")
            results[test_name] = False
    
    # Summary
    logger.info("\n=== Test Results Summary ===")
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"{status}: {test_name}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All weather settings tests passed!")
        return True
    else:
        logger.warning(f"⚠️  {total - passed} test(s) failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)