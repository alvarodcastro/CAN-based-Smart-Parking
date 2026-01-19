#!/usr/bin/env python3
"""
Network-Based IDS for CAN Bus
Monitors traffic, detects anomalies, logs incidents
"""

import can
import sqlite3
from datetime import datetime
from collections import defaultdict, deque
import numpy as np
import json
import paho.mqtt.client as mqtt

class CANNetworkIDS:
    def __init__(self, channel='can0', bitrate=500000, mqtt_broker='localhost', mqtt_port=1883):
        """Initialize the network-based IDS"""
        self.bus = can.interface.Bus(channel=channel, 
                                     interface='socketcan',
                                     bitrate=bitrate)
        
        # Initialize MQTT client
        self.mqtt_client = mqtt.Client()
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        try:
            self.mqtt_client.connect(mqtt_broker, mqtt_port, 60)
            self.mqtt_client.loop_start()
            print(f"Connected to MQTT broker at {mqtt_broker}:{mqtt_port}")
        except Exception as e:
            print(f"Warning: Could not connect to MQTT broker: {e}")
        
        # Configuration for your sensor network
        self.sensor_ranges = {
            'temperature': (0x300, 0x399, 0, 120),      # CAN ID range, value range
            "air_quality": (0x500, 0x599, 0, 700),
            "gas": (0x600, 0x699, 0, 500),
            "occupancy": (0x700, 0x799, 0, 1),
            "barrier_state": (0x400, 0x499, 0, 1),
            "barrier_command": (0x300, 0x399, 0, 1),
        }
        
        # Baseline statistics (learned during normal operation)
        self.message_frequency = defaultdict(deque)  # CAN ID -> list of timestamps
        self.message_patterns = defaultdict(list)     # CAN ID -> payload patterns
        self.baseline_dlc = {}                         # CAN ID -> expected DLC
        
        # Tuning parameters
        self.window_size = 10
        self.frequency_threshold = 100  # msgs per second (too high = DoS)
        self.anomaly_threshold = 0.8    # Reconstruction error threshold
        
        # Initialize database
        self._init_database()
        
        # Statistics
        self.message_count = 0
        self.anomaly_count = 0
    
    def _init_database(self):
        """Create SQLite database for logging"""
        self.conn = sqlite3.connect('can_ids.db')
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                timestamp REAL,
                can_id INTEGER,
                dlc INTEGER,
                data BLOB,
                is_anomaly BOOLEAN
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS anomalies (
                id INTEGER PRIMARY KEY,
                timestamp REAL,
                can_id INTEGER,
                anomaly_type TEXT,
                severity TEXT,
                details TEXT
            )
        ''')
        self.conn.commit()
    
    def learn_baseline(self, duration_seconds=60):
        """Learn normal traffic patterns during initialization"""
        print(f"Learning baseline for {duration_seconds} seconds...")
        start_time = datetime.now().timestamp()
        
        while datetime.now().timestamp() - start_time < duration_seconds:
            msg = self.bus.recv(timeout=1)
            if msg is None:
                continue
            
            # Record message frequency
            self.message_frequency[msg.arbitration_id].append(
                datetime.now().timestamp()
            )
            
            # Record DLC
            self.baseline_dlc[msg.arbitration_id] = msg.dlc
            
            # Record payload pattern
            self.message_patterns[msg.arbitration_id].append(msg.data)
            
            self.message_count += 1
        
        print(f"Learned {len(self.message_frequency)} unique CAN IDs")
        self._print_baseline_stats()
    
    def _print_baseline_stats(self):
        """Display learned baseline statistics"""
        print("\n=== BASELINE STATISTICS ===")
        for can_id, timestamps in sorted(self.message_frequency.items()):
            if len(timestamps) > 1:
                intervals = np.diff(timestamps)
                freq = len(timestamps)
                print(f"CAN ID 0x{can_id:03X}: {freq} msgs, "
                      f"avg interval: {np.mean(intervals)*1000:.1f}ms")
    
    def _detect_anomalies(self, msg):
        """
        Multi-layered anomaly detection
        Returns: (is_anomaly, anomaly_type, severity)
        """
        anomalies = []
        
        # Check 1: Unknown CAN ID
        if msg.arbitration_id not in self.baseline_dlc:
            anomalies.append(("unknown_id", "WARNING"))
        
        # Check 2: DLC mismatch
        if msg.arbitration_id in self.baseline_dlc:
            if msg.dlc != self.baseline_dlc[msg.arbitration_id]:
                anomalies.append(("dlc_mismatch", "CRITICAL"))
        
        # Check 3: Sensor range validation
        can_id = msg.arbitration_id
        for sensor_type, (id_min, id_max, val_min, val_max) in self.sensor_ranges.items():
            if id_min <= can_id <= id_max:
                # This is a sensor message
                if msg.dlc >= 1:
                    if msg.data is None or len(msg.data) == 0:
                        anomalies.append(("invalid_data", "HIGH"))
                        break
                    value = msg.data[0]
                    if not (val_min <= value <= val_max):
                        anomalies.append(("out_of_range", "HIGH"))
                break
        
        # Check 4: Frequency analysis (DoS detection)
        if can_id in self.message_frequency:
            recent_msgs = self.message_frequency[can_id]
            # Keep only last second of messages
            now = datetime.now().timestamp()
            recent_msgs = [t for t in recent_msgs 
                         if now - t < 1.0]
            
            if len(recent_msgs) > self.frequency_threshold:
                anomalies.append(("dos_attack", "CRITICAL"))
        
        # Check 5: Pattern deviation (fuzzing detection)
        if can_id in self.message_patterns:
            baseline_patterns = self.message_patterns[can_id]
            if baseline_patterns:
                baseline_data = np.array(
                    [list(p) for p in baseline_patterns]
                )
                curr_data = np.array(list(msg.data))
                
                # Calculate deviation from mean pattern
                mean_pattern = np.mean(baseline_data, axis=0)
                deviation = np.abs(curr_data - mean_pattern).mean()
                
                if deviation > 50:  # Threshold in bytes
                    anomalies.append(("pattern_deviation", "MEDIUM"))
        
        if anomalies:
            return True, anomalies[0][0], anomalies[0][1]
        return False, None, None
    
    def run(self):
        """Main IDS loop"""
        print("Network-Based IDS Started. Press Ctrl+C to stop.")
        
        try:
            while True:
                msg = self.bus.recv(timeout=1)
                
                if msg is None:
                    continue
                
                # Update statistics
                self.message_frequency[msg.arbitration_id].append(
                    datetime.now().timestamp()
                )
                self.message_count += 1
                
                # Detect anomalies
                is_anomaly, anom_type, severity = self._detect_anomalies(msg)
                
                # Log message
                self._log_message(msg, is_anomaly)
                
                if is_anomaly:
                    self._handle_anomaly(msg, anom_type, severity)
                
                # Periodic stats
                if self.message_count % 1000 == 0:
                    self._print_stats()
        
        except KeyboardInterrupt:
            print("\nIDS Stopped.")
        finally:
            self._cleanup()
    
    def _log_message(self, msg, is_anomaly):
        """Log message to database"""
        self.cursor.execute('''
            INSERT INTO messages 
            (timestamp, can_id, dlc, data, is_anomaly)
            VALUES (?, ?, ?, ?, ?)
        ''', (datetime.now().timestamp(), msg.arbitration_id, 
              msg.dlc, msg.data.hex(), is_anomaly))
        
        if self.message_count % 100 == 0:
            self.conn.commit()
    
    def _handle_anomaly(self, msg, anom_type, severity):
        """Handle detected anomaly"""
        self.anomaly_count += 1
        
        print(f"\nANOMALY DETECTED [#{self.anomaly_count}]")
        print(f"   Severity: {severity}")
        print(f"   Type: {anom_type}")
        print(f"   CAN ID: 0x{msg.arbitration_id:03X}")
        print(f"   Data: {msg.data.hex()}")
        print(f"   Timestamp: {datetime.now().isoformat()}")
        
        # Log to database
        self.cursor.execute('''
            INSERT INTO anomalies 
            (timestamp, can_id, anomaly_type, severity, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (datetime.now().timestamp(), msg.arbitration_id,
              anom_type, severity, msg.data.hex()))
        self.conn.commit()
        
        # Action based on severity
        if severity == "CRITICAL":
            self._trigger_alert(msg, anom_type)
    
    def _trigger_alert(self, msg, anom_type):
        """Trigger protective actions"""
        # Option 1: Log and notify
        with open('intrusions.log', 'a') as f:
            f.write(f"{datetime.now().isoformat()}: {anom_type} on 0x{msg.arbitration_id:03X}\n")
        
        # Option 2: Send to MQTT
        alert_payload = {
            "timestamp": datetime.now().isoformat(),
            "anomaly_type": anom_type,
            "can_id": f"0x{msg.arbitration_id:03X}",
            "data": msg.data.hex(),
            "dlc": msg.dlc
        }
        try:
            self.mqtt_client.publish(
                "ids/alerts",
                json.dumps(alert_payload),
                qos=1
            )
            print(f"   ACTION: Alert sent to MQTT topic 'ids/alerts'")
        except Exception as e:
            print(f"   ERROR: Could not send MQTT alert: {e}")
        
        # Option 3: Send alert via email/SMS
        # self._send_alert(msg, anom_type)
        
        print(f"   ACTION: Alert triggered for {anom_type}")
    
    def _print_stats(self):
        """Print IDS statistics"""
        detection_rate = (self.anomaly_count / self.message_count * 100) \
                        if self.message_count > 0 else 0
        print(f"\n=== IDS STATS ===")
        print(f"Messages processed: {self.message_count}")
        print(f"Anomalies detected: {self.anomaly_count}")
        print(f"Detection rate: {detection_rate:.2f}%")
    
    def _cleanup(self):
        """Cleanup resources"""
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        self.conn.close()
        self.bus.shutdown()

if __name__ == '__main__':
    # Create IDS instance
    ids = CANNetworkIDS(channel='can0', bitrate=500000)
    
    # Learn normal traffic patterns (60 seconds of normal operation)
    ids.learn_baseline(duration_seconds=60)
    
    # Start monitoring
    ids.run()
