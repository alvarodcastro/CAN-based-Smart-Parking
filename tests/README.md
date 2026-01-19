# Testing Tools

This directory contains tools for testing different components of the Critical IoT Vehicle Access System.

## MQTT Testing Tools

### 1. MQTT Sender (`test_mqtt_send.py`)

This script allows testing of both the MQTT message sending functionality and direct YOLO API access.

#### Prerequisites
- Python 3.x
- Required packages:
  ```
  paho-mqtt
  requests
  ```

#### Configuration
The script uses these default settings:
```python
BROKER = "localhost"
PORT = 1883
USERNAME = "user"
PASSWORD = "user123"
YOLO_API_URL = "http://127.0.0.1:4000/api/anpr"
```

#### Usage

The script can be run in three different modes:

1. Test both MQTT and YOLO API (default):
```powershell
python tests/test_mqtt_send.py
```

2. Test only MQTT messaging:
```powershell
python tests/test_mqtt_send.py --mode mqtt
```

3. Test only YOLO API:
```powershell
python tests/test_mqtt_send.py --mode api
```

#### Topics Used
- Gate Access: `gate/1/access`
- Gate Status: `gate/1/status`
- Gate Sync: `gate/1/sync`
- Server Response: `server/response/{gate_id}`

### 2. MQTT Receiver (`test_mqtt_rec.py`)

This script acts as a test subscriber to verify MQTT message delivery and server responses.

#### Usage
```powershell
python tests/test_mqtt_rec.py
```

The receiver will:
- Connect to the MQTT broker
- Subscribe to all relevant topics
- Print received messages to the console

## Test Environment Setup

1. Start the MQTT broker:
```powershell
cd docker/mosquitto
docker-compose up -d
```

2. Start the YOLO API service:
```powershell
cd docker/yolo
docker-compose up -d
```

3. Ensure the main application is running:
```powershell
python main.py
```

## Test Scenarios

### 1. Basic MQTT Communication
1. Start the receiver (`test_mqtt_rec.py`)
2. Run the sender with MQTT mode (`test_mqtt_send.py --mode mqtt`)
3. Verify messages are received and processed

### 2. YOLO API Integration
1. Run the sender with API mode (`test_mqtt_send.py --mode api`)
2. Check the response for plate detection results

### 3. End-to-End Testing
1. Start the receiver
2. Run the sender in both mode (`test_mqtt_send.py --mode both`)
3. Verify both MQTT messages and API responses

## Troubleshooting

### MQTT Connection Issues
1. Verify broker is running:
```powershell
docker ps | findstr mosquitto
```

2. Check broker logs:
```powershell
docker-compose logs mosquitto
```

3. Verify correct credentials in test scripts

### YOLO API Issues
1. Check if the API is running:
```powershell
curl http://127.0.0.1:4000/api/test
```

2. Check Docker logs:
```powershell
docker logs yolo-api
```

## Notes

- The test scripts use a default test image of a Spanish license plate
- Messages are Base64 encoded before sending
- Default timeout for MQTT connections is 60 seconds
- Tests use gate ID "1" by default