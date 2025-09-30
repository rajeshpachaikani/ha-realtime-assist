# Migration from Picovoice/Porcupine to OpenWakeWord

This document summarizes the changes made to replace Picovoice/Porcupine with OpenWakeWord for wake word detection.

## Files Changed

### Core Implementation
- **src/wake_word/openwakeword_detector.py** - NEW: Main OpenWakeWord detector implementation
- **src/wake_word/__init__.py** - Updated to export OpenWakeWordDetector instead of PorcupineDetector
- **src/main.py** - Updated imports and type hints to use OpenWakeWordDetector
- **src/config.py** - Updated WakeWordConfig class to support OpenWakeWord parameters

### Configuration
- **config/config.yaml** - Updated wake word configuration section for OpenWakeWord
- **.env.example** - Updated environment variables for OpenWakeWord configuration
- **config/models/README.md** - NEW: Documentation for OpenWakeWord model files
- **requirements.txt** - Replaced pvporcupine with openwakeword and onnxruntime

### Examples and Tools
- **examples/test_wake_word.py** - Updated to work with OpenWakeWord
- **tools/gain_calibration/wake_word_tester.py** - Updated imports for OpenWakeWord

## Files Removed
- **src/wake_word/porcupine_detector.py** - Deleted Porcupine implementation
- **config/wake_words/** - Removed entire directory and .ppn files

## Environment Variables

The following environment variables are now used for OpenWakeWord configuration:

- `OWW_MODEL_PATH` - Path to .onnx model file (required)
- `OWW_DETECTION_THRESHOLD` - Detection threshold 0.0-1.0 (default: 0.5)
- `OWW_VAD_THRESHOLD` - Voice activity detection threshold (default: 0.6)
- `OWW_PRE_ACTIVATION_BUFFER` - Pre-activation buffer in seconds (default: 1.5)

## Setup Instructions

1. **Install dependencies:**
   ```bash
   pip install openwakeword onnxruntime
   ```

2. **Download OpenWakeWord models:**
   - Visit: https://github.com/dscripka/openWakeWord
   - Download desired .onnx model files
   - Place them in `config/models/` directory

3. **Configure environment:**
   ```bash
   # Copy and edit .env file
   cp .env.example .env
   
   # Set the model path
   echo "OWW_MODEL_PATH=config/models/alexa_v0.1.onnx" >> .env
   ```

4. **Test the installation:**
   ```bash
   python examples/test_wake_word.py --installation
   ```

## Key Differences from Porcupine

### Advantages of OpenWakeWord:
- No API key required (fully offline)
- No network dependencies
- More customizable thresholds
- Open source with active community
- No libspeexdsp dependency

### Configuration Changes:
- Model files are .onnx instead of .ppn
- Threshold configuration via environment variables
- Models stored in `config/models/` instead of `config/wake_words/`
- No access key needed

### Technical Changes:
- Uses ONNX runtime for inference
- 16kHz sample rate (same as Porcupine)
- Float32 audio processing instead of Int16
- Different detection scoring system

## Testing

Run the test suite to verify the migration:

```bash
# Test installation
python examples/test_wake_word.py --installation

# Test available models
python examples/test_wake_word.py --models

# Interactive testing
python examples/test_wake_word.py --interactive
```

## Troubleshooting

1. **Model not found error:**
   - Ensure OWW_MODEL_PATH points to valid .onnx file
   - Check that model file exists in config/models/

2. **Import errors:**
   - Install dependencies: `pip install openwakeword onnxruntime`
   - For GPU support: `pip install onnxruntime-gpu`

3. **Detection issues:**
   - Adjust OWW_DETECTION_THRESHOLD (lower = more sensitive)
   - Check audio gain settings in config.yaml
   - Verify microphone is working properly