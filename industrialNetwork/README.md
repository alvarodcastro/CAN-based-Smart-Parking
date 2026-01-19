# Industrial Network

This folder contains the programs and sketches that run on the industrial-network equipment for the Smart Parking system — from sensors and actuators on the CAN bus, to a network-based CAN Intrusion Detection System (IDS), and a CAN-to-network gateway implemented on a PIC32MZ board.

## Contents

- [ambient_transmitter](ambient_transmitter/ambient_transmitter.ino): Arduino sketch to publish ambient sensor readings (e.g., temperature, air quality) over CAN.
- [transmitterCAN](transmitterCAN/transmitterCAN.ino): Arduino CAN transmitter example for publishing sensor/telemetry frames.
- [recieverCAN](recieverCAN/recieverCAN.ino): Arduino CAN receiver example, useful for validating bus traffic and local indicators.
- [ultrasonic](ultrasonic/ultrasonic.ino): Ultrasonic distance sensor for spot occupancy detection with local LED indication.
- [servoMotor](servoMotor/servoMotor.ino): Servo-based barrier actuator that periodically reports its state over CAN.
- [NIDS_CAN](NIDS_CAN/main.py): Prototype CAN IDS for monitoring and detecting anomalies on the CAN network.
- [PIC32MZ](PIC32MZ/original.c): PIC32MZ-based CAN gateway/bridge implementation to connect the CAN bus with upstream networks/services.

## Build & Run

- Arduino sketches: Open the respective `.ino` in Arduino IDE, select the correct board and CAN interface/shield settings, then upload.
- PIC32MZ gateway: Open the C source in MPLAB X (XC32 toolchain), configure the target and CAN pins/bitrate, then build and flash.
- CAN IDS (Python): Run the IDS prototype from [NIDS_CAN/main.py](NIDS_CAN/main.py) with your Python 3 environment. Ensure any required CAN interface libraries are installed and configured according to your setup.

## CAN Message Specification (Sensors & Actuators)

For each sensor, raw measurements are encoded into CAN data bytes according to a simple translation. Example for temperature data:

- Temperature sensor IDs: range 0x400–0x500
- Payload size: 2 bytes
- Measurement range: 0°C to 99.99°C
- Resolution: two decimal places
- Conversion factor: (TEMP × 100)
- Convert to hexadecimal using 2 bytes
- Example: 85.31°C → 8531 → 0x2152 → MSB=21, LSB=52
- Example CAN frame: `423#022152` for sensor with ID 0x423

Sensor/actuator notes:

- Air quality: Needs no ACK, just send measures.
- Gas: Needs no ACK, just send measures.
- Ultrasound: Detects spot presence and drives a local LED; needs no ACK, just send measures.
- Servo (barrier): Periodically sends barrier state; the state and identifier provide full status.

If additional sensors are added, follow the same pattern: define ID ranges, byte-size, unit scaling, and encoding (endianness) so the gateway/IDS can decode consistently.

## Related Tests

Integration and transport tests for the broader system (e.g., serial/MQTT) are available under [tests](../tests). Use them to validate end-to-end messaging once device-level pieces here are deployed.

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
