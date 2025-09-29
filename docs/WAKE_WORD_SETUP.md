# Wake Word Setup Guide

Configure wake word detection using OpenWakeWord for reliable hands-free activation.

## Overview

The assistant uses OpenWakeWord for wake word detection. OpenWakeWord offers:
- High accuracy with low false positive rates
- Built-in models that work out of the box
- Support for custom wake words
- Optimized for Raspberry Pi
- No API keys required - completely local

## Getting Started

### 1. No Setup Required

OpenWakeWord works out of the box with no API keys or registration required!

### 2. Basic Configuration

In `config/config.yaml`:

```yaml
wake_word:
  enabled: true
  model: "jarvis"       # Built-in model name
  sensitivity: 1.0      # 0.0-1.0 (1.0 = most sensitive)
```

## Built-in Models

OpenWakeWord includes these models without any downloads:

| Model | Example Phrase |
|-------|----------------|
| `jarvis` | "Jarvis" (default) |
| `alexa` | "Alexa" |
| `hey_mycroft` | "Hey Mycroft" |
| `computer` | "Computer" |
| `hey_picovoice` | "Hey Picovoice" |

**Note**: These are the main built-in models. Additional models can be downloaded or custom trained.

## Sensitivity Tuning

The sensitivity parameter controls how easily the wake word triggers:

- **1.0** (Maximum): Most sensitive, may have occasional false positives
- **0.5** (Balanced): Good balance for most environments
- **0.1** (Minimum): Requires very clear pronunciation

### Testing Sensitivity

```bash
# Activate virtual environment
source venv/bin/activate

# Test wake word detection
python examples/test_wake_word.py
```

Adjust sensitivity based on your environment:
- Quiet room: 0.3 - 0.5
- Normal environment: 0.5 - 0.7
- Noisy environment: 0.7 - 1.0

## Audio Configuration

## Audio Configuration

### Noise Suppression

OpenWakeWord includes built-in noise suppression:

```yaml
wake_word:
  enable_speex_noise_suppression: true  # Recommended for better accuracy
  inference_framework: "onnx"           # Faster than "tflite"
```

This helps reduce false positives in noisy environments.

### Audio Gain

Adjust the wake word audio gain if needed:

```yaml
wake_word:
  audio_gain: 1.0        # 1.0 = no change
  audio_gain_mode: "fixed"
```

- Increase if wake word is hard to trigger
- Decrease if you get false positives
- Start with 1.0 and adjust as needed

## Custom Wake Words

Want to use a different wake word? You can use custom OpenWakeWord models:

### Using Custom Models

1. Download or create a custom OpenWakeWord model (`.onnx` file)
2. Place the model file in the `config/wake_words/` directory:
   ```bash
   cp ~/Downloads/my_custom_model.onnx config/wake_words/
   ```

3. Update configuration:
   ```yaml
   wake_word:
     model_path: "config/wake_words/my_custom_model.onnx"
   ```

### Creating Custom Models

For creating custom models, refer to the [OpenWakeWord documentation](https://github.com/dscripka/openWakeWord) for training instructions.

### Examples

```yaml
# Using a custom model file
model_path: "config/wake_words/custom_jarvis.onnx"

# Or using built-in models
model: "jarvis"          # Built-in Jarvis model
model: "alexa"           # Built-in Alexa model
model: "hey_mycroft"     # Built-in Hey Mycroft model
```

### Important Notes

- Free tier custom models expire after 30 days
- You can create up to 3 custom wake words on free tier
- Files must have `.ppn` extension
- Place files in `config/wake_words/` directory only

## Troubleshooting

### Wake Word Not Detecting

1. **Check Access Key**:
   ```bash
   echo $PICOVOICE_ACCESS_KEY
   ```
   Ensure it's set in your `.env` file

2. **Verify Audio Input**:
   ```bash
   python examples/test_audio_devices.py
   ```

3. **Test with Maximum Sensitivity**:
   ```yaml
   sensitivity: 1.0
   audio_gain: 1.5
   ```

4. **Check Logs**:
   ```bash
   grep -i porcupine logs/assistant.log
   ```

### Too Many False Positives

1. **Reduce Sensitivity**:
   ```yaml
   sensitivity: 0.3
   ```

2. **Increase Cooldown**:
   ```yaml
   cooldown: 3.0  # Seconds between detections
   ```

3. **Try Different Keyword**:
   - Longer phrases work better
   - Unique sounds reduce false positives

### Platform-Specific Issues

#### Raspberry Pi
- Use keywords ending with `_raspberry-pi` for best performance
- Ensure you have sufficient CPU headroom
- Consider using a USB microphone for better quality

#### Access Key Errors
- "Invalid access key": Check key is correct and active
- "Exceeded quota": Free tier allows generous usage, check console
- "Unsupported platform": Ensure using correct platform-specific model

## Performance Optimization

### CPU Usage
- Porcupine uses ~5-10% CPU on Raspberry Pi 4
- Less on more powerful systems

### Memory Usage
- ~10MB per keyword
- Very efficient compared to alternatives

### Reduce Latency
```yaml
wake_word:
  vad_enabled: false  # Disable if not needed
```

## Best Practices

1. **Choose Distinctive Keywords**: Avoid common words in conversation
2. **Test in Your Environment**: What works in one room may not in another
3. **Consider Multiple Users**: Test with different voices
4. **Monitor Logs**: Check for false positives and missed detections
5. **Start Conservative**: Begin with lower sensitivity and increase as needed

## Example Configurations

### Living Room Assistant
```yaml
wake_word:
  model: "alexa"        # Familiar to family
  sensitivity: 0.7      # Balanced for normal conversation
  cooldown: 2.0
```

### Workshop Assistant
```yaml
wake_word:
  model: "computer"     # Clear, distinctive
  sensitivity: 0.9      # High for noisy environment
  audio_gain: 1.5       # Boost for distance
```

### Bedroom Assistant
```yaml
wake_word:
  model: "jarvis"       # Fun choice
  sensitivity: 0.4      # Low to avoid false triggers
  cooldown: 3.0         # Prevent accidental triggers
```

## Need Help?

- Check the [Troubleshooting Guide](TROUBLESHOOTING.md)
- Review [Audio Setup](AUDIO_SETUP.md) for microphone configuration
- Visit [OpenWakeWord Documentation](https://github.com/dscripka/openWakeWord) for advanced features