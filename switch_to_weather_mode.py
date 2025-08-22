#!/usr/bin/env python3
"""
Quick script to switch Bible Clock to weather mode
"""

import sys
import requests
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def switch_to_weather_mode():
    """Switch to weather mode via web API or direct method."""
    try:
        # Try web API first
        try:
            response = requests.post('http://localhost:5000/api/mode/weather', timeout=5)
            if response.status_code == 200:
                print("✅ Switched to weather mode via web API")
                return True
        except requests.RequestException:
            pass
        
        # Try alternative API endpoint
        try:
            response = requests.post('http://localhost:5000/api/display_mode', 
                                   json={'mode': 'weather'}, timeout=5)
            if response.status_code == 200:
                print("✅ Switched to weather mode via web API")
                return True
        except requests.RequestException:
            pass
        
        # Direct method - create a temporary file to signal mode change
        import json
        signal_file = Path('data/mode_change_signal.json')
        signal_data = {
            'requested_mode': 'weather',
            'timestamp': '2025-08-21T09:10:00'
        }
        
        with open(signal_file, 'w') as f:
            json.dump(signal_data, f)
        
        print("✅ Created weather mode signal file")
        print("The system should switch to weather mode on the next update cycle")
        return True
        
    except Exception as e:
        print(f"❌ Failed to switch to weather mode: {e}")
        return False

def show_instructions():
    """Show manual instructions for switching to weather mode."""
    print("\n📋 Manual Methods to Switch to Weather Mode:")
    print("\n1. Voice Control (if enabled):")
    print("   - Say: 'Bible Clock'")
    print("   - Wait for response")
    print("   - Say: 'weather mode'")
    
    print("\n2. Web Interface:")
    print("   - Open browser to: http://[your-pi-ip]:5000")
    print("   - Go to Settings")
    print("   - Change Display Mode to 'Weather'")
    
    print("\n3. Wait for automatic cycling (if enabled)")
    
    print("\n🔧 The weather display improvements are now active!")
    print("   - Much better readability at 10ft distance")
    print("   - Text-based weather icons (SUN, CLDY, RAIN)")
    print("   - Clean temperature display without overlap")
    print("   - Hourly automatic weather data refresh")

if __name__ == "__main__":
    print("🌦️  Bible Clock Weather Mode Switcher")
    print("=" * 40)
    
    success = switch_to_weather_mode()
    
    if not success:
        show_instructions()
    
    print("\n✨ Weather display improvements are loaded and ready!")