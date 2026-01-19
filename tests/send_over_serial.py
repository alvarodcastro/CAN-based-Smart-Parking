import serial
import time

ser = serial.Serial('COM8', 115200, timeout=1)  # adjust COM and baud

commands = [
    "TX 201 1E\r\n",
    "TX 201 1E\r\n",
    "TX 201 1E\r\n"
]

while True:
    start_time = time.time()
    
    # Listen for incoming data for 5 seconds
    while time.time() - start_time < 8:
        if ser.in_waiting:
            data = ser.readline().decode('ascii', errors='ignore')
            print(f"Received: {data.strip()}")
        time.sleep(0.1)

    # Send commands after listening
    for cmd in commands:
        line = cmd + "\r\n"
        ser.write(line.encode('ascii'))
        print(f"Sent: {line.strip()}")
        time.sleep(0.1)

ser.close()