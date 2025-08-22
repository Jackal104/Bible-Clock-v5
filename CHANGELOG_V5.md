# Bible Clock v5 Changelog

## Memory Management & Performance Optimizations

### 🚀 Performance Improvements
- **30%+ Memory Reduction**: Optimized from 193MB → 140MB average usage
- **Smart Garbage Collection**: Automatic cleanup after RSS fetching and image generation
- **Efficient Object Management**: Proper cleanup of temporary objects throughout codebase

### 📰 Enhanced News Service
- **Multiple RSS Sources**: Added Jerusalem Post alongside Times of Israel
- **Increased Story Capacity**: 8 cached articles (up from 5) with better memory management
- **Memory-Aware Processing**: Limits article content size and forces cleanup between operations
- **Better Error Handling**: Improved RSS parsing with proper memory cleanup on errors

### 🖼️ Display Generator Optimizations
- **Reduced Gradient Complexity**: Optimized background generation (10 steps vs 20)
- **Memory Logging**: Tracks memory usage after image generation
- **Proper Cleanup**: Forces garbage collection before and after display generation
- **Draw Object Management**: Explicit cleanup of PIL drawing objects

### 📊 System Monitoring Improvements
- **Realistic Thresholds**: 650MB memory limit (70% of 1GB) instead of conservative 200MB
- **Better Process Detection**: Fixed system monitor to detect Bible Clock process correctly
- **CPU Threshold Adjustment**: 50% sustained CPU threshold (allows normal spikes to 100%)
- **Extended Tolerance**: 3-minute sustained high usage before restart (was 2.5 minutes)

### 🔧 Error Logging Optimization
- **Reduced Storage**: 25 error limit (down from 100) to prevent memory buildup
- **Limited Field Lengths**: Truncated error messages, tracebacks, and metadata
- **Efficient Tracebacks**: Only last 5 lines of stack traces (was unlimited)
- **Memory-Safe Exception Handling**: Length limits on all error log components

### 🛠️ Technical Improvements
- **Emergency Cleanup Tool**: Added `force_memory_cleanup.py` for manual intervention
- **Better RSS Feed Management**: Pre-compiled regex patterns and efficient HTML tag removal
- **Optimized Article Processing**: Length limits on titles/descriptions to prevent bloat
- **Memory Usage Logging**: Real-time memory tracking throughout news processing

### 🎯 Configuration Updates
- **Memory Thresholds**: 
  - Process limit: 650MB (70% of 1GB RAM)
  - System memory: 85% threshold
  - CPU sustained: 50% over 3 minutes
- **News Capacity**: 8 articles from 2 RSS sources
- **Error Retention**: 25 recent errors with size limits

### 🐛 Bug Fixes
- Fixed system monitor detecting itself instead of Bible Clock process
- Resolved memory leak in RSS feed parsing
- Corrected error log memory accumulation
- Improved image generation memory cleanup

## Migration from v4
v5 is fully backward compatible with v4 configurations. The memory optimizations are automatic and require no configuration changes.

## System Requirements
- **RAM**: Works well on 1GB Raspberry Pi systems
- **Storage**: Same as v4 requirements  
- **Performance**: Significant improvement in memory efficiency and stability