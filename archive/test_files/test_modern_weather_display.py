#!/usr/bin/env python3
"""
Test script for Modern Weather Display functionality in Bible Clock.
Tests the new card-based design at different screen sizes and with Fahrenheit.
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

def test_modern_weather_display_different_sizes():
    """Test modern weather display at different screen sizes."""
    logger.info("Testing Modern Weather Display at Different Sizes...")
    
    # Test different e-ink display sizes
    test_sizes = [
        (600, 450, "Small E-ink Display"),
        (800, 600, "Medium E-ink Display"), 
        (1872, 1404, "Large E-ink Display (Bible Clock)")
    ]
    
    try:
        from modern_weather_display import ModernWeatherDisplay
        from weather_settings import weather_settings
        
        # Set to Fahrenheit for testing
        weather_settings.set_temperature_unit('F')
        
        results = []
        
        for width, height, description in test_sizes:
            logger.info(f"Testing {description} ({width}x{height})...")
            
            # Create display generator for this size
            display_generator = ModernWeatherDisplay(width, height)
            
            # Generate weather display
            weather_image = display_generator.generate_modern_weather_display()
            
            if weather_image:
                # Verify correct size
                actual_size = weather_image.size
                expected_size = (width, height)
                
                if actual_size == expected_size:
                    logger.info(f"✓ {description}: Generated correctly at {actual_size}")
                    
                    # Save test image
                    safe_name = description.lower().replace(' ', '_').replace('(', '').replace(')', '')
                    output_path = Path(f'test_modern_weather_{safe_name}.png')
                    weather_image.save(output_path)
                    logger.info(f"✓ Saved: {output_path}")
                    
                    results.append(True)
                else:
                    logger.error(f"✗ {description}: Size mismatch - expected {expected_size}, got {actual_size}")
                    results.append(False)
            else:
                logger.error(f"✗ {description}: Failed to generate image")
                results.append(False)
        
        # Reset settings
        weather_settings.reset_to_defaults()
        
        return all(results)
        
    except Exception as e:
        logger.error(f"Modern weather display size test failed: {e}")
        return False

def test_modern_vs_legacy_display():
    """Compare modern weather display with legacy display."""
    logger.info("Testing Modern vs Legacy Weather Display...")
    
    try:
        from modern_weather_display import ModernWeatherDisplay
        from weather_display_generator import WeatherDisplayGenerator
        from weather_settings import weather_settings
        
        # Set consistent settings
        weather_settings.set_temperature_unit('F')
        
        # Test size
        width, height = 800, 600
        
        # Generate modern display
        modern_generator = ModernWeatherDisplay(width, height)
        modern_image = modern_generator.generate_modern_weather_display()
        
        # Generate legacy display
        legacy_generator = WeatherDisplayGenerator(width, height)
        legacy_image = legacy_generator.generate_weather_display()
        
        if modern_image and legacy_image:
            # Save comparison images
            modern_image.save('test_modern_weather_comparison.png')
            legacy_image.save('test_legacy_weather_comparison.png')
            
            logger.info("✓ Modern weather display generated successfully")
            logger.info("✓ Legacy weather display generated successfully")
            logger.info("✓ Comparison images saved")
            
            # Verify both are correct size
            modern_correct = modern_image.size == (width, height)
            legacy_correct = legacy_image.size == (width, height)
            
            logger.info(f"✓ Modern display size: {modern_image.size} {'✓' if modern_correct else '✗'}")
            logger.info(f"✓ Legacy display size: {legacy_image.size} {'✓' if legacy_correct else '✗'}")
            
            # Reset settings
            weather_settings.reset_to_defaults()
            
            return modern_correct and legacy_correct
        else:
            logger.error("✗ Failed to generate one or both displays")
            return False
        
    except Exception as e:
        logger.error(f"Modern vs legacy comparison test failed: {e}")
        return False

def test_modern_weather_with_image_generator():
    """Test modern weather display integration with main image generator."""
    logger.info("Testing Modern Weather Display Integration...")
    
    try:
        from image_generator import ImageGenerator
        from verse_manager import VerseManager
        from weather_settings import weather_settings
        
        # Set to Fahrenheit
        weather_settings.set_temperature_unit('F')
        
        # Initialize components
        ig = ImageGenerator()
        vm = VerseManager()
        
        # Set weather mode and get data
        vm.display_mode = 'weather'
        verse_data = vm.get_current_verse()
        
        if verse_data and verse_data.get('is_weather_mode'):
            logger.info("✓ Weather verse data ready for image generation")
            
            # Generate image using modern weather display
            image = ig.create_verse_image(verse_data)
            
            if image:
                logger.info(f"✓ Modern weather image generated: {image.size[0]}x{image.size[1]}")
                
                # Save test image
                test_output_path = Path('test_modern_weather_integrated.png')
                image.save(test_output_path)
                logger.info(f"✓ Integrated test image saved to: {test_output_path}")
                
                # Reset settings
                weather_settings.reset_to_defaults()
                
                return True
            else:
                logger.error("✗ Modern weather image generation failed")
                return False
        else:
            logger.error("✗ Weather verse data not ready")
            return False
        
    except Exception as e:
        logger.error(f"Modern weather integration test failed: {e}")
        return False

def test_responsive_design_features():
    """Test responsive design features of modern weather display."""
    logger.info("Testing Responsive Design Features...")
    
    try:
        from modern_weather_display import ModernWeatherDisplay
        
        # Test different display categories
        test_configs = [
            (600, 400, "small", 0.8),      # Small display
            (800, 600, "medium", 1.0),     # Medium display
            (1872, 1404, "large", 1.5)     # Large display
        ]
        
        results = []
        
        for width, height, category, expected_scale in test_configs:
            logger.info(f"Testing {category} display configuration...")
            
            display = ModernWeatherDisplay(width, height)
            
            # Check responsive properties
            scale_factor = display.scale_factor
            is_correct_category = (
                (category == "small" and display.is_small_display) or
                (category == "medium" and display.is_medium_display) or
                (category == "large" and display.is_large_display)
            )
            
            # Check if scale factor is approximately correct
            scale_correct = abs(scale_factor - expected_scale) < 0.1
            
            logger.info(f"  Scale factor: {scale_factor} (expected: {expected_scale}) {'✓' if scale_correct else '✗'}")
            logger.info(f"  Category detection: {category} {'✓' if is_correct_category else '✗'}")
            
            # Check font scaling
            hero_font_size = display.font_sizes['hero']
            expected_hero_size = int(48 * expected_scale)
            font_correct = abs(hero_font_size - expected_hero_size) <= 1
            
            logger.info(f"  Hero font size: {hero_font_size} (expected: {expected_hero_size}) {'✓' if font_correct else '✗'}")
            
            test_passed = is_correct_category and scale_correct and font_correct
            results.append(test_passed)
            
            logger.info(f"  {category.capitalize()} display test: {'PASSED' if test_passed else 'FAILED'}")
        
        return all(results)
        
    except Exception as e:
        logger.error(f"Responsive design test failed: {e}")
        return False

def main():
    """Run all modern weather display tests."""
    logger.info("=== Modern Weather Display Test Suite ===")
    
    tests = [
        ("Modern Weather Display Different Sizes", test_modern_weather_display_different_sizes),
        ("Modern vs Legacy Comparison", test_modern_vs_legacy_display),
        ("Integration with Image Generator", test_modern_weather_with_image_generator),
        ("Responsive Design Features", test_responsive_design_features)
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
        logger.info("🎉 All modern weather display tests passed!")
        return True
    else:
        logger.warning(f"⚠️  {total - passed} test(s) failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)