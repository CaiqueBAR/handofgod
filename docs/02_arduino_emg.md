# Arduino (EMG no A0)

## Objetivo

O Arduino lê o sinal analógico do eletrodo no pino **A0** e envia pela Serial um fluxo contínuo de amostras.

O Python não “lê A0” diretamente: ele lê a **porta COM** (USB) onde o Arduino está conectado.

## Configuração no Arduino IDE (igual ao seu print)

- Board: Arduino Nano
- Processor: ATmega168
- Port: COM20 (exemplo)
- Baud: 115200

## Formato de dados esperado

O sistema Python suporta:

1) Uma coluna (apenas raw):

```
523
524
...
```

2) Duas colunas (raw + filtrado):

```
523    501.123
524    501.456
...
```

Separadores aceitos: espaço ou TAB (`\t`).

## Sketch recomendado (raw + filtrado / “Serial Plotter-like”)

Este é equivalente ao que você está usando na IDE (A0, EMA alpha=0.2, 115200):

Arquivo no repositório:
- [emg_teste/emg_teste.ino](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/emg_teste/emg_teste.ino)

Código:

```cpp
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
```

## Sketch mínimo (apenas raw)

Arquivo no repositório:
- [emg_simple_stream/emg_simple_stream.ino](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/emg_simple_stream/emg_simple_stream.ino)

Uso:

- serve para validar se “chega número” na Serial
- facilita troubleshooting de porta/baud

## Dicas de hardware (prático)

- Use cabo USB de dados
- Evite hubs USB ruins
- Garanta boa fixação dos eletrodos na pele
- Minimize ruído:
  - mantenha fios curtos
  - evite encostar no GND/5V com mão solta durante teste

## PCA9685 + EMG + servos (opcional)

Existe um sketch de referência que lê EMG e movimenta servos via PCA9685:

- [emg_pca9685_control/emg_pca9685_control.ino](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/emg_pca9685_control/emg_pca9685_control.ino)

Esse sketch já faz baseline no Arduino e envia 3 colunas (`raw`, `smoothed`, `threshold`).

