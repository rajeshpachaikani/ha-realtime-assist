#!/usr/bin/env python3
"""
Quick test to verify OpenWakeWord integration
"""
import os
import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from wake_word.openwakeword_detector import OpenWakeWordDetector
from config import WakeWordConfig

async def test_basic_functionality():
    """Test basic OpenWakeWord functionality"""
    print("Testing OpenWakeWord basic functionality...")
    
    # Check if model file exists
    model_path = os.getenv('OWW_MODEL_PATH')
    if not model_path:
        print("ERROR: OWW_MODEL_PATH environment variable not set")
        return False
    
    if not os.path.exists(model_path):
        print(f"ERROR: Model file not found: {model_path}")
        return False
    
    print(f"Using model: {model_path}")
    
    try:
        # Create detector
        config = WakeWordConfig(model_path=model_path)
        detector = OpenWakeWordDetector(config)
        
        # Test initialization
        await detector.start()
        print("✓ Detector started successfully")
        
        # Test with dummy audio
        dummy_audio = np.zeros(1280 * 2, dtype=np.int16)  # 2 frames worth of audio
        detector.process_audio(dummy_audio.tobytes(), input_sample_rate=16000)
        print("✓ Audio processing works")
        
        # Stop detector
        await detector.stop()
        print("✓ Detector stopped successfully")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import asyncio
    
    success = asyncio.run(test_basic_functionality())
    if success:
        print("\n✅ All tests passed! OpenWakeWord integration is working.")
    else:
        print("\n❌ Tests failed. Check the error messages above.")
        sys.exit(1)