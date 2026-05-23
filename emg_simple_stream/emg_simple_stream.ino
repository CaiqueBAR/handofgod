#define EMG_PIN A0
#define BAUD 115200

void setup() {
  Serial.begin(BAUD);
  analogReference(DEFAULT);
  delay(200);
  Serial.println("EMG_STREAM_OK");
}

void loop() {
  int v = analogRead(EMG_PIN);
  Serial.println(v);
  delay(5);
}

