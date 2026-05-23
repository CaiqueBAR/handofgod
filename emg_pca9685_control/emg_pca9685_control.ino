#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pca = Adafruit_PWMServoDriver();

const int emgPin = A0;
int emgThreshold = 0;
const int emgThresholdDelta = 60;
int emgValue = 0;
float emgBaseline = 512.0f;
float emgSmoothed = 0.0f;
const float smoothAlpha = 0.15f;

#define SERVOMIN 150
#define SERVOMAX 600

void setup() {
  Serial.begin(115200);

  analogReference(DEFAULT);

  pca.begin();
  pca.setPWMFreq(50);

  delay(500);

  long acc = 0;
  const int n = 300;
  for (int i = 0; i < n; i++) {
    acc += analogRead(emgPin);
    delay(2);
  }
  emgBaseline = (float)acc / (float)n;
  emgSmoothed = emgBaseline;
  emgThreshold = (int)emgBaseline + emgThresholdDelta;
}

void loop() {
  emgValue = analogRead(emgPin);
  emgSmoothed += smoothAlpha * ((float)emgValue - emgSmoothed);

  Serial.print(emgValue);
  Serial.print('\t');
  Serial.print((int)emgSmoothed);
  Serial.print('\t');
  Serial.println(emgThreshold);

  if (emgSmoothed > (float)emgThreshold) {
    moverTodosServos(180);
  } else {
    moverTodosServos(0);
  }

  delay(20);
}

void moverTodosServos(int angulo) {
  int pwm = map(angulo, 0, 180, SERVOMIN, SERVOMAX);

  for (int canal = 0; canal < 5; canal++) {
    pca.setPWM(canal, 0, pwm);
  }
}
