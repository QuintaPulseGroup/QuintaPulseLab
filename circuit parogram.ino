#define SENSOR_PIN A0

void setup() {
  Serial.begin(9600);
}

void loop() {
  int raw = analogRead(SENSOR_PIN);
  Serial.println(raw);
  delay(20); // Sampling rate ~50 Hz
}
