# Troubleshooting

Este documento foca nos problemas que mais aparecem no Windows com EMG via Serial.

## 1) “Nada aparece no gráfico”

Checklist:

- A porta serial está correta?
  - `python emg_interface.py --list-ports`
- O baud está correto?
  - para os sketches EMG deste repositório: `115200`
- A porta está ocupada?
  - feche Arduino Serial Plotter/Monitor e qualquer app de serial
- O Arduino está com o sketch correto?
  - se estiver rodando outro sketch, você vai receber texto aleatório (ex.: “DHT”)

Teste direto no terminal:

```bash
python tools/emg_serial_test.py --port COM20 --baud 115200 --seconds 5
```

Se o teste não imprime números, a UI não vai ter o que desenhar.

## 2) PermissionError(13) “Acesso negado”

Causa:

- algum programa já abriu a COM e bloqueou para outros

Como resolver:

- feche Arduino IDE → Serial Monitor/Plotter
- feche serial splitters (HHD Shared Serial Port)
- desconecte/reconecte o Arduino

## 3) FileNotFoundError(2)

Causa típica:

- COM antiga não existe mais (Windows renumerou)

Como resolver:

- `--list-ports` e use a COM correta

## 4) Saída “lixo” (caracteres estranhos)

Causas:

- baud errado
- sketch errado (outra coisa imprimindo texto)

Como diagnosticar rápido:

- rode o teste `emg_serial_test` em 115200
- se continuar ruim, teste 9600 e veja se aparece alguma mensagem legível
- quando você acha o baud correto, você passa a ver números consistentes

## 5) O gráfico “trava” ou oscila (sem constância)

Possíveis causas:

- serial chega em “burst” (buffer)
- Arduino travando/reiniciando
- cabo USB ruim
- cálculo pesado (features/FFT) muito frequente

Ações:

- desative qualquer gravação/ML/servo enquanto valida o sinal base
- use `Select... -> Raw + Filtered` e desligue Interpolate para ver a amostragem real
- use um sketch mais simples:
  - [emg_simple_stream/emg_simple_stream.ino](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/emg_simple_stream/emg_simple_stream.ino)

## 6) “Auto” escolhe a porta errada

O `auto` tenta priorizar portas USB reais e evitar portas virtuais.

Se você estiver usando splitters virtuais (HHD), o `auto` pode confundir.

Recomendação:

- rode com `--emg-port COM20` explicitamente enquanto estabiliza o setup

## 7) Checklist mínimo para uma sessão “limpa”

1) Upload do sketch EMG certo no Arduino
2) Confirme no Arduino IDE Serial Plotter que vê ondas
3) Feche o Serial Plotter
4) `python tools/emg_serial_test.py --port COM20 --baud 115200 --seconds 5`
5) `python emg_interface.py --emg-port COM20 --emg-baud 115200`
6) RUN → Calibrate (5s) em repouso

