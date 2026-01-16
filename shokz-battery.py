#!/usr/bin/env python3
"""
shokz-battery: Read Shokz headset information

This script reads battery level and device information from your Shokz headset
by parsing the logs from the Shokz Connect desktop app. The app queries the
headset via the Loop120 USB dongle using a proprietary TLV protocol.

Requirements:
- Shokz Connect app must be installed and running
- Headset must be connected via Loop120 USB dongle
- macOS (reads from ~/Library/Logs/Shokz)

Usage:
    python3 shokz-battery.py          # Show battery status
    python3 shokz-battery.py --json   # Output as JSON with all device info
    python3 shokz-battery.py --watch  # Continuously monitor

Author: Roel Van Gils (with Claude Code)
License: MIT
Repository: https://github.com/roelvangils/shokz-battery
"""

__version__ = "1.1.0"

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


# EQ mode mappings per model family
# Key is the headset type code from getConnectedHeadsetType
#
# Model codes (researched from Shokz documentation):
# - C102: OpenComm (original)
# - C110: OpenComm2 UC
# - C120: OpenComm2 2025 Upgrade
# - S661: OpenMove
# - S700: OpenSwim
# - S710: OpenSwim Pro
# - S803/S804: OpenRun
# - S810: OpenRun Pro
# - S811: OpenRun Pro Mini
# - S812: OpenRun Pro 2
# - T110: OpenFit
# - T310: OpenFit 2
# - T910: OpenFit Pro
#
# EQ mode variations by model family:
# - OpenComm series (C1xx): Standard, Vocal Booster (2 modes)
# - OpenMove (S661): Standard, Vocal Booster, Earplug (3 modes)
# - OpenRun (S803/S804): Standard, Vocal Booster (2 modes, toggle only)
# - OpenRun Pro (S810/S811): Standard, Vocal, Bass Boost, Treble Boost (4 modes)
# - OpenRun Pro 2 (S812): Standard, Vocal, Bass Boost, Treble Boost, Classic, Volume Boost (6 modes)
# - OpenFit Pro (T910): Standard, Vocal, Bass Boost, Treble Boost, Private (5 modes)

EQ_MODES_BY_MODEL = {
    # OpenComm series - 2 modes: Standard, Vocal Booster
    'C102': {0: "Standard", 2: "Vocal Booster"},
    'C110': {0: "Standard", 2: "Vocal Booster"},
    'C120': {0: "Standard", 2: "Vocal Booster"},

    # OpenMove - 3 modes: Standard, Vocal Booster, Earplug
    'S661': {0: "Standard", 1: "Vocal Booster", 2: "Earplug"},

    # OpenRun - 2 modes (simple toggle)
    'S803': {0: "Standard", 1: "Vocal Booster"},
    'S804': {0: "Standard", 1: "Vocal Booster"},

    # OpenRun Pro - 4 modes: Standard, Vocal, Bass Boost, Treble Boost
    'S810': {0: "Standard", 1: "Vocal", 2: "Bass Boost", 3: "Treble Boost"},
    'S811': {0: "Standard", 1: "Vocal", 2: "Bass Boost", 3: "Treble Boost"},

    # OpenRun Pro 2 - 6 modes (4 fixed + 2 custom)
    'S812': {0: "Standard", 1: "Vocal", 2: "Bass Boost", 3: "Treble Boost", 4: "Classic", 5: "Volume Boost"},

    # OpenFit Pro - 5 modes
    'T910': {0: "Standard", 1: "Vocal", 2: "Bass Boost", 3: "Treble Boost", 4: "Private"},

    # Default fallback - 4 standard modes
    'default': {0: "Standard", 1: "Vocal", 2: "Bass Boost", 3: "Treble Boost"},
}

# Model name lookup for friendly display
MODEL_NAMES = {
    'C102': "OpenComm",
    'C110': "OpenComm2 UC",
    'C120': "OpenComm2",
    'S661': "OpenMove",
    'S700': "OpenSwim",
    'S710': "OpenSwim Pro",
    'S803': "OpenRun",
    'S804': "OpenRun",
    'S810': "OpenRun Pro",
    'S811': "OpenRun Pro Mini",
    'S812': "OpenRun Pro 2",
    'T110': "OpenFit",
    'T310': "OpenFit 2",
    'T910': "OpenFit Pro",
}


def get_eq_mode_name(mode_id, headset_type):
    """Get EQ mode name based on model and mode ID."""
    modes = EQ_MODES_BY_MODEL.get(headset_type, EQ_MODES_BY_MODEL['default'])
    return modes.get(mode_id, f"Unknown ({mode_id})")


def get_model_name(headset_type):
    """Get friendly model name from type code."""
    return MODEL_NAMES.get(headset_type, headset_type)

# Voice language mapping
LANGUAGES = {
    0: "English",
    1: "Chinese",
    2: "Japanese",
    3: "Korean",
    4: "Spanish",
    5: "French",
    6: "German",
}

# Advertised talk time in hours (from Shokz spec)
ADVERTISED_TALK_TIME_HOURS = 16


def estimate_remaining_time(battery_percentage):
    """
    Calculate estimated remaining time based on advertised 16h talk time.
    Conservative estimate: subtract 1 hour and round to nearest 30 minutes.
    """
    if battery_percentage <= 0:
        return 0
    raw_minutes = (battery_percentage / 100) * ADVERTISED_TALK_TIME_HOURS * 60
    conservative_minutes = raw_minutes - 60  # Subtract 1 hour
    if conservative_minutes <= 0:
        return 0
    # Round to nearest 30 minutes
    return round(conservative_minutes / 30) * 30


def format_duration(minutes):
    """Format minutes as '2h 30m' or '45m'."""
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    if mins == 0:
        return f"{hours}h"
    return f"{hours}h {mins}m"


def get_audio_mode():
    """
    Detect current audio output/input device and mode.

    Returns dict with:
    - output_device: current output device name
    - input_device: current input device name
    - using_dongle: True if using Loop120 USB dongle
    - using_bluetooth_mic: True if using Bones Bluetooth mic (HFP mode = low quality)
    - audio_quality: 'high' (USB/A2DP) or 'low' (HFP with mic)
    - missing_tool: True if SwitchAudioSource is not installed
    """
    result = {
        'output_device': None,
        'input_device': None,
        'using_dongle': False,
        'using_bluetooth_mic': False,
        'audio_quality': None,
        'missing_tool': False,
    }

    try:
        # Check if SwitchAudioSource is available
        output = subprocess.run(
            ['SwitchAudioSource', '-c', '-t', 'output'],
            capture_output=True, text=True, timeout=5
        )
        if output.returncode == 0:
            result['output_device'] = output.stdout.strip()
            result['using_dongle'] = 'loop120' in result['output_device'].lower()

        input_result = subprocess.run(
            ['SwitchAudioSource', '-c', '-t', 'input'],
            capture_output=True, text=True, timeout=5
        )
        if input_result.returncode == 0:
            result['input_device'] = input_result.stdout.strip()
            result['using_bluetooth_mic'] = result['input_device'].lower() == 'bones'

        # Determine audio quality
        if result['using_dongle']:
            result['audio_quality'] = 'high'  # USB 48kHz
        elif result['output_device'] and 'bones' in result['output_device'].lower():
            if result['using_bluetooth_mic']:
                result['audio_quality'] = 'low'  # HFP 16kHz mono
            else:
                result['audio_quality'] = 'high'  # A2DP 44.1kHz stereo

    except subprocess.TimeoutExpired:
        pass
    except FileNotFoundError:
        result['missing_tool'] = True

    return result


def get_latest_log_dir():
    """Find the most recent Shokz log directory."""
    log_base = Path.home() / "Library/Logs/Shokz/LOG"
    if not log_base.exists():
        return None

    dirs = sorted(log_base.glob("20*"), reverse=True)
    return dirs[0] if dirs else None


def hex_to_ascii(hex_str, skip_first=0):
    """Convert hex to ASCII string, stopping at null bytes."""
    try:
        bytes_data = bytes.fromhex(hex_str)[skip_first:]
        null_idx = bytes_data.find(b'\x00')
        if null_idx > 0:
            bytes_data = bytes_data[:null_idx]
        return bytes_data.decode('ascii', errors='ignore')
    except (ValueError, IndexError):
        return None


def hex_to_mac(hex_str):
    """Convert hex to MAC address."""
    try:
        bytes_data = bytes.fromhex(hex_str)[:6]
        return ':'.join(f'{b:02X}' for b in bytes_data)
    except (ValueError, IndexError):
        return None


def parse_logs(log_dir):
    """Parse all relevant TLV data from Shokz Connect log files."""
    if not log_dir:
        return None

    log_files = list(log_dir.rglob("*"))
    log_files = [f for f in log_files if f.is_file()]

    # Store latest values for each data type
    data = {
        'battery': {'value': None, 'timestamp': None},
        'dongle_firmware': None,
        'dongle_mac': None,
        'headset_type': None,
        'headset_firmware': None,
        'multipoint_enabled': None,
        'multipoint_connections': None,
        'eq_mode_id': None,
        'eq_mode': None,
        'voice_language': None,
        'connected': None,
    }

    # Patterns for different TLV responses
    patterns = {
        'battery': r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}:\d{3})\].*getDeviceBatteryLevel.*tag2:8003.*value:([0-9A-Fa-f]+)',
        'dongle_firmware': r'getVersionInfo.*tag2:800A.*value:([0-9A-Fa-f]+)',
        'dongle_mac': r'getBluetoothAddress.*tag2:8001.*value:([0-9A-Fa-f]+)',
        'headset_type': r'getConnectedHeadsetType.*tag2:800C.*value:([0-9A-Fa-f]+)',
        'headset_firmware': r'getDeviceVersionName.*tag2:8002.*value:([0-9A-Fa-f]+)',
        'multipoint': r'getDeviceMutConn.*tag2:8010.*value:([0-9A-Fa-f]+)',
        'eq_mode': r'getHeadsetEQ.*tag2:8008.*value:([0-9A-Fa-f]+)',
        'language': r'getDeviceLanguage.*tag2:8006.*value:([0-9A-Fa-f]+)',
        'connection': r'getBluetoothConnectionStatus.*tag2:8009.*value:([0-9A-Fa-f]+)',
    }

    for log_file in log_files:
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Parse battery (with timestamp tracking)
            for match in re.finditer(patterns['battery'], content):
                timestamp_str = match.group(1)
                value_hex = match.group(2)
                try:
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S:%f')
                    if data['battery']['timestamp'] is None or timestamp > data['battery']['timestamp']:
                        data['battery'] = {'value': value_hex, 'timestamp': timestamp}
                except ValueError:
                    continue

            # Parse other values (just get latest occurrence)
            for key, pattern in patterns.items():
                if key == 'battery':
                    continue
                for match in re.finditer(pattern, content):
                    value = match.group(1)
                    if key == 'dongle_firmware':
                        data['dongle_firmware'] = hex_to_ascii(value)
                    elif key == 'dongle_mac':
                        data['dongle_mac'] = hex_to_mac(value)
                    elif key == 'headset_type':
                        decoded = hex_to_ascii(value)
                        if decoded and decoded != '\x00\x00\x00\x00':
                            data['headset_type'] = decoded
                    elif key == 'headset_firmware':
                        data['headset_firmware'] = hex_to_ascii(value, skip_first=1)
                    elif key == 'multipoint':
                        try:
                            bytes_data = bytes.fromhex(value)
                            data['multipoint_enabled'] = bytes_data[1] == 1
                            data['multipoint_connections'] = bytes_data[2]
                        except (ValueError, IndexError):
                            pass
                    elif key == 'eq_mode':
                        try:
                            bytes_data = bytes.fromhex(value)
                            data['eq_mode_id'] = bytes_data[1]
                        except (ValueError, IndexError):
                            pass
                    elif key == 'language':
                        try:
                            bytes_data = bytes.fromhex(value)
                            lang_id = bytes_data[0]
                            data['voice_language'] = LANGUAGES.get(lang_id, f"Unknown ({lang_id})")
                        except (ValueError, IndexError):
                            pass
                    elif key == 'connection':
                        try:
                            bytes_data = bytes.fromhex(value)
                            data['connected'] = bytes_data[0] == 1
                        except (ValueError, IndexError):
                            pass

        except (IOError, OSError):
            continue

    # Resolve EQ mode name based on headset type
    if data['eq_mode_id'] is not None:
        data['eq_mode'] = get_eq_mode_name(data['eq_mode_id'], data['headset_type'])

    return data


def decode_battery(hex_value):
    """
    Decode battery level from the hex response value.

    Response format: 0005FF00
    The Shokz Connect app displays battery in 10% increments.
    Formula: percentage = (level + 1) × 10, capped at 100%
    """
    try:
        value_bytes = bytes.fromhex(hex_value)

        if len(value_bytes) >= 2:
            level_indicator = value_bytes[1]
            percentage = min((level_indicator + 1) * 10, 100)

            if percentage >= 70:
                level_text = "High"
            elif percentage >= 40:
                level_text = "Medium"
            elif percentage >= 20:
                level_text = "Low"
            else:
                level_text = "Critical"

            return {
                'level_indicator': level_indicator,
                'percentage': percentage,
                'level_text': level_text,
            }
    except (ValueError, IndexError):
        pass

    return None


def format_output(data, as_json=False, verbose=False):
    """Format the output for display."""
    if not data or not data['battery']['value']:
        if as_json:
            return json.dumps({'success': False, 'error': 'No data found'}, indent=2)
        return "Error: No battery data found. Is Shokz Connect running?"

    battery = decode_battery(data['battery']['value'])
    audio = get_audio_mode()

    # Calculate estimated remaining time based on advertised talk time
    estimate_minutes = estimate_remaining_time(battery['percentage']) if battery else None

    if as_json:
        output = {
            'success': True,
            'timestamp': data['battery']['timestamp'].isoformat() if data['battery']['timestamp'] else None,
            'battery': {
                'percentage': battery['percentage'] if battery else None,
                'level_text': battery['level_text'] if battery else None,
                'level_indicator': battery['level_indicator'] if battery else None,
                'raw_value': data['battery']['value'],
                'estimated_remaining_minutes': estimate_minutes,
                'estimated_remaining_text': format_duration(estimate_minutes) if estimate_minutes else None,
            },
            'headset': {
                'type': data['headset_type'],
                'model_name': get_model_name(data['headset_type']) if data['headset_type'] else None,
                'firmware': data['headset_firmware'],
                'eq_mode': data['eq_mode'],
                'voice_language': data['voice_language'],
                'multipoint_enabled': data['multipoint_enabled'],
                'multipoint_connections': data['multipoint_connections'],
            },
            'dongle': {
                'firmware': data['dongle_firmware'],
                'mac_address': data['dongle_mac'],
            },
            'audio': {
                'output_device': audio['output_device'],
                'input_device': audio['input_device'],
                'using_dongle': audio['using_dongle'],
                'using_bluetooth_mic': audio['using_bluetooth_mic'],
                'quality': audio['audio_quality'],
            },
            'connected': data['connected'],
        }
        return json.dumps(output, indent=2)

    # ANSI color codes
    RESET = "\033[0m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    DIM = "\033[2m"

    # Plain text output
    lines = []

    if battery:
        # Create visual battery bar (10 segments for 0-100%)
        filled = battery['percentage'] // 10
        empty = 10 - filled

        # Color based on battery level
        if battery['percentage'] >= 70:
            bar_color = GREEN
        elif battery['percentage'] >= 40:
            bar_color = YELLOW
        else:
            bar_color = RED

        bar = f"{bar_color}{'■' * filled}{DIM}{'□' * empty}{RESET}"

        # Add estimate to battery line
        if estimate_minutes and estimate_minutes > 0:
            estimate_str = format_duration(estimate_minutes)
            lines.append(f"Battery: {bar} {battery['percentage']}% {DIM}(~{estimate_str} remaining){RESET}")
        else:
            lines.append(f"Battery: {bar} {battery['percentage']}%")
    else:
        lines.append(f"Battery: Unknown (raw: {data['battery']['value']})")

    # Show model, EQ mode, and audio quality in compact output
    info_parts = []
    if data['headset_type']:
        model_name = get_model_name(data['headset_type'])
        info_parts.append(f"{CYAN}{model_name}{RESET}")
    if data['eq_mode']:
        info_parts.append(f"EQ: {data['eq_mode']}")
    # Show audio mode/quality
    if audio['output_device']:
        if audio['using_dongle']:
            info_parts.append(f"{GREEN}USB 48kHz{RESET}")
        elif audio['using_bluetooth_mic']:
            info_parts.append(f"{RED}HFP 16kHz{RESET} (mic on)")
        elif 'bones' in audio['output_device'].lower():
            info_parts.append(f"{YELLOW}BT 44kHz{RESET}")
        else:
            # Not using Shokz for audio output
            info_parts.append(f"{DIM}Audio: inactive{RESET}")
    if info_parts:
        lines.append(" · ".join(info_parts))

    # Show hint if SwitchAudioSource is not installed
    if audio['missing_tool']:
        lines.append(f"{DIM}Tip: brew install switchaudio-osx for audio mode detection{RESET}")

    if data['battery']['timestamp']:
        lines.append(f"{DIM}Updated: {data['battery']['timestamp'].strftime('%H:%M:%S')}{RESET}")

    if verbose:
        lines.append("")
        lines.append("Headset:")
        if data['headset_type']:
            model_name = get_model_name(data['headset_type'])
            if model_name != data['headset_type']:
                lines.append(f"  Model: {model_name} ({data['headset_type']})")
            else:
                lines.append(f"  Model: {data['headset_type']}")
        if data['headset_firmware']:
            lines.append(f"  Firmware: {data['headset_firmware']}")
        if data['eq_mode']:
            lines.append(f"  EQ Mode: {data['eq_mode']}")
        if data['voice_language']:
            lines.append(f"  Voice: {data['voice_language']}")
        if data['multipoint_enabled'] is not None:
            status = "Enabled" if data['multipoint_enabled'] else "Disabled"
            if data['multipoint_connections']:
                status += f" ({data['multipoint_connections']} connected)"
            lines.append(f"  Multipoint: {status}")

        lines.append("")
        lines.append("Dongle:")
        if data['dongle_firmware']:
            lines.append(f"  Firmware: {data['dongle_firmware']}")
        if data['dongle_mac']:
            lines.append(f"  MAC: {data['dongle_mac']}")

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Read Shokz headset battery and device information',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s              Show current battery status
  %(prog)s -v           Show battery + device info
  %(prog)s --json       Output all info as JSON
  %(prog)s --watch      Continuously monitor battery
  %(prog)s --raw        Show raw battery hex value only
        '''
    )
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--raw', action='store_true', help='Output raw hex value only')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed device info')
    parser.add_argument('--watch', action='store_true', help='Continuously monitor (every 30s)')
    parser.add_argument('--watch-interval', type=int, default=30,
                        help='Watch interval in seconds (default: 30)')

    args = parser.parse_args()

    log_dir = get_latest_log_dir()
    if not log_dir:
        print("Error: Shokz Connect logs not found.", file=sys.stderr)
        print("", file=sys.stderr)
        print("To use this utility, make sure the Shokz Connect app is installed.", file=sys.stderr)
        print("You can get it here: https://pro.shokz.com/pages/shokz-connect", file=sys.stderr)
        return 1

    def get_and_print():
        data = parse_logs(log_dir)

        if args.raw:
            if data and data['battery']['value']:
                print(data['battery']['value'])
            else:
                print("ERROR", file=sys.stderr)
                return 1
        else:
            print(format_output(data, as_json=args.json, verbose=args.verbose))

        return 0 if (data and data['battery']['value']) else 1

    if args.watch:
        try:
            while True:
                os.system('clear' if os.name != 'nt' else 'cls')
                print(f"Shokz Battery Monitor (updating every {args.watch_interval}s)")
                print("=" * 40)
                get_and_print()
                print("\nPress Ctrl+C to exit")
                time.sleep(args.watch_interval)
        except KeyboardInterrupt:
            print("\nExiting...")
            return 0
    else:
        return get_and_print()


if __name__ == "__main__":
    sys.exit(main())
