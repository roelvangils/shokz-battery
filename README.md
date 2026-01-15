# shokz-battery

A command-line tool to check your Shokz headset battery level and device information on macOS.

```
Battery: ■■■■■■□□□□ 60% (~8h 30m remaining)
OpenComm2 · EQ: Vocal Booster · USB 48kHz
Updated: 16:55:56
```

## Installation

### Using Homebrew (recommended)

```bash
brew install roelvangils/tap/shokz-battery
```

### Manual installation

```bash
curl -o /usr/local/bin/shokz-battery https://raw.githubusercontent.com/roelvangils/shokz-battery/main/shokz-battery.py
chmod +x /usr/local/bin/shokz-battery
```

## Requirements

- **macOS** (reads from `~/Library/Logs/Shokz`)
- **[Shokz Connect](https://pro.shokz.com/pages/shokz-connect)** app must be installed and running
- **Loop120 USB dongle** (comes with OpenComm2 and other UC models)

Optional: Install `switchaudio-osx` for audio mode detection:
```bash
brew install switchaudio-osx
```

## Usage

```bash
# Show battery status
shokz-battery

# Show detailed device info
shokz-battery -v

# Output as JSON (for scripts/automation)
shokz-battery --json

# Continuously monitor (updates every 30s)
shokz-battery --watch

# Custom update interval
shokz-battery --watch --watch-interval 10
```

## Features

- **Battery level** with visual bar and estimated remaining time
- **Audio mode detection** - Shows whether you're using USB (48kHz), Bluetooth A2DP (44kHz), or HFP (16kHz with mic)
- **Device info** - Model, firmware version, EQ mode, voice language, multipoint status
- **JSON output** - Perfect for scripting, automation, or integration with other tools
- **Watch mode** - Continuously monitor your headset

## Supported Devices

| Model | Code | EQ Modes |
|-------|------|----------|
| OpenComm | C102 | Standard, Vocal Booster |
| OpenComm2 UC | C110 | Standard, Vocal Booster |
| OpenComm2 | C120 | Standard, Vocal Booster |
| OpenMove | S661 | Standard, Vocal Booster, Earplug |
| OpenRun | S803/S804 | Standard, Vocal Booster |
| OpenRun Pro | S810 | Standard, Vocal, Bass Boost, Treble Boost |
| OpenRun Pro Mini | S811 | Standard, Vocal, Bass Boost, Treble Boost |
| OpenRun Pro 2 | S812 | Standard, Vocal, Bass Boost, Treble Boost, Classic, Volume Boost |
| OpenFit | T110 | - |
| OpenFit 2 | T310 | - |
| OpenFit Pro | T910 | Standard, Vocal, Bass Boost, Treble Boost, Private |

> **Note:** This tool requires the Loop120 USB dongle. Bluetooth-only connections are not supported for battery reading.

## How It Works

The Shokz Connect desktop app communicates with your headset via the Loop120 USB dongle using a proprietary TLV (Tag-Length-Value) protocol. The app logs all device queries to `~/Library/Logs/Shokz/LOG/`.

This tool parses those logs to extract:
- Battery level (reported in 10% increments)
- Headset model and firmware
- EQ mode and voice language settings
- Multipoint connection status
- Dongle firmware and MAC address

## JSON Output Example

```json
{
  "success": true,
  "battery": {
    "percentage": 60,
    "level_text": "Medium",
    "estimated_remaining_minutes": 510,
    "estimated_remaining_text": "8h 30m"
  },
  "headset": {
    "type": "C120",
    "model_name": "OpenComm2",
    "firmware": "HC_HU_T_01_20240902",
    "eq_mode": "Vocal Booster"
  },
  "audio": {
    "output_device": "Loop120 by Shokz",
    "using_dongle": true,
    "quality": "high"
  }
}
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

Created by [Roel Van Gils](https://github.com/roelvangils) with [Claude Code](https://claude.ai/code).

## Disclaimer

This project is not affiliated with Shokz. For official product information, visit [shokz.com](https://shokz.com).
