# Bible Clock v5

A comprehensive Raspberry Pi-based e-ink display system that shows Bible verses corresponding to the current time, featuring a modern web interface, parallel translation mode, advanced voice control, AI integration, and **optimized memory management**.

## 🆕 What's New in v5

### 🎯 **Major Features Added**
- **Parallel Translation Mode**: Display two Bible translations side by side
- **Random Translation Support**: Intelligent "random" translation selection with proper persistence
- **Mobile-First UI**: Completely redesigned responsive web interface optimized for mobile devices
- **Hardware Recovery System**: Automatic display error detection and recovery
- **GPIO Error Resolution**: Fixed all hardware communication issues
- **Statistics Tracking**: Accurate translation usage statistics (tracks actual translations, not "random")

### 🔧 **Technical Improvements**
- **Memory Optimization**: Reduced memory usage by 30%+ with smart garbage collection
- **Enhanced RSS Processing**: More efficient news fetching with better memory management  
- **Improved System Monitoring**: Smarter process detection and realistic thresholds
- **Better Error Logging**: Reduced memory footprint while maintaining functionality
- **Multiple News Sources**: Times of Israel + Jerusalem Post for comprehensive coverage
- **GPIO Hardware Fixes**: Resolved all "GPIO channel setup" errors for stable hardware operation

### 🎨 **UI/UX Enhancements**
- **Mobile Dashboard**: Touch-optimized interface for smartphones and tablets
- **Reorganized Settings**: Parallel mode settings integrated with translation settings
- **Simplified Controls**: Removed redundant sections, focused on core functionality
- **Improved Navigation**: Clean mobile/desktop layout with better organization

## ✨ Features

### Core Features
- **Time-Based Verses**: Hour = Chapter, Minute = Verse
- **Date-Based Mode**: Biblical calendar events for special dates
- **Random Mode**: Inspirational verses any time
- **Parallel Translation Mode**: Display two translations simultaneously
- **Multiple Translations**: KJV, ESV, NASB, AMP, NLT, CEV, MSG + Random selection
- **Book Summaries**: Complete book overviews displayed at minute :00

### Display & Visual
- **E-ink Optimization**: Optimized for 10.3" Waveshare IT8951 displays
- **9 Beautiful Backgrounds + 9 Border Styles**: Automatically cycling visual elements
- **Font Management**: Multiple fonts with dynamic switching
- **Simulation Mode**: Test without hardware using file output
- **Hardware Recovery**: Automatic error detection and display reinitialization

### Web Interface
- **Modern Responsive Dashboard**: Works perfectly on mobile, tablet, and desktop
- **Mobile-Optimized Controls**: Touch-friendly interface with large buttons
- **Settings Management**: Complete configuration with live preview
- **Statistics Page**: Usage analytics with interactive charts
- **RESTful API**: Full API for integration and automation
- **Real-time Updates**: Live verse display with automatic refreshing

### Advanced Features
- **Enhanced Voice Control**: "Hey Bible" wake word with comprehensive commands
- **ChatGPT Integration**: AI-powered biblical questions and context-aware answers
- **Performance Monitoring**: System health tracking and alerts
- **Error Handling**: Automatic retry logic with graceful fallbacks
- **Advanced Scheduling**: Smart update timing and background tasks
- **Biblical Calendar**: 22+ curated events throughout the year
- **Parallel Mode**: Primary and secondary translations displayed simultaneously

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/Jackal104/Bible-Clock-v5.git
cd Bible-Clock-v5

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# For minimal installation (software mode only):
pip install -r requirements-dev.txt

# For full installation (includes voice and AI features):
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your preferences
```

### 2. Software Mode (Local Development)

For local development without Raspberry Pi hardware:

```bash
# Install minimal dependencies
pip install -r requirements-dev.txt

# Run in software simulation mode  
python main.py --simulation

# Access web interface at http://localhost:7777
```

### 3. Hardware Mode (Raspberry Pi)

```bash
# Run with hardware display support
./venv/bin/python main.py

# Run without voice control (recommended for stability)
./venv/bin/python main.py --disable-voice

# Access via mDNS
# http://bible-clock.local:7777
```

### 4. Different Running Modes

```bash
# Web interface only (great for testing)
python main.py --web-only

# Full system with display
python main.py

# Simulation mode (no hardware required)
python main.py --simulation

# Debug mode with detailed logging
python main.py --debug --log-file app.log
```

## 📱 Mobile Web Interface

### Mobile Dashboard Features
- **Touch-Optimized Controls**: Large buttons designed for mobile use
- **Mode Switching**: Easy switching between Time, Date, Random, Weather, News modes
- **Parallel Mode Toggle**: Quick enable/disable for dual translations
- **Quick Actions**: Force update, clear display ghosting
- **System Status**: Real-time health monitoring
- **Responsive Design**: Adapts to all screen sizes

### Mobile Settings
- **Primary/Secondary Translations**: Easy selection with random option
- **Parallel Mode Control**: Toggle and configure dual translation display
- **Display Settings**: Font, background, and visual customization
- **Voice Control**: Wake word and voice command configuration
- **System Settings**: Hardware and performance options

## 🌐 Parallel Translation Mode

### Features
- **Dual Display**: Show two Bible translations side by side
- **Smart Selection**: Choose specific translations or use "random" for both
- **Persistent Settings**: "Random" settings maintain user preference while tracking actual translations
- **Cache Optimization**: Efficient verse loading for both translations
- **Statistics Tracking**: Records actual translation usage for analytics

### Usage
1. **Via Mobile Interface**: Use settings page to enable parallel mode
2. **Translation Selection**: Choose primary and secondary translations
3. **Random Support**: Select "random" for either/both translations
4. **Mode Persistence**: Settings remember your preferences across restarts

### Technical Details
- **Translation Resolution**: "Random" resolves to actual translations internally
- **Statistics Accuracy**: Usage stats track resolved translations (e.g., "ESV", "NLT") not "random"
- **Cache System**: Efficiently loads content for both translations
- **Display Layout**: Optimized side-by-side layout for readability

## 🔌 Hardware Setup

### Required Hardware
- **Raspberry Pi 4B** (2GB+ RAM recommended) 
- **Waveshare 10.3" IT8951** e-ink display with HAT
- **MicroSD card** (32GB+ recommended, Class 10)
- **Power supply** (3A+ for Pi 4, 5.1V USB-C)
- **Optional**: USB microphone for voice control
- **Optional**: ReSpeaker HAT for enhanced audio

### GPIO Connection & Setup
1. **Connect IT8951 HAT** to Raspberry Pi GPIO pins (all 40 pins)
2. **Enable SPI interface**:
```bash
sudo raspi-config
# Interface Options > SPI > Enable
sudo reboot
```

3. **Install IT8951 Library**:
```bash
# IT8951 library is included in requirements.txt
pip install IT8951
```

### Display Configuration
- **Resolution**: 1872x1404 (10.3" display)
- **Rotation**: Configurable via environment variables
- **Refresh**: Partial updates for performance, full refresh for quality
- **VCOM**: Auto-detected from display ribbon cable

### System Service Installation
```bash
# Install as system service for auto-start
sudo cp systemd/bible-clock.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bible-clock
sudo systemctl start bible-clock

# View logs
sudo journalctl -u bible-clock -f

# Check status
sudo systemctl status bible-clock
```

### Network Configuration
```bash
# Enable mDNS for bible-clock.local access
sudo systemctl enable avahi-daemon
sudo systemctl start avahi-daemon

# Access via: http://bible-clock.local:7777
```

## 🎙️ Enhanced Voice Control

### Wake Word Commands
All voice commands start with **"Hey Bible"** followed by your request:

#### Display Control
- **"Hey Bible, speak verse"** - Read current verse aloud
- **"Hey Bible, refresh display"** - Update the display
- **"Hey Bible, change background"** - Switch background style
- **"Hey Bible, parallel mode"** - Enable dual translation display
- **"Hey Bible, time mode"** - Switch to time-based verses
- **"Hey Bible, date mode"** - Switch to biblical calendar
- **"Hey Bible, random mode"** - Switch to random verses

#### Information Commands
- **"Hey Bible, what time is it"** - Current time
- **"Hey Bible, system status"** - System health report
- **"Hey Bible, current mode"** - Display mode information
- **"Hey Bible, help"** - Voice command help

#### Biblical AI Questions
- **"Hey Bible, what does this verse mean?"**
- **"Hey Bible, who was King David?"** 
- **"Hey Bible, explain this passage"**
- **"Hey Bible, tell me about Exodus"**

### Voice Setup
```bash
# Install voice dependencies (included in requirements.txt)
pip install speechrecognition pyaudio pyttsx3

# For ReSpeaker HAT (optional enhanced audio)
./scripts/setup_respeaker.sh

# Enable voice in configuration
echo "ENABLE_VOICE=true" >> .env
echo "WAKE_WORD=hey bible" >> .env
```

## 📊 API Documentation

### Base URL
- **Local**: `http://localhost:7777`
- **Network**: `http://bible-clock.local:7777`

### Core Endpoints

#### Verse Management
```bash
GET /api/verse          # Current verse data
POST /api/refresh       # Force display refresh
GET /api/verse-history  # Recent verse history
```

#### Settings Management
```bash
GET /api/settings       # Current configuration
POST /api/settings      # Update settings
```

Example settings update:
```json
{
  "parallel_mode": true,
  "translation": "random",
  "secondary_translation": "esv",
  "display_mode": "time"
}
```

#### System Status
```bash
GET /api/status         # System health and statistics
GET /api/health         # Basic health check
```

#### Display Control
```bash
POST /api/refresh       # Update display
POST /api/clear-ghosting  # Clear e-ink ghosting
POST /api/preview       # Generate preview image
```

### Example API Responses

#### Current Verse
```json
{
  "success": true,
  "data": {
    "reference": "John 3:16",
    "text": "For God so loved the world...",
    "book": "John",
    "chapter": 3,
    "verse": 16,
    "translation": "ESV",
    "parallel_mode": true,
    "secondary_translation": "NLT",
    "secondary_text": "For this is how God loved...",
    "timestamp": "2024-12-17T10:30:00"
  }
}
```

#### Settings Response
```json
{
  "success": true,
  "data": {
    "translation": "random",
    "secondary_translation": "amp", 
    "parallel_mode": true,
    "display_mode": "time",
    "voice_enabled": false,
    "available_translations": ["kjv", "esv", "amp", "nlt", "msg", "nasb", "cev", "random"]
  }
}
```

## 🛠️ Configuration

### Environment Variables (.env)
```bash
# Display Settings
DISPLAY_WIDTH=1872
DISPLAY_HEIGHT=1404
SIMULATION_MODE=false
DISPLAY_ROTATION=0
DISPLAY_MIRROR=false

# Web Interface
WEB_HOST=0.0.0.0
WEB_PORT=7777
WEB_DEBUG=false

# Bible Settings
BIBLE_API_URL=https://bible-api.com
DEFAULT_TRANSLATION=kjv
PARALLEL_MODE=false
SECONDARY_TRANSLATION=amp

# Voice Control
ENABLE_VOICE=false
WAKE_WORD=hey bible
VOICE_RATE=150
VOICE_VOLUME=0.8

# ChatGPT Integration
OPENAI_API_KEY=your_openai_api_key_here
ENABLE_CHATGPT=false
CHATGPT_MODEL=gpt-3.5-turbo

# Hardware Settings  
FORCE_REFRESH_INTERVAL=60
VCOM_VOLTAGE=-2.0
DISPLAY_PHYSICAL_ROTATION=180
```

### Command Line Options
```bash
python main.py --help

Options:
  --debug              Enable debug logging
  --simulation         Run in simulation mode
  --web-only          Run only web interface
  --disable-voice     Disable voice control (recommended)
  --disable-web       Disable web interface
  --log-file FILE     Log to specified file
```

## 📅 Biblical Calendar Events

The date mode includes 25+ carefully selected biblical events:

### Major Christian Holidays
- **New Year (1/1)**: God's Covenant Renewal  
- **Epiphany (1/6)**: Manifestation of Christ
- **Valentine's Day (2/14)**: God's Love
- **Easter Season (varies)**: Passover/Resurrection
- **Christmas (12/25)**: Birth of Christ

### Family & Life Events  
- **Mother's Day (2nd Sun in May)**: Honoring Mothers
- **Father's Day (3rd Sun in June)**: Godly Fatherhood
- **Thanksgiving (4th Thu in Nov)**: Gratitude to God

### Seasonal Celebrations
- **Spring Equinox (3/20)**: New Life in Christ
- **Summer Solstice (6/21)**: Light of the World  
- **Autumn Equinox (9/22)**: Harvest & Provision
- **Winter Solstice (12/21)**: Hope in Darkness

### National & Cultural
- **Independence Day (7/4)**: Freedom in Christ
- **Memorial Day (Last Mon in May)**: Sacrifice & Service
- **Labor Day (1st Mon in Sep)**: Work as Worship

## 📈 Performance & Monitoring

### System Requirements
- **RAM**: 1GB minimum, 2GB+ recommended
- **Storage**: 500MB for application, 2GB+ for logs/cache
- **Network**: WiFi or Ethernet for verse fetching
- **Display**: IT8951-compatible e-ink display

### Performance Specifications
- **Memory Usage**: ~200MB typical, ~400MB peak
- **Display Update**: 2-3 seconds full refresh, <1 second partial  
- **Web Response**: <100ms for API calls, <200ms for page loads
- **Storage Growth**: ~1MB per month (logs and cache)
- **Network Usage**: ~1MB per day (verse fetching)

### Monitoring Features
- **Real-time Statistics**: Memory, CPU, display health
- **Error Tracking**: Automatic error logging and recovery
- **Performance Metrics**: Response times, success rates
- **Hardware Health**: Display communication status, GPIO health
- **Usage Analytics**: Translation preferences, mode usage patterns

## 🔧 Troubleshooting

### Common Issues & Solutions

#### GPIO/Hardware Errors
```bash
# Check for GPIO setup errors
sudo dmesg | grep -i gpio

# Verify SPI is enabled
lsmod | grep spi

# Test hardware connection
python -c "from IT8951.display import AutoEPDDisplay; print('Hardware OK')"

# If GPIO errors persist, restart service:
sudo systemctl restart bible-clock
```

#### Web Interface Issues
```bash
# Check if web server is running
curl http://localhost:7777/health

# Test mobile interface
curl -H "User-Agent: Mobile" http://localhost:7777/

# View web interface logs  
./venv/bin/python main.py --debug --web-only
```

#### Display Not Updating
```bash
# Force display refresh
curl -X POST http://localhost:7777/api/refresh

# Clear e-ink ghosting
curl -X POST http://localhost:7777/api/clear-ghosting

# Check display status
curl http://localhost:7777/api/status | grep display
```

#### Translation Issues
```bash
# Test random translation resolution
curl http://localhost:7777/api/verse | jq '.data.translation'

# Check parallel mode
curl http://localhost:7777/api/settings | jq '.data.parallel_mode'

# Verify translation cache
ls -la data/translations/
```

#### Memory/Performance Issues
```bash
# Monitor system resources
htop

# Check application memory usage
curl http://localhost:7777/api/status | jq '.data.memory_usage'

# View performance statistics
curl http://localhost:7777/api/status | jq '.data.performance'
```

#### Voice Control Issues
```bash
# Test microphone
arecord -l

# Check voice dependencies
python -c "import speech_recognition; print('Speech recognition OK')"

# Run without voice (recommended for stability)
./venv/bin/python main.py --disable-voice
```

### Log Analysis
```bash
# View system logs
sudo journalctl -u bible-clock -f

# Check error logs
tail -f data/daily_error_log.json

# Debug specific issues
./venv/bin/python main.py --debug --log-file debug.log
```

## 📂 Project Structure

```
Bible-Clock-v5/
├── main.py                 # Application entry point
├── requirements.txt        # Full dependencies (voice + AI)
├── requirements-dev.txt    # Minimal dependencies (software only)
├── .env.example           # Configuration template
├── README.md              # This documentation
├── INSTALLATION.md        # Detailed installation guide
├── HARDWARE.md           # Hardware setup guide
│
├── src/                   # Core application modules
│   ├── verse_manager.py   # Bible verse logic with parallel mode
│   ├── image_generator.py # Image creation with backgrounds/fonts
│   ├── display_manager.py # E-ink display control + GPIO recovery
│   ├── service_manager.py # Main service orchestration
│   ├── voice_control.py   # Voice command processing
│   ├── scheduler.py       # Advanced task scheduling
│   ├── performance_monitor.py # System monitoring
│   ├── error_handler.py   # Error handling & retry logic
│   ├── config_validator.py # Configuration validation
│   ├── display_constants.py # E-ink display constants
│   └── web_interface/     # Web interface components
│       ├── app.py         # Flask application + API
│       ├── templates/     # HTML templates
│       │   ├── base.html  # Base desktop template
│       │   ├── dashboard.html # Desktop dashboard
│       │   ├── settings.html  # Desktop settings
│       │   ├── statistics.html # Statistics page
│       │   └── mobile/    # Mobile-optimized templates
│       │       ├── base.html      # Mobile base template
│       │       ├── dashboard.html # Mobile dashboard
│       │       └── settings.html  # Mobile settings
│       └── static/        # CSS, JS, images
│           ├── css/style.css  # Responsive styles
│           └── js/app.js      # JavaScript application
│
├── data/                  # Application data
│   ├── biblical_calendar.json # Date-based events (25+ events)
│   ├── fallback_verses.json  # Offline verse backup
│   ├── book_summaries.json   # Bible book descriptions
│   ├── active_sessions.json  # User session tracking
│   ├── aggregated_metrics.json # Usage analytics
│   ├── daily_error_log.json    # Error tracking
│   ├── translations/         # Bible translation files
│   │   ├── bible_kjv.json   # King James Version
│   │   ├── bible_esv.json   # English Standard Version
│   │   ├── bible_amp.json   # Amplified Bible
│   │   ├── bible_nlt.json   # New Living Translation
│   │   ├── bible_msg.json   # The Message
│   │   ├── bible_nasb1995.json # NASB 1995
│   │   └── bible_cev.json   # Contemporary English Version
│   └── fonts/               # TrueType fonts
│
├── images/               # Background images (9 backgrounds + 9 borders)
├── scripts/             # Utility scripts
│   ├── setup_respeaker.sh  # ReSpeaker HAT setup
│   └── install_service.sh  # System service installer
├── systemd/            # Service configuration
│   └── bible-clock.service
└── tests/              # Test files
    ├── test_verse_manager.py
    ├── test_display_manager.py
    └── test_web_interface.py
```

## 🧪 Development & Testing

### Local Development Setup
```bash
# Clone and setup
git clone https://github.com/Jackal104/Bible-Clock-v5.git
cd Bible-Clock-v5
python3 -m venv venv
source venv/bin/activate

# Install development dependencies
pip install -r requirements-dev.txt

# Run in simulation mode
python main.py --simulation --debug

# Access web interface
open http://localhost:7777
```

### Testing Different Features
```bash
# Test parallel translation mode
curl -X POST http://localhost:7777/api/settings \
  -H "Content-Type: application/json" \
  -d '{"parallel_mode": true, "translation": "random", "secondary_translation": "esv"}'

# Test mobile interface
curl -H "User-Agent: Mobile" http://localhost:7777/

# Test API endpoints
curl http://localhost:7777/api/verse | jq
curl http://localhost:7777/api/status | jq
```

### Adding Custom Content
- **Backgrounds**: Add 1872x1404 PNG files to `images/backgrounds/`
- **Borders**: Add 1872x1404 PNG files to `images/borders/`  
- **Fonts**: Add TTF files to `data/fonts/`
- **Events**: Edit `data/biblical_calendar.json`
- **Translations**: Add JSON files to `data/translations/`

## 🤝 Contributing

### How to Contribute
1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Test** in simulation mode first
4. **Commit** changes (`git commit -m 'Add amazing feature'`)
5. **Push** to the branch (`git push origin feature/amazing-feature`)
6. **Open** a Pull Request

### Development Guidelines
- **Test mobile interface** on actual mobile devices
- **Verify parallel translation mode** works correctly
- **Ensure GPIO hardware compatibility** (if modifying display code)
- **Test in simulation mode** before hardware testing
- **Add appropriate tests** for new features
- **Update documentation** for new features
- **Follow existing code style** and patterns

### Priority Areas for Contribution
- **Additional Bible translations**
- **More biblical calendar events**
- **Enhanced mobile UI features**
- **Voice command improvements**
- **Performance optimizations**
- **Hardware compatibility (other e-ink displays)**

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Waveshare** for excellent IT8951 e-ink display hardware and drivers
- **Bible API providers** for verse access and multiple translations
- **OpenAI** for ChatGPT integration capabilities  
- **Bible translation organizations** for their invaluable work
- **Open source community** for libraries, tools, and inspiration
- **Beta testers** who helped refine the mobile interface
- **Contributors** who continue to improve this project

## 🔗 Related Documentation

- **[INSTALLATION.md](INSTALLATION.md)** - Detailed installation guide
- **[HARDWARE.md](HARDWARE.md)** - Hardware setup and troubleshooting
- **[API.md](API.md)** - Complete API documentation
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Developer guidelines

---

## 🎯 Key Features Summary

### ✅ **Core Bible Features**
- Time-based verses (Hour:Minute = Chapter:Verse)
- Parallel translation display (side-by-side)
- Random translation selection with persistence
- 7 Bible translations + "random" option
- Biblical calendar with 25+ events
- Book summaries at minute :00

### ✅ **Hardware & Display** 
- IT8951 10.3" e-ink display support
- GPIO error recovery system
- Automatic hardware reinitialization
- 9 backgrounds + 9 border styles
- Multiple font options
- Simulation mode for development

### ✅ **Web Interface**
- Mobile-first responsive design
- Touch-optimized controls
- Real-time verse updates
- Settings management
- Statistics and monitoring
- RESTful API

### ✅ **Advanced Features**
- Voice control with "Hey Bible" wake word
- ChatGPT AI integration for biblical questions
- System health monitoring
- Error tracking and recovery
- Performance optimization
- Automatic service management

---

*"Thy word is a lamp unto my feet, and a light unto my path." - Psalm 119:105*

**Bible Clock v5** - Bringing God's Word to your daily life through modern technology. 🙏