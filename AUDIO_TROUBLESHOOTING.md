# Audio Troubleshooting Guide

## Audio Output Underflow Issues

### What is "output underflow"?

An "output underflow" occurs when the audio playback buffer runs empty before new audio data arrives. This causes:
- Audio glitches or stuttering
- Potential interference with audio input/wake word detection
- Degraded user experience

### Recent Fixes Applied

The following improvements have been made to prevent audio underflows on Raspberry Pi:

1. **Increased Buffer Sizes**
   - Minimum buffer: 200ms → 300ms
   - Target buffer: 500ms → 750ms
   - Maximum buffer: 2s → 3s
   - Queue size: 150 → 200 items

2. **Improved Latency Settings**
   - Explicit 200ms latency for both input and output streams
   - More aggressive pre-buffering (750ms before playback starts)

3. **Reduced Logging Noise**
   - Output underflow warnings now logged at DEBUG level instead of WARNING
   - Reduces console spam while still allowing diagnostics if needed

### Verification

After applying these fixes, you should see:
- Fewer or no "output underflow" messages
- More stable wake word detection
- Smoother audio playback

### If Issues Persist

If you still experience audio underflow issues, try the following:

#### 1. Check CPU Usage
```bash
# Monitor CPU while running
top -d 1
```

If CPU usage is consistently high (>80%), consider:
- Closing other applications
- Reducing OpenAI model complexity
- Using a more powerful Raspberry Pi model

#### 2. Check Network Latency
```bash
# Test network latency to OpenAI
ping api.openai.com
```

High network latency (>100ms) can cause audio delays. Consider:
- Using a wired Ethernet connection instead of WiFi
- Improving WiFi signal strength
- Checking for network congestion

#### 3. Adjust Audio Configuration

Edit your config file (`config/config.yaml`) and try:

```yaml
audio:
  sample_rate: 16000  # Lower sample rate for less CPU load
  chunk_size: 2048    # Larger chunks for less frequent processing
  input_volume: 1.0
  output_volume: 0.8  # Slightly lower volume to prevent clipping
```

#### 4. Enable Debug Logging

To see detailed audio buffer status, set logging level to DEBUG:

```yaml
logging:
  level: DEBUG
  file: logs/assistant.log
```

Then check the logs for patterns:
```bash
grep "Audio callback status" logs/assistant.log
grep "buffer" logs/assistant.log
```

#### 5. Test Audio Devices

List available audio devices:
```bash
python3 -c "import sounddevice as sd; print(sd.query_devices())"
```

Try different output devices by changing the `output_device` setting:
```yaml
audio:
  output_device: "default"  # or specific device index
```

#### 6. System-Level Optimizations

**ALSA Configuration** (create/edit `/etc/asound.conf`):
```
pcm.!default {
    type plug
    slave {
        pcm "hw:0,0"
        rate 48000
        period_size 2048
        buffer_size 16384
    }
}
```

**Increase Audio Thread Priority**:
```bash
# Add to /etc/security/limits.conf
@audio - rtprio 95
@audio - memlock unlimited
```

**Disable PulseAudio Power Saving** (if using PulseAudio):
```bash
# Edit /etc/pulse/default.pa
# Add or uncomment:
load-module module-suspend-on-idle timeout=0
```

#### 7. Hardware Considerations

- Use a good quality USB audio interface if built-in audio is problematic
- Ensure adequate power supply (3A+ for Raspberry Pi 4)
- Use a heatsink or active cooling to prevent thermal throttling
- Use a high-quality SD card (Class 10 or better)

### Diagnostic Commands

```bash
# Check audio system status
aplay -l
arecord -l

# Test audio playback
speaker-test -t wav -c 2

# Monitor system resources
htop

# Check for throttling (Raspberry Pi)
vcgencmd get_throttled

# Check temperature
vcgencmd measure_temp
```

### Understanding Buffer Behavior

The audio system uses three buffer levels:

1. **Minimum Buffer (300ms)**: Critical threshold - underruns likely if below this
2. **Target Buffer (750ms)**: Optimal level for smooth playback
3. **Maximum Buffer (3s)**: Prevents memory issues from excessive buffering

The system tries to maintain the buffer at the target level, but network delays or CPU spikes can cause temporary drops.

### Common Scenarios

**Scenario 1: Underflows at Start of Playback**
- This is normal - the system pre-buffers 750ms before playing
- Should not affect wake word detection

**Scenario 2: Random Underflows During Playback**
- Usually caused by network delays from OpenAI
- Fixed by increased buffer sizes and higher latency tolerance

**Scenario 3: Continuous Underflows**
- Indicates systematic problem (CPU, network, or hardware)
- Follow troubleshooting steps above

### Contact & Support

If issues persist after trying these steps, please provide:
- Raspberry Pi model and OS version
- Network connection type (WiFi/Ethernet)
- Log excerpts showing the issue
- Output of diagnostic commands
