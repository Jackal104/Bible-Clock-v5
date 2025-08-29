"""
Manages e-ink display output and simulation.
"""

import os
import logging
import psutil
from PIL import Image, ImageDraw, ImageFont
from typing import Optional
import time
import threading

try:
    from display_constants import DisplayModes
except ImportError:
    from .display_constants import DisplayModes

class DisplayManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.simulation_mode = os.getenv('SIMULATION_MODE', 'false').lower() == 'true'
        self.width = int(os.getenv('DISPLAY_WIDTH', '1872'))
        self.height = int(os.getenv('DISPLAY_HEIGHT', '1404'))
        self.restore_callback = None  # Will be set by service manager
        self._ai_display_active = False  # Flag to prevent interruptions during AI display
        self._display_locked = False  # Lock to prevent any display updates during AI responses
        self._lock_timer = None  # Timer to unlock display after AI response completes
        
        # Hardware recovery system for 24/7 reliability
        self.timeout_count = 0
        self.last_successful_update = time.time()
        self.max_consecutive_timeouts = 3
        self.service_manager = None  # Will be set by main.py
        # Convert rotation to IT8951 expected format
        rotation_setting = os.getenv('DISPLAY_ROTATION', '0')
        if rotation_setting == '0':
            self.rotation = None  # No rotation
        elif rotation_setting == '90':
            self.rotation = 'CW'
        elif rotation_setting == '180':
            self.rotation = 'flip'
        elif rotation_setting == '270':
            self.rotation = 'CCW'
        else:
            self.rotation = None
        self.vcom_voltage = float(os.getenv('DISPLAY_VCOM', '-1.21'))
        self.force_refresh_interval = int(os.getenv('FORCE_REFRESH_INTERVAL', '60'))  # 1 hour to reduce ghosting
        
        self.last_image_hash = None
        self.last_full_refresh = time.time()
        self.partial_refresh_count = 0  # Track partial refreshes for ghosting prevention
        self.max_partial_refreshes = 10  # Force full refresh after N partial refreshes
        self.display_device = None
        
        if not self.simulation_mode:
            self._initialize_hardware()
    
    def set_restore_callback(self, callback):
        """Set callback function to restore normal display."""
        self.restore_callback = callback
    
    def lock_display(self, duration: float = 30.0):
        """Lock display to prevent updates during AI responses."""
        self._display_locked = True
        self._ai_display_active = True
        
        # Cancel any existing timer
        if self._lock_timer:
            self._lock_timer.cancel()
        
        # Set timer to unlock display after duration + 15 seconds buffer
        unlock_delay = duration + 15.0
        self._lock_timer = threading.Timer(unlock_delay, self._unlock_display)
        self._lock_timer.start()
        
        self.logger.info(f"Display locked for {unlock_delay} seconds during AI response")
    
    def _unlock_display(self):
        """Unlock display and restore normal operation."""
        self._display_locked = False
        self._ai_display_active = False
        self._lock_timer = None
        
        self.logger.info("Display unlocked - normal updates resumed")
        
        # Trigger display restore
        if self.restore_callback:
            try:
                self.restore_callback()
            except Exception as e:
                self.logger.error(f"Failed to restore display after unlock: {e}")
    
    def is_display_locked(self) -> bool:
        """Check if display is currently locked."""
        return self._display_locked
    
    def set_service_manager(self, service_manager):
        """Set service manager reference for hardware recovery system."""
        self.service_manager = service_manager
    
    def _initialize_hardware(self):
        """Initialize the IT8951 e-ink display."""
        try:
            # Import hardware-specific modules
            from IT8951.display import AutoEPDDisplay
            import RPi.GPIO as GPIO
            
            # Clean up any previous GPIO state to prevent conflicts
            try:
                GPIO.cleanup()
                self.logger.debug("GPIO cleanup completed")
            except Exception as cleanup_error:
                self.logger.debug(f"GPIO cleanup warning (non-critical): {cleanup_error}")
            
            # Set GPIO mode explicitly before initializing the display
            try:
                GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering
                GPIO.setwarnings(False)  # Disable warnings for already configured pins
                self.logger.debug("GPIO mode set to BCM")
            except Exception as gpio_error:
                self.logger.warning(f"GPIO mode setup warning: {gpio_error}")
            
            self.display_device = AutoEPDDisplay(
                vcom=self.vcom_voltage,  # VCOM voltage from display ribbon
                rotate=self.rotation,
                spi_hz=24000000
            )
            
            self.logger.info(f"E-ink display initialized: {self.width}x{self.height}")
            
            
        except ImportError:
            self.logger.warning("IT8951 library not available, falling back to simulation")
            # Only enable simulation if explicitly requested
            if os.getenv('SIMULATION_MODE', 'false').lower() != 'false':
                self.simulation_mode = True
            else:
                self.logger.error("❌ CRITICAL: IT8951 library missing but simulation disabled!")
                raise ImportError("IT8951 library required for hardware mode")
        except Exception as e:
            self.logger.error(f"Display initialization failed: {e}")
            # Only enable simulation if explicitly requested
            if os.getenv('SIMULATION_MODE', 'false').lower() != 'false':
                self.simulation_mode = True
            else:
                self.logger.error("❌ CRITICAL: Display init failed but simulation disabled!")
                # Try one more time with explicit initialization
                try:
                    self.logger.info("🔧 Attempting display recovery...")
                    from IT8951.display import AutoEPDDisplay
                    self.display_device = AutoEPDDisplay(vcom=-1.5)
                    self.logger.info("✅ Display recovery successful!")
                except Exception as recovery_error:
                    self.logger.error(f"❌ Display recovery failed: {recovery_error}")
                    raise Exception(f"Hardware mode required but display unavailable: {e}")
    
    def display_image(self, image: Image.Image, force_refresh: bool = False, preserve_border: bool = False, bypass_lock: bool = False):
        """Display image on e-ink screen or save for simulation."""
        try:
            # Check if display is locked (unless this is an AI response bypassing the lock)
            if self._display_locked and not bypass_lock:
                self.logger.debug("Display update skipped - display is locked for AI response")
                return
            # Resize image to display dimensions
            if image.size != (self.width, self.height):
                image = image.resize((self.width, self.height), Image.Resampling.LANCZOS)
            
            # Convert to grayscale for e-ink
            if image.mode != 'L':
                image = image.convert('L')
            
            # Check if image has changed
            image_hash = hash(image.tobytes())
            needs_update = (
                force_refresh or 
                image_hash != self.last_image_hash or
                self._should_force_refresh()
            )
            
            if not needs_update:
                self.logger.info("Image unchanged, skipping update")
                return
            
            if self.simulation_mode:
                self._simulate_display(image)
                self.logger.info("Display updated (simulation mode)")
            else:
                self._display_on_hardware(image, force_refresh, preserve_border)
                self.logger.info("Display updated (hardware mode)")
            
            self.last_image_hash = image_hash
            self._check_memory_usage()
            
            # Reset timeout counter on successful update
            self.timeout_count = 0
            self.last_successful_update = time.time()
            
        except Exception as e:
            self.logger.error(f"Display update failed: {e}")
            
            # Check for timeout errors and implement recovery
            if "timed out" in str(e).lower() or "timeout" in str(e).lower():
                self.timeout_count += 1
                self.logger.warning(f"Display timeout detected (count: {self.timeout_count}/{self.max_consecutive_timeouts})")
                
                if self.timeout_count >= self.max_consecutive_timeouts:
                    self.logger.error("Multiple consecutive timeouts detected, attempting hardware recovery")
                    self._attempt_hardware_recovery()
    
    def _attempt_hardware_recovery(self):
        """Attempt to recover from hardware timeout by reinitializing display device."""
        try:
            self.logger.warning("🔧 Starting hardware recovery process...")
            
            # Step 1: Clean shutdown of current display device
            if self.display_device:
                try:
                    self.display_device.close()
                    self.logger.info("Display device closed successfully")
                except Exception as e:
                    self.logger.warning(f"Error closing display device: {e}")
                finally:
                    self.display_device = None
            
            # Step 2: Wait for hardware to reset
            time.sleep(2)
            
            # Step 3: Reinitialize hardware
            self._initialize_hardware()
            
            if self.display_device:
                self.logger.info("✅ Hardware recovery successful - display reinitialized")
                
                # Step 4: Reset timeout counters
                self.timeout_count = 0
                self.last_successful_update = time.time()
                
                # Step 5: Restore previous display state if possible
                if self.service_manager and hasattr(self.service_manager, 'restore_display_state'):
                    try:
                        self.logger.info("🔄 Attempting to restore previous display state...")
                        self.service_manager.restore_display_state()
                        self.logger.info("✅ Display state restored successfully")
                    except Exception as e:
                        self.logger.warning(f"Could not restore display state: {e}")
                        # Fallback: just clear the display
                        try:
                            self.clear_display()
                        except Exception as clear_error:
                            self.logger.error(f"Fallback clear display failed: {clear_error}")
                else:
                    self.logger.info("🔄 Service manager not available, clearing display as fallback")
                    try:
                        self.clear_display()
                    except Exception as clear_error:
                        self.logger.error(f"Recovery clear display failed: {clear_error}")
            else:
                self.logger.error("❌ Hardware recovery failed - display device still not available")
                # Only fall back to simulation if explicitly allowed
                if os.getenv('SIMULATION_MODE', 'false').lower() != 'false':
                    self.simulation_mode = True
                    self.logger.warning("Falling back to simulation mode due to hardware recovery failure")
                else:
                    self.logger.error("❌ CRITICAL: Hardware recovery failed but simulation disabled!")
        
        except Exception as e:
            self.logger.error(f"❌ Hardware recovery process failed: {e}")
            # Only enable simulation if explicitly allowed
            if os.getenv('SIMULATION_MODE', 'false').lower() != 'false':
                self.simulation_mode = True
                self.timeout_count = 0  # Reset counters to prevent recovery loops
            else:
                self.logger.error("❌ CRITICAL: Recovery failed but simulation disabled!")
    
    def _simulate_display(self, image: Image.Image):
        """Simulate display by saving image to file."""
        simulation_path = 'current_display.png'
        image.save(simulation_path)
        self.logger.info(f"Display simulated - image saved to {simulation_path}")
    
    def _display_on_hardware(self, image: Image.Image, force_refresh: bool, preserve_border: bool = False):
        """Display image on actual e-ink hardware."""
        if not self.display_device:
            raise RuntimeError("Display device not initialized")
        
        # Apply mirroring if needed (fixes backwards text)
        mirror_setting = os.getenv('DISPLAY_MIRROR', 'false').lower()
        if mirror_setting == 'true':
            image = image.transpose(Image.FLIP_LEFT_RIGHT)
        elif mirror_setting == 'vertical':
            image = image.transpose(Image.FLIP_TOP_BOTTOM)
        elif mirror_setting == 'both':
            image = image.transpose(Image.FLIP_LEFT_RIGHT)
            image = image.transpose(Image.FLIP_TOP_BOTTOM)
        
        # Apply software rotation for precise control (since hardware rotation=None)
        # This ensures proper coordinate handling for our text positioning
        if os.getenv('DISPLAY_PHYSICAL_ROTATION', '180') == '180':
            image = image.rotate(180)
        
        # Smart refresh mode - full refresh only when needed
        if force_refresh or self._should_force_refresh():
            if preserve_border:
                # Border-preserving refresh: only refresh the content area, not the borders
                border_width = 40  # Match decorative border width
                content_area = (border_width, border_width, 
                               self.width - border_width, self.height - border_width)
                
                # Paste only the content area (excluding borders)
                content_image = image.crop(content_area)
                self.display_device.frame_buf.paste(content_image, content_area[:2])
                
                # Use partial refresh for faster updates when preserving borders
                self.display_device.draw_partial(DisplayModes.DU)
                self.partial_refresh_count += 1
                self.logger.debug("Border-preserving refresh (content area only)")
            else:
                # Full refresh for background changes or scheduled refreshes
                self.display_device.frame_buf.paste(image, (0, 0))
                self.display_device.draw_full(DisplayModes.GC16)
                self.last_full_refresh = time.time()
                self.partial_refresh_count = 0  # Reset counter after full refresh
                self.logger.debug("Full display refresh (background change or scheduled)")
        else:
            # Use partial refresh for regular verse updates (faster, preserves display longevity)
            self.display_device.frame_buf.paste(image, (0, 0))
            
            # Check if we should use partial or full refresh
            if self.partial_refresh_count < self.max_partial_refreshes:
                self.display_device.draw_partial(DisplayModes.DU)
                self.partial_refresh_count += 1
                self.logger.debug(f"Partial display refresh ({self.partial_refresh_count}/{self.max_partial_refreshes})")
            else:
                # Force full refresh to clear ghosting
                self.display_device.draw_full(DisplayModes.GC16)
                self.last_full_refresh = time.time()
                self.partial_refresh_count = 0
                self.logger.debug("Full display refresh (ghosting prevention)")
    
    def _should_force_refresh(self) -> bool:
        """Check if a full refresh is needed based on time interval or partial refresh count."""
        time_based = (time.time() - self.last_full_refresh) > (self.force_refresh_interval * 60)
        count_based = self.partial_refresh_count >= self.max_partial_refreshes
        
        if count_based:
            self.logger.info(f"Forcing refresh due to {self.partial_refresh_count} partial refreshes (ghosting prevention)")
        
        return time_based or count_based
    
    def _check_memory_usage(self):
        """Monitor memory usage and trigger garbage collection if needed."""
        memory_percent = psutil.virtual_memory().percent
        threshold = int(os.getenv('MEMORY_THRESHOLD', '80'))
        
        if memory_percent > threshold:
            import gc
            gc.collect()
            self.logger.warning(f"High memory usage ({memory_percent}%), garbage collection triggered")
    
    def clear_display(self):
        """Clear the display to white."""
        white_image = Image.new('L', (self.width, self.height), 255)
        self.display_image(white_image, force_refresh=True)
    
    def clear_ghosting(self):
        """Aggressive ghosting removal with multiple refresh cycles."""
        if self.simulation_mode:
            self.logger.info("Simulation mode - would clear ghosting")
            return
            
        try:
            self.logger.info("Starting aggressive ghosting removal")
            
            # Create full black then full white images
            black_image = Image.new('L', (self.width, self.height), 0)
            white_image = Image.new('L', (self.width, self.height), 255)
            
            # Multiple refresh cycles to remove ghosting
            for cycle in range(3):
                self.logger.info(f"Ghosting removal cycle {cycle + 1}/3")
                
                # Black refresh
                self.display_device.frame_buf.paste(black_image, (0, 0))
                self.display_device.draw_full(DisplayModes.GC16)
                time.sleep(1)
                
                # White refresh
                self.display_device.frame_buf.paste(white_image, (0, 0))
                self.display_device.draw_full(DisplayModes.GC16)
                time.sleep(1)
            
            self.last_full_refresh = time.time()
            self.partial_refresh_count = 0
            self.logger.info("Ghosting removal completed")
            
        except Exception as e:
            self.logger.error(f"Error during ghosting removal: {e}")
    
    def show_transient_message(self, state: str, message: str = None, duration: float = None):
        """Show a temporary message overlay on the display."""
        try:
            # Skip status messages if AI response is currently being displayed
            if self._ai_display_active and state not in ["restore", "ai_response_page"]:
                self.logger.debug(f"Skipping status message '{state}' - AI response active")
                return
                
            # Handle special restore state
            if state == "restore":
                self.logger.info("🔄 RESTORE STATE RECEIVED - Triggering display restoration to normal Bible verse")
                if self.restore_callback:
                    try:
                        self.logger.info("🔄 Calling restore callback...")
                        self.restore_callback()
                        self.logger.info("✅ Restore callback completed successfully")
                        return
                    except Exception as e:
                        self.logger.error(f"❌ Restore callback failed: {e}")
                # Fallback: just clear to trigger normal display
                self.logger.info("🔄 Using fallback clear display method")
                try:
                    self.clear_display()
                    self.logger.info("✅ Fallback clear display completed")
                except Exception as e:
                    self.logger.error(f"❌ Display restore clear failed: {e}")
                return
            
            # Handle paginated AI response pages
            if state == "ai_response_page":
                if message:
                    self._show_ai_response_page(message, duration or 15.0)
                return
            # Map voice states to display messages
            display_messages = {
                "wake_detected": "🎤 Listening...",
                "listening": "🎤 Listening...",
                "recording": "🎙️ Recording...",
                "processing": "💭 Processing...",
                "thinking": "🤔 Thinking...",
                "speaking": "🔊 Speaking...",
                "ready": "✅ Ready",
                "error": "❌ Error",
                "interrupted": "⏸️ Interrupted"
            }
            
            # Set state-specific durations if not provided
            if duration is None:
                state_durations = {
                    "speaking": 15.0,      # Longer for TTS - up to 15 seconds
                    "ai_response": 10.0,   # Longer for AI responses
                    "processing": 8.0,     # Longer for processing
                    "thinking": 5.0,       # Medium for thinking
                    "wake_detected": 3.0,  # Short for wake detection
                    "listening": 5.0,      # Medium for listening
                    "recording": 5.0,      # Medium for recording
                    "ready": 2.0,          # Short for ready state
                    "error": 4.0,          # Medium for errors
                    "interrupted": 2.0,    # Short for interruptions
                    "idle": 2.0            # Short for idle state
                }
                duration = state_durations.get(state, 2.0)  # Default 2 seconds
            
            # Get display text - prefer custom message when provided
            if message:
                display_text = message
            elif state == "ai_response":
                display_text = "AI Response"  # Fallback for AI responses without message
            else:
                display_text = display_messages.get(state, state)
            
            # Create a simple overlay image
            overlay = Image.new('L', (self.width, self.height), 255)  # white background
            draw = ImageDraw.Draw(overlay)
            
            # Use appropriate font size based on content type
            if state == "ai_response":
                # Smaller font for AI responses to fit more text
                font_size = 32
            else:
                # Larger font for status messages
                font_size = 48
                
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except:
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
                except:
                    font = ImageFont.load_default()
            
            # Handle text wrapping for AI responses
            if state == "ai_response":
                wrapped_lines = self._wrap_text_for_display(display_text, font, self.width - 60)
                display_text = "\n".join(wrapped_lines)
            
            # Calculate text size and position
            if "\n" in display_text:
                # Multi-line text
                lines = display_text.split("\n")
                line_heights = []
                max_width = 0
                for line in lines:
                    line_bbox = draw.textbbox((0, 0), line, font=font)
                    line_width = line_bbox[2] - line_bbox[0]
                    line_height = line_bbox[3] - line_bbox[1]
                    line_heights.append(line_height)
                    max_width = max(max_width, line_width)
                text_width = max_width
                text_height = sum(line_heights) + (len(lines) - 1) * 10  # 10px line spacing
            else:
                # Single line text
                text_bbox = draw.textbbox((0, 0), display_text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
            
            # Position based on display transforms: mirror=true + rotation=180 means we need bottom-right initially
            mirror_setting = os.getenv('DISPLAY_MIRROR', 'false').lower()
            rotation_setting = os.getenv('DISPLAY_PHYSICAL_ROTATION', '0')
            
            if mirror_setting == 'true' and rotation_setting == '180':
                # Position in bottom-right so after flip + 180° rotation it ends up top-left
                x = self.width - text_width - 30
                y = self.height - text_height - 30
            else:
                # Default position
                x, y = 30, 30
            
            # Check if we need to rotate the text itself
            if mirror_setting == 'true' and rotation_setting == '180':
                # Create a temporary image for the text with some padding
                text_padding = 20
                text_img_width = text_width + (text_padding * 2)
                text_img_height = text_height + (text_padding * 2)
                text_img = Image.new('L', (text_img_width, text_img_height), 255)
                text_draw = ImageDraw.Draw(text_img)
                
                # Draw text on temporary image
                text_draw.text((text_padding, text_padding), display_text, font=font, fill=0)
                
                # Rotate the text image 180 degrees
                text_img = text_img.rotate(180)
                
                # Draw white rectangle background with black border on main overlay
                draw.rectangle((x - 15, y - 15, x + text_width + 30, y + text_height + 30), 
                              fill=255, outline=0, width=4)
                
                # Paste the rotated text onto the overlay
                # Adjust position to account for the rotated text placement
                paste_x = x - text_padding
                paste_y = y - text_padding
                overlay.paste(text_img, (paste_x, paste_y))
            else:
                # Draw normally
                # Draw white rectangle background with black border
                draw.rectangle((x - 15, y - 15, x + text_width + 30, y + text_height + 30), 
                              fill=255, outline=0, width=4)
                
                # Draw text (handle multi-line for AI responses)
                if "\n" in display_text:
                    self._draw_multiline_text(draw, (x, y), display_text, font, fill=0)
                else:
                    draw.text((x, y), display_text, font=font, fill=0)
            
            # Display the overlay (transforms will be applied in _display_on_hardware)
            self.display_image(overlay, force_refresh=True)
            
            self.logger.info(f"Showing visual feedback: {state} -> {display_text}")
            
            # Start a timer to restore normal display (only for certain states)
            if state in ["wake_detected", "listening", "recording", "ready", "ai_response", "speaking", "idle"]:
                def restore_display():
                    time.sleep(duration)
                    # Force a display update to clear the message
                    self.logger.info("Visual feedback expired - restoring normal display")
                    # Use callback to restore display if available
                    if self.restore_callback:
                        try:
                            self.restore_callback()
                        except Exception as e:
                            self.logger.error(f"Failed to restore display after visual feedback: {e}")
                    else:
                        # Fallback: just clear with a white screen
                        try:
                            self.clear_display()
                        except Exception as e:
                            self.logger.error(f"Failed to clear display after visual feedback: {e}")
                
                timer_thread = threading.Thread(target=restore_display, daemon=True)
                timer_thread.start()
            
        except Exception as e:
            self.logger.error(f"Failed to show visual feedback: {e}")
    
    def _show_ai_response_page(self, text: str, duration: float = 15.0):
        """Show a paginated AI response with large, centered text and auto-pagination."""
        try:
            if not text:
                return
            
            # Split text into pages that fit on screen with large fonts
            pages = self._paginate_ai_response(text)
            total_duration = len(pages) * duration
            
            # Lock display to prevent interruptions during AI response
            self.lock_display(total_duration)
            
            self.logger.info(f"AI response split into {len(pages)} pages, display locked for {total_duration + 15} seconds")
            
            # Show pages sequentially
            self._show_ai_pages_sequence(pages, duration)
                
        except Exception as e:
            self.logger.error(f"Failed to show AI response page: {e}")
    
    def _paginate_ai_response(self, text: str) -> list:
        """Split AI response text into pages that fit with large fonts."""
        # Create a temporary image for measurement
        temp_image = Image.new('L', (self.width, self.height), 255)
        temp_draw = ImageDraw.Draw(temp_image)
        
        # Use large font for optimal readability
        font_size = 48  # Start with large font
        font = None
        
        # Try to get a good font
        for size in [font_size, 44, 40, 36, 32]:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
                font_size = size
                break
            except:
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
                    font_size = size
                    break
                except:
                    continue
        
        if not font:
            font = ImageFont.load_default()
            font_size = 20
        
        # Calculate usable area (accounting for header and margins) - very conservative
        margin = 100  # Very large margins to prevent cutoff
        header_height = 150  # Lots of space for "ChatGPT Response" header
        usable_width = self.width - (2 * margin)
        usable_height = self.height - header_height - (2 * margin)
        
        # Split into pages
        words = text.split()
        pages = []
        current_page = []
        
        for word in words:
            # Test adding this word
            test_text = ' '.join(current_page + [word])
            wrapped_lines = self._wrap_text_for_font(test_text, font, usable_width)
            test_height = len(wrapped_lines) * (font_size + 12)  # More generous line spacing
            
            if test_height <= usable_height:
                # Fits on current page
                current_page.append(word)
            else:
                # Start new page
                if current_page:
                    pages.append(' '.join(current_page))
                current_page = [word]
        
        # Add final page
        if current_page:
            pages.append(' '.join(current_page))
        
        return pages
    
    def _wrap_text_for_font(self, text: str, font, max_width: int) -> list:
        """Wrap text to fit within max_width using the given font."""
        words = text.split()
        lines = []
        current_line = []
        
        temp_draw = ImageDraw.Draw(Image.new('L', (100, 100), 255))
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = temp_draw.textbbox((0, 0), test_line, font=font)
            line_width = bbox[2] - bbox[0]
            
            if line_width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    def _show_ai_pages_sequence(self, pages: list, page_duration: float):
        """Show AI response pages in sequence with timing."""
        import threading
        
        def show_next_page(page_index):
            if page_index < len(pages):
                # Show current page
                self._display_ai_page(pages[page_index], page_index + 1, len(pages))
                
                # Schedule next page or restoration
                if page_index + 1 < len(pages):
                    # More pages to show
                    threading.Timer(page_duration, lambda: show_next_page(page_index + 1)).start()
                else:
                    # Last page - let the display lock timer handle restoration
                    pass
        
        # Start showing pages
        show_next_page(0)
    
    def _display_ai_page(self, page_text: str, page_num: int, total_pages: int):
        """Display a single page of AI response with large, centered text."""
        try:
            # Create clean background
            image = Image.new('L', (self.width, self.height), 255)
            draw = ImageDraw.Draw(image)
            
            # Use much larger font for better readability from distance
            font_size = 96  # Much larger for distance viewing
            font = None
            
            # Try to get the best available font - start larger
            for size in [font_size, 88, 80, 72, 64, 56, 48]:
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
                    font_size = size
                    break
                except:
                    try:
                        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
                        font_size = size
                        break
                    except:
                        continue
            
            if not font:
                font = ImageFont.load_default()
                font_size = 20
            
            # Draw header with larger font
            header_font_size = min(60, font_size)  # Larger header font
            header_font = None
            try:
                header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", header_font_size)
            except:
                header_font = font
            
            header_text = f"🤖 ChatGPT Response"
            if total_pages > 1:
                header_text += f" ({page_num}/{total_pages})"
            
            # Center header
            header_bbox = draw.textbbox((0, 0), header_text, font=header_font)
            header_width = header_bbox[2] - header_bbox[0]
            header_x = (self.width - header_width) // 2
            header_y = 30
            
            draw.text((header_x, header_y), header_text, font=header_font, fill=0)
            
            # Prepare main text with matching margins from pagination
            margin = 100  # Match pagination margin - very conservative
            content_y_start = header_y + (header_bbox[3] - header_bbox[1]) + 70
            content_width = self.width - (2 * margin)
            content_height = self.height - content_y_start - margin
            
            # Wrap text
            wrapped_lines = self._wrap_text_for_font(page_text, font, content_width)
            
            # Calculate total text height with matching spacing from pagination
            line_height = font_size + 12  # Match pagination line spacing
            total_text_height = len(wrapped_lines) * line_height
            
            # Center text vertically in available space
            text_y = content_y_start + max(0, (content_height - total_text_height) // 2)
            
            # Draw each line centered
            current_y = text_y
            for line in wrapped_lines:
                line_bbox = draw.textbbox((0, 0), line, font=font)
                line_width = line_bbox[2] - line_bbox[0]
                line_x = (self.width - line_width) // 2
                
                draw.text((line_x, current_y), line, font=font, fill=0)
                current_y += line_height
            
            # Apply only horizontal mirror transformation for AI responses
            # The physical rotation is handled by the hardware, we just need mirroring
            mirror_setting = os.getenv('DISPLAY_MIRROR', 'false').lower()
            
            if mirror_setting == 'true':
                image = image.transpose(Image.FLIP_LEFT_RIGHT)
            
            # Use direct hardware display to bypass additional transformations
            if self.simulation_mode:
                # Save simulation image (bypasses lock check since we call _simulate_display directly)
                simulation_path = 'current_display.png'
                image.save(simulation_path)
                self.logger.info(f"AI response simulated - image saved to {simulation_path}")
            else:
                # Direct hardware display without additional transformations
                self._display_ai_on_hardware_direct(image)
            self.logger.info(f"AI response page {page_num}/{total_pages} displayed (font size: {font_size})")
            
        except Exception as e:
            self.logger.error(f"Failed to display AI page: {e}")
    
    def _display_ai_on_hardware_direct(self, image: Image.Image):
        """Display AI response directly on hardware without additional transformations."""
        if not self.display_device:
            raise RuntimeError("Display device not initialized")
        
        # Clear frame buffer completely
        white_image = Image.new('L', (self.width, self.height), 255)
        for i in range(2):
            self.display_device.frame_buf.paste(white_image, (0, 0))
        
        # Paste the pre-transformed image
        self.display_device.frame_buf.paste(image, (0, 0))
        
        # Use full refresh for clean display
        self.display_device.draw_full(DisplayModes.GC16)
        self.last_full_refresh = time.time()
        self.partial_refresh_count = 0
        self.logger.debug("AI response displayed with direct hardware method")
    
    
    def _calculate_optimal_font_size(self, text: str, max_width: int, max_height: int) -> int:
        """Calculate optimal font size for text to fit within given dimensions while remaining readable."""
        # Start with a large font size and reduce until text fits
        max_font_size = 72  # Large for distance reading
        min_font_size = 24  # Minimum readable size
        
        for font_size in range(max_font_size, min_font_size - 1, -4):
            try:
                # Test with this font size
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except:
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
                except:
                    font = ImageFont.load_default()
                    return 24  # Fallback size
            
            # Wrap text and check if it fits
            wrapped_lines = self._wrap_text_for_display(text, font, max_width)
            
            # Check if the wrapped text fits within height
            line_height = font.getbbox("Ay")[3] - font.getbbox("Ay")[1] + 8  # Add spacing
            total_height = len(wrapped_lines) * line_height
            
            if total_height <= max_height:
                self.logger.info(f"Optimal font size calculated: {font_size}px for {len(wrapped_lines)} lines")
                return font_size
        
        # If nothing fits, return minimum size
        self.logger.warning(f"Text too long for optimal sizing, using minimum font size: {min_font_size}px")
        return min_font_size
    
    def _wrap_text_for_display(self, text: str, font, max_width: int) -> list:
        """Wrap text to fit within display width."""
        import textwrap
        
        # Calculate average character width
        sample_text = "W" * 10  # Use wide character for measurement
        sample_bbox = ImageDraw.Draw(Image.new('L', (100, 100))).textbbox((0, 0), sample_text, font=font)
        avg_char_width = (sample_bbox[2] - sample_bbox[0]) / len(sample_text)
        
        # Calculate approximate characters per line
        chars_per_line = int(max_width / avg_char_width) - 2  # Add buffer
        
        # Wrap text
        wrapped = textwrap.fill(text, width=max(chars_per_line, 20))  # Minimum 20 chars per line
        return wrapped.split('\n')
    
    def _draw_multiline_text(self, draw, position: tuple, text: str, font, fill=0):
        """Draw multi-line text on the display."""
        x, y = position
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line_y = y + (i * 40)  # 40px line spacing
            if line_y < self.height - 40:  # Don't draw beyond display bounds
                draw.text((x, line_y), line, font=font, fill=fill)
    
    def get_display_info(self) -> dict:
        """Get display information."""
        return {
            'width': self.width,
            'height': self.height,
            'rotation': self.rotation,
            'simulation_mode': self.simulation_mode,
            'last_refresh': self.last_full_refresh
        }