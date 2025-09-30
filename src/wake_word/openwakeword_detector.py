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
try:
    from scipy import signal
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

from config import WakeWordConfig
from utils.logger import get_logger

try:
    import openwakeword
    from openwakeword.model import Model
    OPENWAKEWORD_AVAILABLE = True
except ImportError:
    OPENWAKEWORD_AVAILABLE = False
    openwakeword = None
    Model = None


class OpenWakeWordDetector:
    """
    Wake word detection using OpenWakeWord
    """
    
    def __init__(self, config: WakeWordConfig):
        self.config = config
        self.logger = None  # Will be initialized in start()
        
        if not OPENWAKEWORD_AVAILABLE:
            raise ImportError("OpenWakeWord not available. Install with: pip install openwakeword")
        
        # Get model path from environment or config
        env_model_path = os.getenv('OWW_MODEL_PATH')
        config_model_path = getattr(config, 'model_path', None)
        
        self.model_path = env_model_path or config_model_path
        
        if self.model_path:
            # If it's just a filename, prepend the models directory path
            if not os.path.isabs(self.model_path) and not os.path.exists(self.model_path):
                models_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'models')
                models_dir = os.path.abspath(models_dir)
                original_path = self.model_path
                self.model_path = os.path.join(models_dir, self.model_path)
                # Debug: log path resolution
                if hasattr(self, 'logger') and self.logger:
                    self.logger.debug(f"Resolved model path '{original_path}' to '{self.model_path}'")
            
            # Make sure it's absolute path
            self.model_path = os.path.abspath(self.model_path)
        else:
            # Default model path
            self.model_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'models', 'alexa_v0.1.onnx')
            self.model_path = os.path.abspath(self.model_path)
        
        # Audio parameters (OpenWakeWord typically uses 16kHz)
        self.sample_rate = 16000  # OpenWakeWord standard sample rate
        self.frame_length = 1280  # 80ms at 16kHz (1280 samples) - standard OpenWakeWord chunk size
        
        # State
        self.is_running = False
        self.oww_model = None  # Type: Optional[Model]
        self.audio_queue = Queue()
        self.detection_callbacks = []
        
        # Audio buffer for accumulating samples
        self.audio_buffer = np.array([], dtype=np.int16)
        
        # Threading
        self.detection_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Detection parameters
        self.detection_threshold = float(os.getenv('OWW_DETECTION_THRESHOLD', '0.5'))
        self.detection_cooldown = config.cooldown
        # Initialize to negative cooldown to ensure first detection works
        self.last_detection_time = -self.detection_cooldown
        
        # Audio gain configuration from config
        self.audio_gain = config.audio_gain if hasattr(config, 'audio_gain') else 1.0
        
        # High-pass filter configuration
        self.highpass_filter_enabled = getattr(config, 'highpass_filter_enabled', False)
        self.highpass_filter_cutoff = getattr(config, 'highpass_filter_cutoff', 50.0)
        
        # VAD settings from environment
        self.vad_threshold = float(os.getenv('OWW_VAD_THRESHOLD', '0.6'))
        self.pre_activation_buffer_seconds = float(os.getenv('OWW_PRE_ACTIVATION_BUFFER', '1.5'))
        
    def __del__(self):
        """Cleanup OpenWakeWord on object destruction"""
        if hasattr(self, 'oww_model') and self.oww_model:
            try:
                self.oww_model = None
            except Exception:
                pass  # Ignore errors during cleanup
    
    async def start(self) -> None:
        """Start wake word detection"""
        # Initialize logger now that logging system is configured
        if self.logger is None:
            self.logger = get_logger("OpenWakeWordDetector")
        self.logger.debug("OpenWakeWordDetector.start() called")
        if self.is_running:
            self.logger.warning("Wake word detector already running")
            return
        
        # Clean up any existing model instance before starting
        if hasattr(self, 'oww_model') and self.oww_model:
            self.logger.warning("Found existing OpenWakeWord model - cleaning up before restart")
            try:
                self.oww_model = None
            except Exception as e:
                self.logger.error(f"Error cleaning up existing model: {e}")
            self.oww_model = None
        
        try:
            # Check model path
            if not self.model_path:
                raise ValueError("OpenWakeWord model path not specified. Set OWW_MODEL_PATH environment variable or config.model_path")
            
            if not os.path.exists(self.model_path):
                # Provide detailed error information
                models_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'models')
                models_dir = os.path.abspath(models_dir)
                
                self.logger.error(f"OpenWakeWord model file not found: {self.model_path}")
                self.logger.error(f"Models directory: {models_dir}")
                self.logger.error(f"Models directory exists: {os.path.exists(models_dir)}")
                
                if os.path.exists(models_dir):
                    available_models = [f for f in os.listdir(models_dir) if f.endswith('.onnx')]
                    if available_models:
                        self.logger.error(f"Available models in {models_dir}: {available_models}")
                    else:
                        self.logger.error(f"No .onnx model files found in {models_dir}")
                        self.logger.error("Download models from: https://github.com/dscripka/openWakeWord")
                
                raise ValueError(f"OpenWakeWord model file not found: {self.model_path}")
            
            # Log initialization status
            self.logger.info("Starting OpenWakeWord wake word detector...")
            self.logger.info(f"Model path: {self.model_path}")
            self.logger.info(f"Detection threshold: {self.detection_threshold}")
            self.logger.info(f"VAD threshold: {self.vad_threshold}")
            self.logger.debug(f"self.oww_model status before init: {self.oww_model is not None}")
            
            # Initialize OpenWakeWord only if it doesn't exist
            if not self.oww_model:
                self.logger.info("Creating OpenWakeWord model instance (this may take a moment)...")
                self.logger.debug("Starting OpenWakeWord initialization")
                
                # Create OpenWakeWord model in a separate thread to allow timeout
                loop = asyncio.get_event_loop()
                
                def create_model():
                    self.logger.debug("Inside create_model()")
                    self.logger.debug(f"Creating OpenWakeWord model from: {self.model_path}")
                    
                    # Initialize the model with correct parameters
                    # Use the exact parameter names from the API
                    model = Model(
                        wakeword_model_paths=[self.model_path],
                        enable_speex_noise_suppression=False,  # We don't want libspeexdsp
                        vad_threshold=self.vad_threshold
                    )
                    return model
                
                # Use ThreadPoolExecutor to run blocking call with timeout
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = loop.run_in_executor(executor, create_model)
                    try:
                        # Wait up to 30 seconds for initialization
                        self.logger.debug("Waiting for OpenWakeWord model creation...")
                        self.oww_model = await asyncio.wait_for(future, timeout=30.0)
                        self.logger.debug("OpenWakeWord model creation completed")
                    except asyncio.TimeoutError:
                        self.logger.error("OpenWakeWord initialization timed out after 30 seconds")
                        self.logger.error("This may indicate:")
                        self.logger.error("  - Invalid model file")
                        self.logger.error("  - Missing ONNX runtime dependencies")
                        self.logger.error("  - Incompatible model format")
                        raise TimeoutError("OpenWakeWord initialization timed out")
            else:
                self.logger.warning("OpenWakeWord already initialized - skipping creation")
                self.logger.debug("Skipping OpenWakeWord creation - already exists")
            
            # Log successful initialization
            self.logger.info("OpenWakeWord initialized successfully!")
            self.logger.info(f"Sample rate: {self.sample_rate}Hz")
            self.logger.info(f"Frame length: {self.frame_length} samples")
            
            # Model verification logging
            self.logger.debug("Model verification:")
            self.logger.debug(f"  Model path: {self.model_path}")
            self.logger.debug(f"  Detection threshold: {self.detection_threshold}")
            self.logger.debug(f"  Audio gain: {self.audio_gain}")
            
            # Start detection thread
            self.stop_event.clear()
            self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
            self.detection_thread.start()
            
            self.is_running = True
            self.logger.info("OpenWakeWord wake word detection thread started")
            
        except Exception as e:
            self.logger.error(f"Failed to start wake word detection: {e}")
            if "model" in str(e).lower():
                self.logger.error("Model loading failed!")
                self.logger.error(f"Please check that the model file exists: {self.model_path}")
                self.logger.error("Set OWW_MODEL_PATH environment variable to specify model location")
            elif isinstance(e, TimeoutError):
                self.logger.error("Check your model file and dependencies")
            raise
    
    async def stop(self) -> None:
        """Stop wake word detection"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Stop detection thread
        self.stop_event.set()
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=2.0)
        
        # Clear queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except Empty:
                break
        
        # Clear audio buffer
        self.audio_buffer = np.array([], dtype=np.int16)
        
        # Clean up OpenWakeWord model
        if self.oww_model:
            self.oww_model = None
        
        self.logger.info("OpenWakeWord wake word detection stopped")
    
    def add_detection_callback(self, callback: Callable[[str, float], None]) -> None:
        """
        Add callback for wake word detection
        
        Args:
            callback: Function to call when wake word detected (model_name, confidence)
        """
        self.detection_callbacks.append(callback)
    
    def remove_detection_callback(self, callback: Callable[[str, float], None]) -> None:
        """Remove detection callback"""
        if callback in self.detection_callbacks:
            self.detection_callbacks.remove(callback)
    
    def process_audio(self, audio_data: bytes, input_sample_rate: int = 24000) -> None:
        """
        Process audio data for wake word detection
        
        Args:
            audio_data: Audio data (PCM16 format)
            input_sample_rate: Sample rate of input audio (default 24000 for OpenAI)
        """
        if not self.is_running:
            return
        
        # Debug logging
        if not hasattr(self, '_process_counter'):
            self._process_counter = 0
            if self.logger:
                self.logger.info(f"Wake word detector receiving first audio - input_rate: {input_sample_rate}Hz, data: {len(audio_data)} bytes")
                self.logger.debug(f"Detection state: running={self.is_running}, queue_size={self.audio_queue.qsize()}")
        
        self._process_counter += 1
        
        try:
            # Convert bytes to numpy array (PCM16)
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Apply audio gain if configured (keep as int16)
            if self.audio_gain != 1.0:
                # Convert to float for gain calculation, then back to int16
                audio_float = audio_array.astype(np.float32) * self.audio_gain
                # Clip to prevent overflow and convert back to int16
                audio_array = np.clip(audio_float, -32768, 32767).astype(np.int16)
            
            # Apply high-pass filter if enabled
            if self.highpass_filter_enabled and SCIPY_AVAILABLE:
                try:
                    # Convert to float for filtering
                    audio_float = audio_array.astype(np.float32)
                    # Design high-pass filter
                    nyquist = input_sample_rate / 2
                    normalized_cutoff = self.highpass_filter_cutoff / nyquist
                    b, a = signal.butter(2, normalized_cutoff, btype='high')
                    audio_float = signal.filtfilt(b, a, audio_float)
                    # Convert back to int16
                    audio_array = np.clip(audio_float, -32768, 32767).astype(np.int16)
                except Exception as e:
                    if self.logger and self._process_counter % 100 == 1:
                        self.logger.warning(f"High-pass filter failed: {e}")
            
            # Resample if needed (OpenWakeWord expects 16kHz)
            if input_sample_rate != self.sample_rate:
                if SCIPY_AVAILABLE:
                    try:
                        # Convert to float for resampling
                        audio_float = audio_array.astype(np.float32)
                        # Use scipy for high-quality resampling
                        num_samples = int(len(audio_float) * self.sample_rate / input_sample_rate)
                        audio_float = signal.resample(audio_float, num_samples)
                        # Convert back to int16
                        audio_array = np.clip(audio_float, -32768, 32767).astype(np.int16)
                    except Exception as e:
                        if self.logger and self._process_counter % 100 == 1:
                            self.logger.warning(f"Scipy resampling failed, using linear interpolation: {e}")
                        # Fallback to linear interpolation
                        audio_float = audio_array.astype(np.float32)
                        original_indices = np.linspace(0, len(audio_float) - 1, len(audio_float))
                        target_length = int(len(audio_float) * self.sample_rate / input_sample_rate)
                        target_indices = np.linspace(0, len(audio_float) - 1, target_length)
                        audio_float = np.interp(target_indices, original_indices, audio_float)
                        audio_array = np.clip(audio_float, -32768, 32767).astype(np.int16)
                else:
                    # Use numpy linear interpolation as fallback
                    audio_float = audio_array.astype(np.float32)
                    original_indices = np.linspace(0, len(audio_float) - 1, len(audio_float))
                    target_length = int(len(audio_float) * self.sample_rate / input_sample_rate)
                    target_indices = np.linspace(0, len(audio_float) - 1, target_length)
                    audio_float = np.interp(target_indices, original_indices, audio_float)
                    audio_array = np.clip(audio_float, -32768, 32767).astype(np.int16)
                    if self._process_counter == 1:
                        if self.logger:
                            self.logger.debug("Using numpy.interp for resampling (install scipy for better quality)")
            
            # Add to buffer
            self.audio_buffer = np.concatenate([self.audio_buffer, audio_array])
            
            # Process complete frames
            frames_queued = 0
            while len(self.audio_buffer) >= self.frame_length:
                # Extract frame
                frame = self.audio_buffer[:self.frame_length]
                self.audio_buffer = self.audio_buffer[self.frame_length:]
                
                # Validate frame before queuing
                if len(frame) != self.frame_length:
                    self.logger.error(f"Extracted frame size mismatch! Expected {self.frame_length}, got {len(frame)}")
                    continue
                
                # Queue for processing
                self.audio_queue.put(frame, block=False)
                frames_queued += 1
                
                # Prevent queue from growing too large
                if self.audio_queue.qsize() > 100:
                    try:
                        self.audio_queue.get_nowait()  # Remove oldest frame
                    except Empty:
                        pass
            
            # Debug logging for first few chunks
            if self._process_counter <= 5:
                self.logger.debug(f"Audio processing #{self._process_counter}: "
                                f"input_len={len(audio_data)}, "
                                f"converted_len={len(audio_array)}, "
                                f"buffer_len={len(self.audio_buffer)}, "
                                f"frames_queued={frames_queued}")
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error processing audio: {e}")
    
    def _detection_loop(self) -> None:
        """Background thread for wake word detection"""
        self.logger.debug("OpenWakeWord detection thread started")
        self.logger.debug(f"OpenWakeWord detection loop started - listening for model: {self.model_path}")
        
        frames_processed = 0
        
        while not self.stop_event.is_set():
            try:
                # Get audio frame from queue
                try:
                    audio_frame = self.audio_queue.get(timeout=0.1)
                except Empty:
                    continue
                
                frames_processed += 1
                
                # Log processing activity
                if frames_processed == 1:
                    self.logger.info(f"Wake word detection started - first frame received, shape: {audio_frame.shape}, dtype: {audio_frame.dtype}")
                    frame_max = np.max(np.abs(audio_frame))
                    self.logger.debug(f"First frame max amplitude: {frame_max:.6f}")
                
                # Log frame info periodically
                if frames_processed % 200 == 0:
                    frame_max = np.max(np.abs(audio_frame))
                    self.logger.debug(f"Frame #{frames_processed} - size: {len(audio_frame)}, max amplitude: {frame_max:.6f}")
                
                # Process with OpenWakeWord
                try:
                    # Get prediction from model
                    prediction = self.oww_model.predict(audio_frame)
                    
                    # Check prediction buffer for detections
                    for model_name in self.oww_model.prediction_buffer.keys():
                        # Get the latest score from prediction buffer
                        scores = list(self.oww_model.prediction_buffer[model_name])
                        if scores:
                            latest_score = scores[-1]
                            
                            if latest_score >= self.detection_threshold:
                                # Log wake word detection
                                self.logger.info(f"OpenWakeWord wake word detected: {model_name} (score: {latest_score:.4f})")
                                
                                current_time = time.time()
                                time_since_last = current_time - self.last_detection_time
                                
                                # Debug logging for first detection
                                if self.last_detection_time < 0:
                                    self.logger.info(f"First wake word detection after startup - cooldown check will pass")
                                
                                self.logger.debug(f"Cooldown check: time_since_last={time_since_last:.2f}s, cooldown={self.detection_cooldown}s")
                                
                                # Check cooldown
                                if time_since_last >= self.detection_cooldown:
                                    self.logger.info(f"Wake word active: {model_name}")
                                    self.last_detection_time = current_time
                                    
                                    # Call detection callbacks
                                    self.logger.debug(f"Triggering {len(self.detection_callbacks)} detection callbacks")
                                    for callback in self.detection_callbacks:
                                        try:
                                            callback(model_name, latest_score)
                                            self.logger.debug("Callback executed successfully")
                                        except Exception as e:
                                            self.logger.error(f"Error in detection callback: {e}")
                                else:
                                    self.logger.debug(f"Wake word detected but in cooldown period ({time_since_last:.1f}s < {self.detection_cooldown}s)")
                    
                except Exception as e:
                    self.logger.error(f"OpenWakeWord process error: {e}")
                    continue
                
                # Log detection result periodically  
                if frames_processed % 50 == 0:
                    max_score = 0.0
                    if hasattr(self.oww_model, 'prediction_buffer'):
                        for model_name in self.oww_model.prediction_buffer.keys():
                            scores = list(self.oww_model.prediction_buffer[model_name])
                            if scores:
                                max_score = max(max_score, scores[-1])
                    self.logger.debug(f"OpenWakeWord process result: max_score={max_score:.4f} (threshold={self.detection_threshold})")
                
                # Log progress periodically
                if frames_processed % 100 == 0:
                    self.logger.debug(f"Processed {frames_processed} frames, queue size: {self.audio_queue.qsize()}")
                
            except Exception as e:
                self.logger.error(f"Error in detection loop: {e}")
        
        self.logger.debug("OpenWakeWord detection thread stopped")
    
    def get_available_models(self) -> list:
        """
        Get list of available wake word models
        
        Returns:
            List of available model names
        """
        models_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'models')
        models_dir = os.path.abspath(models_dir)
        
        if not os.path.exists(models_dir):
            return []
        
        model_files = []
        for file in os.listdir(models_dir):
            if file.endswith('.onnx'):
                model_files.append(file)
        
        return model_files
    
    def get_model_info(self) -> dict:
        """
        Get information about the current model
        
        Returns:
            Dictionary with model information
        """
        info = {
            'engine': 'openwakeword',
            'model_path': self.model_path,
            'detection_threshold': self.detection_threshold,
            'sample_rate': self.sample_rate,
            'frame_length': self.frame_length,
            'audio_buffer_size': len(self.audio_buffer) if hasattr(self, 'audio_buffer') else 0,
            'vad_threshold': self.vad_threshold,
            'model_loaded': self.oww_model is not None
        }
        
        return info
    
    def reset_audio_buffers(self) -> None:
        """
        Reset audio buffers
        
        OpenWakeWord handles its own internal buffers, so we just clear our accumulation buffer
        """
        self.audio_buffer = np.array([], dtype=np.int16)
        
        # Clear the queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except Empty:
                break
        
        self.logger.info("Audio buffers reset")
    
    @staticmethod
    def test_installation() -> bool:
        """
        Test if OpenWakeWord is properly installed
        
        Returns:
            True if installation is working, False otherwise
        """
        logger = get_logger("OpenWakeWordTest")
        
        try:
            import openwakeword
            from openwakeword import Model
            
            logger.info("Testing OpenWakeWord installation...")
            
            # Check if we have a model file
            model_path = os.getenv('OWW_MODEL_PATH')
            if not model_path or not os.path.exists(model_path):
                logger.error("OWW_MODEL_PATH environment variable not set or file not found")
                logger.error("Please set OWW_MODEL_PATH to point to your .onnx model file")
                return False
            
            # Try to create a simple instance
            try:
                model = Model(wakeword_models=[model_path], inference_framework='onnx')
                logger.info(f"OpenWakeWord model loaded successfully from: {model_path}")
                model = None  # Clean up
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                return False
            
            logger.info("OpenWakeWord installation test passed")
            return True
            
        except ImportError as e:
            logger.error(f"OpenWakeWord not installed: {e}")
            logger.error("Install with: pip install openwakeword")
            return False
        except Exception as e:
            logger.error(f"OpenWakeWord installation test failed: {e}")
            return False