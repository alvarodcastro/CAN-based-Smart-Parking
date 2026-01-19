import time
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
USERNAME = "user"  # Replace with actual username
PASSWORD = "user123"  # Replace with actual password

TOPIC_GATE_STATUS = "gate/1/status"
TOPIC_GATE_ACCESS = "gate/1/access"
TOPIC_GATE_SYNC = "gate/1/sync"
TOPIC_SERVER_RESPONSE = "server/response/1"
TOPIC_SENSOR_DATA = "gate/1/sensors"
TOPIC_ACTUATORS = "gate/1/actuators"

def on_connect(client, userdata, flags, rc, properties=None):
    print("Connected with result code " + str(rc))
    client.subscribe(TOPIC_GATE_ACCESS)
    client.subscribe(TOPIC_GATE_STATUS)
    client.subscribe(TOPIC_GATE_SYNC)
    client.subscribe(TOPIC_SERVER_RESPONSE)
    client.subscribe(TOPIC_SENSOR_DATA)
    client.subscribe(TOPIC_ACTUATORS)
    print(f"Subscribed to {TOPIC_SERVER_RESPONSE}")
    print(f"Subscribed to {TOPIC_GATE_ACCESS}")
    print(f"Subscribed to {TOPIC_GATE_STATUS}")
    print(f"Subscribed to {TOPIC_GATE_SYNC}")
    print(f"Subscribed to {TOPIC_SENSOR_DATA}")
    print(f"Subscribed to {TOPIC_ACTUATORS}")

def on_message(client, userdata, msg):
    print(f"Received message on {msg.topic}: {msg.payload.decode()}")

def main():
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    client.username_pw_set(USERNAME, PASSWORD)  # Set authentication credentials
    client.connect(BROKER, PORT)
    client.loop_start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    client.loop_stop()
    client.disconnect()

if __name__ == "__main__":
    main()