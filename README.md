# CAN-based Smart Parking CPS

A  Cyber-Physical System (CPS) for smart parking built around a Controller Area Network (CAN) connecting sensors and actuators, with a host-side CAN Intrusion Detection System (IDS), and two attack suites for security evaluation: image-space adversarial attacks against ANPR and CAN-bus attacks.

This repository consolidates embedded firmware (sensors/actuators), a PIC32MZ gateway, IDS logic, attack tooling, and test utilities to support experiments in detection performance, robustness, and end-to-end behavior.

## Architecture Diagram
The arquitecture diagram is as follows:

<img src="figures/SecCPS_Arquitecture.drawio.svg" alt="CAN-based Smart Parking CPS architecture" width="800">

## Repository Structure

- [industrialNetwork](industrialNetwork/README.md): Embedded sketches and host utilities for the CPS industrial network
	- Sensors/actuators (Arduino sketches):
		- [ambient_transmitter](industrialNetwork/ambient_transmitter/ambient_transmitter.ino)
		- [ultrasonic](industrialNetwork/ultrasonic/ultrasonic.ino)
		- [servoMotor](industrialNetwork/servoMotor/servoMotor.ino)
		- [transmitterCAN](industrialNetwork/transmitterCAN/transmitterCAN.ino)
		- [recieverCAN](industrialNetwork/recieverCAN/recieverCAN.ino)
	- Gateway: [PIC32MZ/original.c](industrialNetwork/PIC32MZ/original.c)
	- CAN IDS: [NIDS_CAN/main.py](industrialNetwork/NIDS_CAN/main.py)
- Attacks
	- ANPR adversarial: [attacks/adversarialANPR](attacks/adversarialANPR/README.md)
	- CAN bus attacks: [attacks/CANbus](attacks/CANbus/README.md)
- Tests and utilities: [tests](tests/README.md)

## System Overview

The CPS consists of CAN-connected devices providing occupancy detection (ultrasonic), ambient sensing, and a barrier actuator (servo). A PIC32MZ gateway/bridge connects the CAN segment upstream. A host-side IDS observes CAN traffic to detect anomalies such as ID misuse, payload irregularities, and flooding. Two attack suites are provided to evaluate defenses:

- Adversarial ANPR attacks: image-space perturbations to degrade plate detection/OCR in the perception pipeline.
- CAN bus attacks: flooding, fuzzing, spoofing, and replay to probe CAN IDS detection.

High-level data path: Sensors/Actuators ⇄ CAN Bus ⇄ PIC32MZ Gateway ⇄ Host (IDS, logging, analytics) and Video ⇄ ANPR ⇄ Attack evaluation.

## Hardware & Interfaces

- CAN transceivers/shields for Arduino-compatible boards (for the included sketches).
- PIC32MZ-based gateway (see [industrialNetwork/PIC32MZ/original.c](industrialNetwork/PIC32MZ/original.c)).
- Host CAN adapter:
	- Linux: SocketCAN-compatible (e.g., USB-CAN) on `can0`/`vcan0`.
	- Windows: Vendor adapters (Peak PCAN, Kvaser) supported via `python-can`.

## Threat Model
The proposed threat model is shown in the next Figure. Attacker (1) refers to CAN-bus threats considered. Attacker (2) refers to ANPR threats considered.
<img src="figures/Adversarial_SecCPS_Arquitecture.drawio.svg" alt="CAN-based Smart Parking CPS architecture" width="800">

## Software Components

### Industrial Network & IDS

- Device firmware and utility sketches in [industrialNetwork](industrialNetwork/README.md) implement periodic sensing and actuation with simple CAN message formats.
- The host-side IDS at [industrialNetwork/NIDS_CAN/main.py](industrialNetwork/NIDS_CAN/main.py) ingests CAN frames via `python-can`, learns a baseline, and detects anomalies:
	- Unknown IDs, DLC mismatches
	- Payload/range deviations for configured sensors
	- Rate-based DoS/flooding
	- Payload pattern deviation
- Outputs: SQLite `can_ids.db` (messages, anomalies), console logs, `intrusions.log`, and optional MQTT alerts.

Key tunables: `window_size`, `frequency_threshold`, `anomaly_threshold`, and `sensor_ranges` mappings (see the IDS source).

### Attacks

- ANPR adversarial (vision): see [attacks/adversarialANPR/README.md](attacks/adversarialANPR/README.md) for full documentation on the three attacks implemented:
	- Detection DoS via bounded perturbations
	- Targeted region transfer
	- Imperceptible OCR manipulation

- CAN bus attacks: see [attacks/CANbus](attacks/CANbus/README.md) for a Python CLI using `python-can` implementing:
	- Flood (DoS) with configurable ID/rate/payload
	- Fuzzing over ID/DLC/payload ranges
	- Spoof injection for a target ID
	- Replay from CSV/candump logs

All sent frames are logged for reproducibility.

## CAN Message Specification (Summary)

Device-level message formats are defined in [industrialNetwork/README.md](industrialNetwork/README.md). Example for temperature:

- ID range: 0x400–0x500
- Payload: 2 bytes, big-endian; value scaled as `°C × 100`
- Example: 85.31°C → 8531 → 0x2152 (MSB=0x21, LSB=0x52)
- Example frame: `423#022152` for ID 0x423

Similar conventions apply to air quality, gas, and ultrasonic occupancy. The barrier (servo) periodically reports state via ID+state.

Note: The IDS currently validates coarse ranges; if using multi-byte encodings, extend parsing logic accordingly (see `_detect_anomalies` in the IDS).

## Quick Start

### 1) Python Environment

Install core packages for IDS and CAN tooling:

```bash
pip install python-can numpy paho-mqtt
```

For ANPR experiments, install notebook requirements (see the ANPR README for details):

```bash
pip install -r attacks/adversarialANPR/requirements.txt
```

### 2) CAN Interface

- Linux (SocketCAN):

```bash
sudo ip link set can0 up type can bitrate 500000
# For local tests without hardware:
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0
```

- Windows: Use vendor tools to configure adapter/channel (e.g., PCAN `PCAN_USBBUS1`, Kvaser channel `0`).

### 3) Run the IDS

```bash
python industrialNetwork/NIDS_CAN/main.py
```

Tune the channel and adapter in the code if not using SocketCAN. For `vcan0`, adjust the constructor accordingly.

### 4) Launch CAN Attacks

```bash
# Help
python attacks/CANbus/can_attacks.py --help

# Flood at 5k fps for 10s (SocketCAN)
python attacks/CANbus/can_attacks.py flood --bus-type socketcan --channel can0 \
	--id 0x123 --dlc 8 --payload-mode random --rate 5000 --duration 10

# Fuzz across standard ID space
python attacks/CANbus/can_attacks.py fuzz --bus-type socketcan --channel can0 \
	--id-range 0x000-0x7FF --min-dlc 0 --max-dlc 8 --payload-mode random --rate 500 --duration 30

# Spoof with fixed payload every 20ms (Windows/Kvaser example)
python attacks/CANbus/can_attacks.py spoof --bus-type kvaser --channel 0 \
	--id 0x321 --dlc 8 --payload 01,02,03,04,05,06,07,08 --period 0.02 --duration 10

# Replay from CSV with timestamp preservation
python attacks/CANbus/can_attacks.py replay --bus-type socketcan --channel can0 \
	--input path/to/log.csv --preserve-timestamps
```

### 5) Run ANPR Adversarial Experiments

See [attacks/adversarialANPR/README.md](attacks/adversarialANPR/README.md) for full steps. In short:

```bash
pip install -r attacks/adversarialANPR/requirements.txt
# Open and run the notebook
code attacks/adversarialANPR/adversarial_ANPR.ipynb
```

## Data, Logs, and Metrics

- IDS writes SQLite `can_ids.db` with `messages` and `anomalies` tables and logs to `intrusions.log`.
- CAN attack CLI logs all transmitted frames to CSV (path configurable with `--log`).
- ANPR notebook saves visualizations and quantitative summaries for each attack.

Example anomaly query (Linux):

```bash
sqlite3 can_ids.db "SELECT datetime(timestamp,'unixepoch'), can_id, anomaly_type FROM anomalies ORDER BY timestamp DESC LIMIT 10;"
```

## Tests

See [tests/README.md](tests/README.md) for MQTT and integration utilities, including:

- `test_mqtt_send.py` and `test_mqtt_rec.py` for broker interaction and YOLO API checks.
- `send_over_serial.py` for serial-based checks.
- Additional scenarios for end-to-end validation and troubleshooting.

## Ethics and Safe Use

All experiments must be performed on isolated, authorized testbeds. Do not connect experimental setups to public roads or production environments. Follow institutional review processes and responsible disclosure for any discovered issues.

## License

This project is licensed under the terms described in [LICENSE](LICENSE).