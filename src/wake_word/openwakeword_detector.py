"""
OpenWakeWord wake word detection implementation
"""
import asyncio
import numpy as np
import threading
from typing import Callable, Optional, List, Dict
from queue import Queue, Empty
import time
import os
import concurrent.futures

from config import WakeWordConfig
from utils.logger import get_logger

try:
    import openwakeword
    from openwakeword import Model
    OPENWAKEWORD_AVAILABLE = True
except ImportError:
    OPENWAKEWORD_AVAILABLE = False
    openwakeword = None
    Model = None


class OpenWakeWordDetector:
    """
    Wake word detection using OpenWakeWord
    """
    
    # Mapping from config names to OpenWakeWord model names
    MODEL_MAPPING = {
        # Built-in models available in OpenWakeWord
        'alexa': 'alexa_v0.1.onnx',
        'hey_mycroft': 'hey_mycroft_v0.1.onnx',
        'hey_jarvis': 'jarvis_v0.1.onnx',
        'computer': 'computer_v0.1.onnx',
        'hey_picovoice': 'hey_picovoice_v0.1.onnx',
        
        # Default fallback
        'jarvis': 'jarvis_v0.1.onnx',
        'mycroft': 'hey_mycroft_v0.1.onnx',
        'picovoice': 'hey_picovoice_v0.1.onnx',
    }
    
    def __init__(self, config: WakeWordConfig):
        self.config = config
        self.logger = None  # Will be initialized in start()
        
        if not OPENWAKEWORD_AVAILABLE:
            raise ImportError("OpenWakeWord not available. Install with: pip install openwakeword")
        
        # Audio parameters (OpenWakeWord requirements)
        self.sample_rate = 16000  # OpenWakeWord requires 16kHz
        self.frame_length = 1280  # 80ms frames (16000 * 0.08)
        
        # State
        self.is_running = False
        self.audio_queue = Queue()
        self.detection_thread = None
        self.oww_model = None
        
        # Detection callback
        self.detection_callback: Optional[Callable[[str, float], None]] = None
        
        # Cooldown management
        self.last_detection_time = 0
        
    def __del__(self):
        """Cleanup OpenWakeWord on object destruction"""
        if self.oww_model is not None:
            # OpenWakeWord doesn't require explicit cleanup
            pass
    
    def _get_model_names(self) -> List[str]:
        """Get list of model names based on config"""
        model = self.config.model.lower()
        
        # If a custom model path is specified
        if hasattr(self.config, 'model_path') and self.config.model_path:
            return [self.config.model_path]
        
        # For built-in models, return empty list to load all pre-trained models
        # OpenWakeWord will handle loading the default models automatically
        return []
    
    def _get_detection_threshold(self) -> float:
        """Get detection threshold based on sensitivity"""
        # OpenWakeWord uses prediction scores, typically between 0 and 1
        # Convert sensitivity (0.0-1.0) to threshold (lower threshold = more sensitive)
        return 1.0 - self.config.sensitivity
    
    async def start(self) -> None:
        """Start wake word detection"""
        if self.is_running:
            return
        
        if not OPENWAKEWORD_AVAILABLE:
            raise ImportError("OpenWakeWord not available")
        
        # Initialize logger after it's been set up
        self.logger = get_logger("OpenWakeWord")
        
        try:
            # Log initialization status
            self.logger.info("Starting OpenWakeWord wake word detector...")
            
            # Get model names
            model_names = self._get_model_names()
            self.logger.info(f"Loading models: {model_names}")
            
            # Initialize OpenWakeWord model
            self.oww_model = Model(
                wakeword_model_paths=model_names,
                enable_speex_noise_suppression=True
            )
            
            threshold = self._get_detection_threshold()
            self.logger.info(f"Detection threshold: {threshold}")
            self.logger.info(f"Cooldown: {self.config.cooldown}s")
            
            # Start detection thread
            self.is_running = True
            self.detection_thread = threading.Thread(
                target=self._detection_loop,
                daemon=True,
                name="OpenWakeWordDetection"
            )
            self.detection_thread.start()
            
            self.logger.info("OpenWakeWord detector started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start OpenWakeWord detector: {e}")
            self.is_running = False
            raise
    
    async def stop(self) -> None:
        """Stop wake word detection"""
        if not self.is_running:
            return
        
        self.logger.info("Stopping OpenWakeWord detector...")
        self.is_running = False
        
        # Wait for detection thread to finish
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=2.0)
        
        # Clear the audio queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except Empty:
                break
        
        self.logger.info("OpenWakeWord detector stopped")
    
    def process_audio(self, audio_data: bytes, input_sample_rate: int = 24000) -> int:
        """Process audio data for wake word detection (compatible with main app interface)
        
        Returns:
            int: Number of audio chunks processed (for activity tracking)
        """
        if not self.is_running:
            return 0
        
        try:
            # Convert bytes to numpy array
            audio_np = np.frombuffer(audio_data, dtype=np.int16)
            
            # Resample if needed (OpenWakeWord requires 16kHz)
            if input_sample_rate != self.sample_rate:
                # Simple downsampling (could be improved with proper resampling)
                step = input_sample_rate // self.sample_rate
                audio_np = audio_np[::step]
            
            # Process in chunks of frame_length
            chunks_processed = 0
            for i in range(0, len(audio_np), self.frame_length):
                chunk = audio_np[i:i + self.frame_length]
                if len(chunk) == self.frame_length:
                    self.process_audio_chunk(chunk)
                    chunks_processed += 1
                    
            return chunks_processed
                    
        except Exception as e:
            self.logger.error(f"Error processing audio: {e}")
            return 0
    
    def process_audio_chunk(self, audio_data: np.ndarray) -> None:
        """Process audio data chunk for wake word detection"""
        if not self.is_running:
            return
        
        try:
            # Add to queue for processing
            self.audio_queue.put(audio_data.copy())
        except Exception as e:
            self.logger.error(f"Error adding audio to queue: {e}")
    
    def reset_audio_buffers(self) -> None:
        """Reset audio buffers"""
        # Clear the audio queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except Empty:
                break
    
    def _detection_loop(self) -> None:
        """Main detection loop running in separate thread"""
        self.logger.debug("Detection loop started")
        
        try:
            while self.is_running:
                try:
                    # Get audio data from queue
                    audio_data = self.audio_queue.get(timeout=0.1)
                    
                    # Ensure audio is the right length and format
                    if len(audio_data) != self.frame_length:
                        continue
                    
                    # Process with OpenWakeWord
                    predictions = self.oww_model.predict(audio_data)
                    
                    # Check for detections
                    threshold = self._get_detection_threshold()
                    for model_name, score in predictions.items():
                        if score >= threshold:
                            self._handle_detection(model_name, score)
                    
                except Empty:
                    continue
                except Exception as e:
                    if self.is_running:  # Only log if we're still supposed to be running
                        self.logger.error(f"Error in detection loop: {e}")
                    break
                    
        except Exception as e:
            self.logger.error(f"Detection loop crashed: {e}")
        finally:
            self.logger.debug("Detection loop ended")
    
    def _handle_detection(self, model_name: str, score: float) -> None:
        """Handle wake word detection"""
        current_time = time.time()
        
        # Check cooldown
        if current_time - self.last_detection_time < self.config.cooldown:
            return
        
        # Only process detections for the configured model or if it matches expected patterns
        configured_model = self.config.model.lower()
        
        # Check if this detection matches our configured model
        if configured_model == 'jarvis' and model_name != 'hey_jarvis':
            return
        elif configured_model == 'alexa' and model_name != 'alexa':
            return  
        elif configured_model == 'hey_mycroft' and model_name != 'hey_mycroft':
            return
        elif configured_model not in ['jarvis', 'alexa', 'hey_mycroft'] and model_name not in ['hey_jarvis', 'alexa', 'hey_mycroft']:
            # For other models, accept any detection for now
            pass
        
        self.last_detection_time = current_time
        
        # Use a friendlier wake word name for display
        display_name = model_name.replace('hey_', '').replace('_', ' ')
        
        self.logger.info(f"Wake word detected: '{display_name}' (score: {score:.3f})")
        
        # Call detection callback if set
        if self.detection_callback:
            try:
                self.detection_callback(display_name, score)
            except Exception as e:
                self.logger.error(f"Error in detection callback: {e}")
    
    def set_detection_callback(self, callback: Callable[[str, float], None]) -> None:
        """Set callback function for wake word detection"""
        self.detection_callback = callback