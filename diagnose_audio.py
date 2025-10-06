#!/usr/bin/env python3
"""
Audio system diagnostic script for ha-realtime-assist

Checks audio devices, system resources, and identifies potential issues
that could cause audio underflow or wake word detection problems.
"""

import sys
import platform
import subprocess
import os

def print_header(title):
    """Print a section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def run_command(cmd, description):
    """Run a shell command and return output"""
    print(f"{description}...")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"Error: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return "Command timed out"
    except Exception as e:
        return f"Error: {str(e)}"

def check_python_environment():
    """Check Python version and key packages"""
    print_header("Python Environment")
    
    print(f"Python version: {sys.version}")
    print(f"Platform: {platform.platform()}")
    print(f"Architecture: {platform.machine()}")
    
    # Check required packages
    print("\nRequired packages:")
    packages = [
        'sounddevice',
        'numpy',
        'scipy',
        'openwakeword',
        'asyncio'
    ]
    
    for package in packages:
        try:
            __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} (MISSING)")

def check_audio_devices():
    """Check available audio devices"""
    print_header("Audio Devices")
    
    try:
        import sounddevice as sd
        
        print("Input devices:")
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                default = " (DEFAULT)" if i == sd.default.device[0] else ""
                print(f"  [{i}] {device['name']}{default}")
                print(f"      Channels: {device['max_input_channels']}, "
                      f"Sample rate: {device['default_samplerate']} Hz")
        
        print("\nOutput devices:")
        for i, device in enumerate(devices):
            if device['max_output_channels'] > 0:
                default = " (DEFAULT)" if i == sd.default.device[1] else ""
                print(f"  [{i}] {device['name']}{default}")
                print(f"      Channels: {device['max_output_channels']}, "
                      f"Sample rate: {device['default_samplerate']} Hz")
    except ImportError:
        print("sounddevice not installed - cannot check audio devices")
    except Exception as e:
        print(f"Error checking audio devices: {e}")

def check_system_resources():
    """Check CPU, memory, and temperature"""
    print_header("System Resources")
    
    # CPU info
    if platform.system() == "Linux":
        cpu_info = run_command(
            "lscpu | grep 'Model name' | cut -d: -f2 | xargs",
            "CPU Model"
        )
        print(f"CPU: {cpu_info}")
        
        # CPU frequency
        freq = run_command(
            "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || echo 'N/A'",
            "CPU Frequency"
        )
        if freq != 'N/A':
            print(f"CPU Frequency: {int(freq)/1000:.0f} MHz")
        
        # Temperature (Raspberry Pi)
        temp = run_command(
            "vcgencmd measure_temp 2>/dev/null || sensors 2>/dev/null | grep -i temp | head -1",
            "Temperature"
        )
        if temp and 'Error' not in temp:
            print(f"Temperature: {temp}")
        
        # Throttling status (Raspberry Pi)
        throttle = run_command(
            "vcgencmd get_throttled 2>/dev/null",
            "Throttling Status"
        )
        if throttle and 'Error' not in throttle:
            print(f"Throttling: {throttle}")
            if "0x0" not in throttle:
                print("  ⚠️  WARNING: Throttling detected!")
    
    # Memory
    try:
        import psutil
        mem = psutil.virtual_memory()
        print(f"\nMemory: {mem.percent}% used ({mem.used/1024/1024/1024:.1f}GB / {mem.total/1024/1024/1024:.1f}GB)")
        if mem.percent > 85:
            print("  ⚠️  WARNING: High memory usage!")
    except ImportError:
        print("\npsutil not installed - cannot check memory")
    except Exception as e:
        print(f"\nError checking memory: {e}")

def check_audio_system():
    """Check ALSA/PulseAudio configuration"""
    print_header("Audio System")
    
    if platform.system() == "Linux":
        # Check for PulseAudio
        pulse = run_command(
            "pulseaudio --version 2>/dev/null",
            "PulseAudio"
        )
        if pulse and 'Error' not in pulse:
            print(f"PulseAudio: {pulse}")
        else:
            print("PulseAudio: Not running or not installed")
        
        # Check ALSA devices
        print("\nALSA Playback Devices:")
        alsa_playback = run_command(
            "aplay -l 2>/dev/null",
            "Listing playback devices"
        )
        if alsa_playback:
            print(alsa_playback)
        
        print("\nALSA Capture Devices:")
        alsa_capture = run_command(
            "arecord -l 2>/dev/null",
            "Listing capture devices"
        )
        if alsa_capture:
            print(alsa_capture)
        
        # Check for ALSA config
        if os.path.exists("/etc/asound.conf"):
            print("\n✓ Custom ALSA config found: /etc/asound.conf")
        else:
            print("\nℹ️  No custom ALSA config (/etc/asound.conf)")

def check_network():
    """Check network connectivity and latency"""
    print_header("Network")
    
    # Check OpenAI connectivity
    openai_ping = run_command(
        "ping -c 3 -W 2 api.openai.com 2>/dev/null | tail -1",
        "Ping to api.openai.com"
    )
    if openai_ping and 'Error' not in openai_ping:
        print(f"OpenAI latency: {openai_ping}")
        # Parse average latency
        if "avg" in openai_ping:
            try:
                avg_ms = float(openai_ping.split('/')[-3])
                if avg_ms > 100:
                    print("  ⚠️  WARNING: High latency (>100ms)")
            except:
                pass
    
    # Check connection type
    if platform.system() == "Linux":
        wifi = run_command(
            "iwconfig 2>/dev/null | grep -i 'SSID' | head -1",
            "WiFi Connection"
        )
        if wifi and 'Error' not in wifi and wifi.strip():
            print(f"Connection: WiFi - {wifi}")
            print("  ℹ️  Consider using wired Ethernet for better stability")
        else:
            print("Connection: Likely wired (Ethernet)")

def check_config_files():
    """Check configuration files"""
    print_header("Configuration")
    
    config_files = [
        'config/config.yaml',
        '.env',
        'config/models/alexa_v0.1.onnx'
    ]
    
    for config_file in config_files:
        if os.path.exists(config_file):
            size = os.path.getsize(config_file)
            print(f"✓ {config_file} ({size} bytes)")
        else:
            print(f"✗ {config_file} (MISSING)")

def print_recommendations():
    """Print recommendations based on findings"""
    print_header("Recommendations")
    
    print("""
1. Buffer Settings: Enhanced buffers have been configured (300ms/750ms/3s)
2. Latency: Using 200ms explicit latency for Raspberry Pi stability
3. Logging: Underflow messages are now at DEBUG level

If you still experience issues:
- Reduce sample_rate to 16000 Hz in config
- Use wired Ethernet connection
- Ensure adequate power supply (3A+ for RPi 4)
- Check CPU temperature and throttling
- Close unnecessary applications

For detailed troubleshooting, see: AUDIO_TROUBLESHOOTING.md
""")

def main():
    """Main diagnostic routine"""
    print("="*60)
    print("  HA Realtime Assist - Audio System Diagnostics")
    print("="*60)
    
    check_python_environment()
    check_audio_devices()
    check_system_resources()
    check_audio_system()
    check_network()
    check_config_files()
    print_recommendations()
    
    print("\nDiagnostics complete!")
    print("Save this output for troubleshooting if needed.\n")

if __name__ == "__main__":
    main()
