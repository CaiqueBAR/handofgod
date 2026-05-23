#define EMG_PIN A0

float emgFiltrado = 0;
float alpha = 0.2;

void setup() {
  Serial.begin(115200);
}

void loop() {
  int emgValor = analogRead(EMG_PIN);

  emgFiltrado = (alpha * emgValor) + ((1.0 - alpha) * emgFiltrado);

  Serial.print(emgValor);
  Serial.print('\t');
  Serial.println(emgFiltrado, 3);

  delay(2);
}

