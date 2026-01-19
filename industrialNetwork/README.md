# Industrial Network (Smart Parking)

This directory contains the embedded programs and host utilities used in the industrial segment of the Smart Parking system: CAN-connected sensors and actuators, a PIC32MZ-based CAN gateway, and a network-based CAN Intrusion Detection System (IDS) used in our experiments and evaluations.

## Contents

- [ambient_transmitter](ambient_transmitter/ambient_transmitter.ino): Arduino sketch that publishes ambient sensor readings (e.g., temperature, air quality) over CAN.
- [transmitterCAN](transmitterCAN/transmitterCAN.ino): Example CAN transmitter for general telemetry frames.
- [recieverCAN](recieverCAN/recieverCAN.ino): Example CAN receiver for validation and local indicators.
- [ultrasonic](ultrasonic/ultrasonic.ino): Ultrasonic distance sensor (spot occupancy) with a local LED indicator.
- [servoMotor](servoMotor/servoMotor.ino): Servo-driven barrier actuator that periodically reports state over CAN.
- [PIC32MZ](PIC32MZ/original.c): PIC32MZ-based CAN gateway/bridge connecting the CAN bus to upstream services.
- [NIDS_CAN](NIDS_CAN/main.py): Network-Based IDS for CAN bus monitoring, anomaly detection, persistent logging, and alerting.

## CAN Network IDS

The IDS in [NIDS_CAN/main.py](NIDS_CAN/main.py) is a modular, host-side monitor for a single CAN segment. It learns a baseline from benign traffic and applies multi-layer anomaly detection during operation. It is designed to be reproducible and extensible for research.

### Objective and Scope

- Detect deviations in CAN traffic that may indicate misuse or attacks (e.g., flooding, fuzzing, invalid payloads, DLC mismatches, unexpected IDs).
- Provide auditable artifacts: persistent message/anomaly logs (SQLite), console traces, and MQTT alerts for higher-level orchestration.

### Environment and Dependencies

- OS/Interface: Linux with SocketCAN (`channel='can0'` by default). For reproducibility, tests can use `vcan0`.
- Python 3.8+ with the following packages:
	- `python-can`
	- `numpy`
	- `paho-mqtt`
	- `sqlite3` (stdlib)

Install packages:

```bash
pip install python-can numpy paho-mqtt
```

Bring up a virtual CAN interface for local testing (Linux):

```bash
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0
```

Then run the IDS with `channel='vcan0'` (update in code or adapt invocation).

Note: The current implementation initializes the CAN bus with `interface='socketcan'`. On non-Linux or vendor-specific adapters (e.g., PCAN, Kvaser), update the interface and channel accordingly in `CANNetworkIDS.__init__`.

### Architecture and Detection Logic

- Ingestion: `python-can` bus receiving frames from the configured `channel`/bitrate.
- Baseline Learning: Collects per-ID frequency, DLC, and payload samples for a configurable warm-up window.
- Detection (multi-layer):
	- Unknown CAN ID (not observed in baseline)
	- DLC mismatch (runtime DLC differs from learned DLC)
	- Sensor value range validation (coarse first-byte check per configured ID ranges)
	- Frequency/DoS (messages per-ID exceeding threshold in a 1s window)
	- Payload pattern deviation (mean absolute deviation from baseline payloads)
- Outputs:
	- SQLite database (`can_ids.db`) with tables `messages` and `anomalies`
	- Console statistics and anomaly prints
	- File `intrusions.log` for critical events
	- MQTT alert (`ids/alerts`) carrying JSON payloads (timestamp, type, CAN ID, DLC, data)

Key tunables (see `CANNetworkIDS`): `window_size`, `frequency_threshold`, `anomaly_threshold`, and sensor `id`/`range` mappings in `sensor_ranges`.

### Data and Logging Schema

- `messages(timestamp REAL, can_id INTEGER, dlc INTEGER, data BLOB, is_anomaly BOOLEAN)`
- `anomalies(timestamp REAL, can_id INTEGER, anomaly_type TEXT, severity TEXT, details TEXT)`

Example query (Linux):

```bash
sqlite3 can_ids.db "SELECT datetime(timestamp,'unixepoch'), can_id, anomaly_type FROM anomalies ORDER BY timestamp DESC LIMIT 10;"
```

### Running the IDS

1) Learn baseline (default 60s) and start monitoring (SocketCAN example):

```bash
python3 NIDS_CAN/main.py
```

2) To test with `vcan0`, change the constructor to `channel='vcan0'` in `__main__`.

3) Optional: Configure MQTT broker (`mqtt_broker`, `mqtt_port`) and subscribe to `ids/alerts`.

### Evaluation Guidance

- Baseline: Capture benign traffic reflecting normal duty cycles for ≥60s.
- Attack stimuli (examples):
	- Flooding/DoS on selected IDs to exceed `frequency_threshold`.
	- Payload fuzzing to trigger `pattern_deviation` and `out_of_range`.
	- DLC inconsistencies and unknown IDs to exercise structural checks.
- Metrics: Compute detection rate, false positives, and time-to-detect using `messages` and `anomalies` with synchronized ground truth.

### Limitations and Extensions

- Value checks use the first data byte for simplicity. If a sensor uses multi-byte encodings (e.g., 2-byte temperature), adapt `_detect_anomalies` to parse and validate the intended field.
- Baseline persistence across runs is not yet implemented (learned state is in-memory). Consider persisting model state for production.
- Additional detectors (per-ID inter-arrival models, entropy-based validators, learned sequence models) can be integrated.

## Build & Run (Devices)

- Arduino sketches: Open the respective `.ino` in Arduino IDE, select the board and CAN shield/interface, then upload.
- PIC32MZ gateway: Open [PIC32MZ/original.c](PIC32MZ/original.c) in MPLAB X (XC32), configure target pins/bitrate, build, and flash.

## CAN Message Specification (Sensors & Actuators)

For device interoperability, each measurement is encoded into CAN payload bytes with clearly defined ID ranges, units, scaling, and endianness. Example (temperature):

- Temperature sensor IDs: range 0x400–0x500
- Payload: 2 bytes, big-endian
- Range: 0.00°C to 99.99°C, two decimals
- Scaling: value = round(°C × 100)
- Example: 85.31°C → 8531 → 0x2152 → MSB=0x21, LSB=0x52
- Example CAN frame: `423#022152` for sensor with ID 0x423

Notes:

- Air quality: No ACK required; periodic measures.
- Gas: No ACK required; periodic measures.
- Ultrasound (occupancy): Periodic spot presence; drives local LED; no ACK.
- Servo (barrier): Periodically reports barrier state; ID + state suffice for status.

Important: The IDS currently validates sensor ranges using a coarse 1-byte value (see `sensor_ranges` in [NIDS_CAN/main.py](NIDS_CAN/main.py)). If your deployed encoding uses multi-byte fields (as in the temperature example), extend `_detect_anomalies` to parse those fields for accurate range checks.

## Related Tests

Integration and transport tests for the broader system (e.g., serial/MQTT) are under [../tests](../tests). Use them to validate end-to-end messaging once device-level components here are deployed.

## Sensor and actuators
For each sensor measurement data sent over the CAN. We should construct a specification for its corresponding translation. For example, for temperature data:
- Temperature sensor IDs will be in the range 0x400-0x500
- 2 Bytes used
- Ranges from 0ºC to 99.99ºC
- Only 2 decimals for ºC
- Conversion factor will be as follows: (TEMP x 100)
- Then converted into hex to send over CAN using 2 bytes
- So, 85.31ºC -> 8531 -> 0x2152 -> MSB=21, LSB=52
- CAN message will be: 423#022152 for sensor with ID 423
### Air quality 
Needs no ACK, just send measures
### Gas 
Needs no ACK, just send measures
### Ultrasound
Sensor for detecting presence in the parking spot. Will have a led attached to indicate locally whether the spot is busy or not. Independently the data will be sent over CAN, Needs no ACK, just send measures.
### Servo
Simulating barrier. Barrier will constantly send their state, which along with the identifier will provide a complete understanding of barrier(s) state.
