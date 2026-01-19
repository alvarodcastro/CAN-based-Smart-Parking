import time
import json
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
USERNAME = "user"
PASSWORD = "user123"

TOPIC_ACTUATOR = "gate/1/actuators"

def on_connect(client, userdata, flags, rc, properties=None):
    """Callback when client connects to broker"""
    print(f"Connected with result code {rc}")


def send_barrier_command(client, gate_id: int, command: bool):
    """Send barrier command to specific gate"""
    topic = f"gate/{gate_id}/actuators"
    payload = {"barrierCommand": command}
    payload_json = json.dumps(payload)
    
    result = client.publish(topic, payload_json)
    print(f"Sent to {topic}: {payload_json}")
    print(f"Result: {result.rc}")
    return result

def main():
    # Create MQTT client
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    
    # Set authentication credentials
    client.username_pw_set(USERNAME, PASSWORD)
    
    # Connect to broker
    try:
        client.connect(BROKER, PORT, 60)
        client.loop_start()
        print(f"Connected to MQTT broker at {BROKER}:{PORT}")
        
        # Wait for connection to establish
        time.sleep(1)
        
        # Test sending barrier commands
        print("\n--- Testing Barrier Commands ---")
        
        # Open barrier (gate 1)
        print("\n1. Opening barrier for gate 1...")
        send_barrier_command(client, 1, True)
        time.sleep(2)
        
        # Close barrier (gate 1)
        print("\n2. Closing barrier for gate 1...")
        send_barrier_command(client, 1, False)
        time.sleep(2)
        
        # Open barrier (gate 1)
        print("\n1. Opening barrier for gate 1...")
        send_barrier_command(client, 1, True)
        time.sleep(2)
        
        # Close barrier (gate 1)
        print("\n2. Closing barrier for gate 1...")
        send_barrier_command(client, 1, False)
        time.sleep(2)
        
        
        
        print("\nAll test messages sent successfully!")
        
        # Keep connection alive for a bit
        time.sleep(2)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.loop_stop()
        client.disconnect()
        print("Disconnected from broker")

if __name__ == "__main__":
    main()
