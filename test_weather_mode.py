#!/usr/bin/env python3
"""
Test script for the new Weather Mode functionality in Bible Clock.
Tests weather service, verse manager integration, and display generation.
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

def test_weather_service():
    """Test the weather service functionality."""
    logger.info("Testing Weather Service...")
    
    try:
        from weather_service import weather_service
        
        # Test location detection
        logger.info("Testing location detection...")
        location = weather_service.get_current_location()
        if location:
            logger.info(f"✓ Location detected: {location['city']}, {location['country']}")
        else:
            logger.warning("✗ Location detection failed")
        
        # Test weather forecast for current location
        if location:
            logger.info("Testing current location weather...")
            weather = weather_service.get_weather_forecast(
                location['latitude'], 
                location['longitude'],
                f"{location['city']}, {location['country']}"
            )
            if weather:
                logger.info(f"✓ Current location weather: {weather['current']['temperature']}°C, {weather['current']['description']}")
            else:
                logger.warning("✗ Current location weather failed")
        
        # Test Jerusalem weather
        logger.info("Testing Jerusalem weather...")
        jerusalem_weather = weather_service.get_weather_forecast(31.7683, 35.2137, "Jerusalem, Israel")
        if jerusalem_weather:
            logger.info(f"✓ Jerusalem weather: {jerusalem_weather['current']['temperature']}°C, {jerusalem_weather['current']['description']}")
        else:
            logger.warning("✗ Jerusalem weather failed")
        
        # Test moon phases
        logger.info("Testing moon phases...")
        moon_data = weather_service.get_moon_phase_data()
        if moon_data:
            logger.info(f"✓ Moon data: {moon_data['current_illumination']}% illuminated")
        else:
            logger.warning("✗ Moon phase data failed")
        
        # Test complete weather data
        logger.info("Testing complete weather data...")
        complete_data = weather_service.get_complete_weather_data()
        if complete_data:
            logger.info("✓ Complete weather data retrieved successfully")
        else:
            logger.warning("✗ Complete weather data failed")
        
        return True
        
    except Exception as e:
        logger.error(f"Weather service test failed: {e}")
        return False

def test_verse_manager_weather_mode():
    """Test weather mode integration in verse manager."""
    logger.info("Testing Verse Manager Weather Mode...")
    
    try:
        from verse_manager import VerseManager
        
        # Initialize verse manager
        vm = VerseManager()
        
        # Set to weather mode
        vm.display_mode = 'weather'
        logger.info("✓ Weather mode set")
        
        # Get weather verse data
        verse_data = vm.get_current_verse()
        
        if verse_data and verse_data.get('is_weather_mode'):
            logger.info("✓ Weather mode verse data retrieved")
            logger.info(f"  Reference: {verse_data.get('reference', 'N/A')}")
            logger.info(f"  Text: {verse_data.get('text', 'N/A')[:100]}...")
            
            if verse_data.get('weather_data'):
                logger.info("✓ Weather data included in verse response")
            else:
                logger.warning("✗ Weather data missing from verse response")
        else:
            logger.warning("✗ Weather mode verse data failed")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Verse manager weather mode test failed: {e}")
        return False

def test_weather_display_generation():
    """Test weather display image generation."""
    logger.info("Testing Weather Display Generation...")
    
    try:
        from weather_display_generator import weather_display_generator
        
        # Generate weather display
        logger.info("Generating weather display image...")
        weather_image = weather_display_generator.generate_weather_display()
        
        if weather_image:
            logger.info(f"✓ Weather display generated: {weather_image.size[0]}x{weather_image.size[1]}")
            
            # Save test image
            test_output_path = Path('test_weather_display.png')
            weather_image.save(test_output_path)
            logger.info(f"✓ Test image saved to: {test_output_path}")
            
        else:
            logger.warning("✗ Weather display generation failed")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Weather display generation test failed: {e}")
        return False

def test_image_generator_integration():
    """Test weather mode integration in image generator."""
    logger.info("Testing Image Generator Weather Mode Integration...")
    
    try:
        from image_generator import ImageGenerator
        from verse_manager import VerseManager
        
        # Initialize components
        ig = ImageGenerator()
        vm = VerseManager()
        
        # Set weather mode and get data
        vm.display_mode = 'weather'
        verse_data = vm.get_current_verse()
        
        if verse_data and verse_data.get('is_weather_mode'):
            logger.info("✓ Weather verse data ready for image generation")
            
            # Generate image
            logger.info("Generating weather mode image...")
            image = ig.create_verse_image(verse_data)
            
            if image:
                logger.info(f"✓ Weather mode image generated: {image.size[0]}x{image.size[1]}")
                
                # Save test image
                test_output_path = Path('test_weather_mode_image.png')
                image.save(test_output_path)
                logger.info(f"✓ Test image saved to: {test_output_path}")
                
            else:
                logger.warning("✗ Weather mode image generation failed")
                return False
        else:
            logger.warning("✗ Weather verse data not ready")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Image generator weather mode test failed: {e}")
        return False

def main():
    """Run all weather mode tests."""
    logger.info("=== Bible Clock Weather Mode Test Suite ===")
    
    tests = [
        ("Weather Service", test_weather_service),
        ("Verse Manager Weather Mode", test_verse_manager_weather_mode),
        ("Weather Display Generation", test_weather_display_generation),
        ("Image Generator Integration", test_image_generator_integration)
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
        logger.info("🎉 All weather mode tests passed!")
        return True
    else:
        logger.warning(f"⚠️  {total - passed} test(s) failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)