#!/usr/bin/env python3
"""
Revert the overly aggressive contrast changes that made images too dark.
Apply more gentle contrast enhancement suitable for e-ink.
"""

from PIL import Image, ImageEnhance
import os
from pathlib import Path

def gentle_contrast_fix(input_path, output_path):
    """
    Apply gentle contrast enhancement - much less aggressive than before.
    """
    try:
        # Open and convert to grayscale for e-ink optimization
        image = Image.open(input_path)
        if image.mode != 'L':
            image = image.convert('L')  # Convert to grayscale
        
        # Very gentle contrast enhancement - just enough to be visible
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.3)  # Much less aggressive than 3.0-4.0
        
        # Very slight brightness adjustment - keep it light
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(0.95)  # Much less aggressive than 0.6-0.7
        
        # Save the enhanced image
        image.save(output_path)
        print(f"Gently enhanced: {input_path}")
        return True
        
    except Exception as e:
        print(f"Error enhancing {input_path}: {e}")
        return False

def revert_all_images():
    """Revert contrast on all images to be more subtle."""
    base_dir = Path("/home/admin/Bible-Clock-v4")
    
    # Fix backgrounds (indices 01-10) - make them very subtle
    backgrounds_dir = base_dir / "images" / "backgrounds"
    print("Reverting background contrast...")
    for i in range(1, 11):
        filename = f"{i:02d}_*.png"
        files = list(backgrounds_dir.glob(filename))
        for file_path in files:
            # For backgrounds, make them very subtle - barely visible
            gentle_contrast_fix(file_path, file_path)
    
    # Fix borders (indices 01-10) - make them visible but not too dark
    borders_dir = base_dir / "images" / "borders"
    print("\nReverting border contrast...")
    for i in range(1, 11):
        filename = f"{i:02d}_*.png"
        files = list(borders_dir.glob(filename))
        for file_path in files:
            # For borders, make them visible but not overly dark
            gentle_contrast_fix(file_path, file_path)
    
    print("\nGentle contrast reversion complete!")

if __name__ == "__main__":
    revert_all_images()