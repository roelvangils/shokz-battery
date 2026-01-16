# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-01-16

### Added
- Compact mode (`--compact`) for single-line output, ideal for menu bar apps like xbar/SwiftBar

## [1.1.0] - 2026-01-16

### Added
- CHANGELOG.md for tracking version history
- Changelog page on GitHub Pages (docs/changelog.html)
- Changelog section on main documentation page
- `/release` Claude skill for automated version releases

## [1.0.0] - 2025-01-15

### Added
- Initial release of shokz-battery
- Battery level display with visual bar and estimated remaining time
- Audio mode detection (USB 48kHz, Bluetooth 44kHz, HFP 16kHz)
- Device information: model, firmware, EQ mode, voice language, multipoint status
- JSON output for scripting and automation (`--json`)
- Watch mode for continuous monitoring (`--watch`)
- Verbose mode for detailed device info (`-v`)
- Raw output mode (`--raw`)
- Support for all Shokz headsets using Loop120 USB dongle:
  - OpenComm / OpenComm2 / OpenComm2 UC
  - OpenRun / OpenRun Pro / OpenRun Pro 2 / OpenRun Pro Mini
  - OpenMove
  - OpenFit / OpenFit 2 / OpenFit Pro
  - OpenSwim / OpenSwim Pro
- Homebrew installation via `brew install roelvangils/tap/shokz-battery`
- GitHub Pages documentation site

[1.2.0]: https://github.com/roelvangils/shokz-battery/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/roelvangils/shokz-battery/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/roelvangils/shokz-battery/releases/tag/v1.0.0
