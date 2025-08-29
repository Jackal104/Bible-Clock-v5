#!/bin/bash
# Bible Clock v3.0 - Startup Script
# Activates virtual environment and starts Bible Clock

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "📖 Starting Bible Clock v3.0..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run the setup script first: ./scripts/setup_bible_clock.sh"
    exit 1
fi

# Activate virtual environment
echo "🐍 Activating virtual environment..."
source venv/bin/activate

# Check if main.py exists
if [ ! -f "main.py" ]; then
    echo "❌ main.py not found!"
    echo "Please ensure you're in the Bible-Clockv2 directory"
    exit 1
fi

# Set environment variables for voice control
export ENABLE_VOICE=true
export DISPLAY_WIDTH=1872
export DISPLAY_HEIGHT=1404
export BIBLE_API_URL=https://bible-api.com
export DISPLAY_MIRROR=true
export DISPLAY_PHYSICAL_ROTATION=0
export FORCE_REFRESH_INTERVAL=60

# Cleanup any lingering GPIO state that might block display access
echo "🧹 Cleaning up GPIO state..."
python3 -c "
try:
    import RPi.GPIO as GPIO
    GPIO.cleanup()
    print('✅ GPIO cleaned up successfully')
except Exception as e:
    print(f'GPIO cleanup: {e}')
" 2>/dev/null

# Kill any remaining processes that might hold GPIO/display resources
# Note: Don't kill bible-clock service processes, only python processes
pkill -f 'python.*main.py' >/dev/null 2>&1 || true
pkill -f 'IT8951' >/dev/null 2>&1 || true

# Start Bible Clock with voice control disabled temporarily due to audio device conflicts
echo "🚀 Launching Bible Clock..."
# Allow access to system site-packages (needed for feedparser)
export PYTHONPATH="/usr/lib/python3/dist-packages:$PYTHONPATH"
python main.py