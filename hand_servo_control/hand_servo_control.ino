#include <Servo.h>

Servo dedos[5];
Servo pulso;

int pinos[5] = {3, 5, 6, 9, 10};

void setup() {
  Serial.begin(9600);

  for (int i = 0; i < 5; i++) {
    dedos[i].attach(pinos[i]);
    dedos[i].write(0);
  }

  pulso.attach(11);
  pulso.write(0);

  Serial.println("Digite um comando:");
}

void moverServo(Servo &s) {
  for (int ang = 0; ang <= 180; ang++) {
    s.write(ang);
    delay(5);
  }
  for (int ang = 180; ang >= 0; ang--) {
    s.write(ang);
    delay(5);
  }
}

void fecharTodos() {
  for (int ang = 0; ang <= 180; ang++) {
    for (int i = 0; i < 5; i++) {
      dedos[i].write(ang);
    }
    delay(5);
  }
  for (int ang = 180; ang >= 0; ang--) {
    for (int i = 0; i < 5; i++) {
      dedos[i].write(ang);
    }
    delay(5);
  }
}

void gestoJoinha() {
  dedos[1].write(180);
  dedos[2].write(180);
  dedos[3].write(180);
  dedos[4].write(180);
  delay(1000);

  for (int ang = 0; ang <= 180; ang++) {
    dedos[0].write(ang);
    delay(5);
  }

  delay(500);

  for (int i = 0; i < 5; i++) dedos[i].write(0);
}

void gestoPaz() {
  dedos[0].write(180);
  dedos[3].write(180);
  dedos[4].write(180);
  delay(1000);

  for (int ang = 0; ang <= 180; ang++) {
    dedos[1].write(ang);
    dedos[2].write(ang);
    delay(5);
  }

  delay(500);

  for (int i = 0; i < 5; i++) dedos[i].write(0);
}

void gestoRock() {
  dedos[1].write(180);
  dedos[2].write(180);
  delay(1000);

  for (int ang = 0; ang <= 180; ang++) {
    dedos[0].write(ang);
    dedos[4].write(ang);
    delay(5);
  }

  delay(500);

  for (int i = 0; i < 5; i++) dedos[i].write(0);
}

void acenar() {
  for (int i = 0; i < 3; i++) {
    pulso.write(60);
    delay(300);
    pulso.write(120);
    delay(300);
  }
  pulso.write(0);
}

void loop() {
  if (Serial.available()) {
    int comando = Serial.parseInt();
    Serial.println(comando);

    switch (comando) {
      case 1: moverServo(dedos[0]); break;
      case 2: moverServo(dedos[1]); break;
      case 3: moverServo(dedos[2]); break;
      case 4: moverServo(dedos[3]); break;
      case 5: moverServo(dedos[4]); break;
      case 6: moverServo(pulso); break;

      case 7: fecharTodos(); break;

      case 8: gestoJoinha(); break;
      case 9: gestoPaz(); break;
      case 10: gestoRock(); break;
      case 11: acenar(); break;

      default:
        Serial.println("Comando invalido");
    }
  }
}

