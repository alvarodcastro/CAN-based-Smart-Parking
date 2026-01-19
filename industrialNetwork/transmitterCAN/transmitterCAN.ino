#include <SPI.h>
#include <mcp2515.h>
#include <math.h>

struct can_frame canTx;
struct can_frame canRx;
struct MCP2515 mcp2515(5); // CS pin is GPIO 5

#define MAX_RETRIES 3
#define CAN_ACK_ID 0x037  // CAN ID for acknowledgment
#define CAN_TX_ID  0x036

// Simulation parameters
const float TEMP_BASE = 25.0;    // center temperature (°C)
const float TEMP_AMP  = 3.0;     // amplitude (°C)
const unsigned long TEMP_PERIOD_MS = 60000UL; // period for sine wave (60s)
unsigned long lastSendMillis = 0;
const unsigned long SEND_INTERVAL_MS = 1000UL; // send every 5 seconds

void setup() {
  Serial.begin(115200);
  delay(10);

  SPI.begin();
  mcp2515.reset();
  mcp2515.setBitrate(CAN_500KBPS, MCP_8MHZ);
  mcp2515.setNormalMode();

  // seed random with some entropy (floating pin)
  randomSeed(analogRead(0));
}

float simulatedTemperature() {
  // Create a smooth sinusoidal temperature + small random jitter
  unsigned long t = millis();
  float phase = (float)(t % TEMP_PERIOD_MS) / (float)TEMP_PERIOD_MS; // 0..1
  float sine = sinf(phase * 2.0f * M_PI); // -1..1
  float jitter = (random(-20, 21) / 100.0f); // random -0.20 .. +0.20 °C
  return TEMP_BASE + (TEMP_AMP * sine) + jitter;
}

void loop() {
  unsigned long now = millis();

  if (now - lastSendMillis < SEND_INTERVAL_MS) {
    // nothing to do yet
    return;
  }
  lastSendMillis = now;

  float temperatureC = simulatedTemperature();
  int tempInt = (int)round(temperatureC * 100.0f); // centi-degrees stored in 2 bytes

  // Prepare CAN transmit message
  canTx.can_id  = CAN_TX_ID;
  canTx.can_dlc = 2;
  canTx.data[0] = (tempInt >> 8) & 0xFF; // MSB
  canTx.data[1] = tempInt & 0xFF;        // LSB

  bool messageSent = false;
  int retries = 0;

  unsigned int waitTime = 100;


  if (mcp2515.sendMessage(&canTx) == MCP2515::ERROR_OK) {
      Serial.print("[CAN] Sent temperature: ");
      Serial.print(temperatureC, 2);
      Serial.println(" °C");

  }else{
    Serial.print("[CAN] Error sending message in sensor ");
    Serial.println(CAN_TX_ID);
  }


  // while (!messageSent && retries < MAX_RETRIES) {
  //   if (mcp2515.sendMessage(&canTx) == MCP2515::ERROR_OK) {
  //     Serial.print("[CAN] Sent temperature: ");
  //     Serial.print(temperatureC, 2);
  //     Serial.println(" °C");

  //     // Wait up to 500ms for ACK (polling)
  //     unsigned long startTime = millis();
  //     bool ackReceived = false;

  //     while (millis() - startTime < 500) {
  //       if (mcp2515.readMessage(&canRx) == MCP2515::ERROR_OK) {
  //         if (canRx.can_id == CAN_ACK_ID) {
  //           ackReceived = true;
  //           break;
  //         }
  //       }
  //     }

  //     if (ackReceived) {
  //       Serial.println("[CAN] ACK received");
  //       messageSent = true;
  //     } else {
  //       Serial.println("[CAN] ACK not received, retrying...");
  //       retries++;
  //     }

  //   } else {
  //     Serial.println("[CAN] Error sending message, retrying...");
  //     retries++;
  //   }
  // }

  // if (!messageSent) {
  //   Serial.println("[CAN] Failed to send message after retries");
  // }

  // loop continues; next send will occur after SEND_INTERVAL_MS elapsed
}
