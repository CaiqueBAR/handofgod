# Interface Qt (tempo real)

Arquivo:
- [project/qt_emg_plotter.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/qt_emg_plotter.py)

Objetivo:

- Reproduzir um layout “Serial Plotter-style” (tema escuro) com RUN/STOP, seleção de porta e plot em tempo real

## Como abrir

```bash
python emg_interface.py --emg-port COM20 --emg-baud 115200
```

Depois:

- clique **RUN** para começar a ler e plotar
- clique **STOP** para parar e liberar a porta serial

## Barra superior

- Indicador de conexão:
  - formato: `/serial/<porta>/<baud> (connected|disconnected)`
- Estado interpretado:
  - exemplo: `repouso x1.8` ou `contracao_forte x12.3`
- Toggle **Interpolate**:
  - ligado: linha contínua
  - desligado: pontos (útil para ver “bursts”/instabilidade no stream)
- Botão **RUN/STOP**
- Menu (≡)

## Menu (≡)

### Refresh ports

Atualiza a lista de portas detectadas no Windows.

### Port / Baud

Seleciona a porta e o baud.

Recomendação:

- Use a porta USB do Arduino (ex.: “USB-SERIAL CH340”)
- Para o sketch EMG padrão: `115200`

### Calibrate

- `Calibrate (2s)` ou `Calibrate (5s)`
- Durante a calibração, mantenha o músculo em repouso e não mexa no sensor.

O objetivo é medir:

- baseline (offset) em repouso
- ruído (desvio padrão) em repouso

Isso melhora:

- cálculo de envelope (amplitude real da contração)
- estabilidade da interpretação (repouso/contração)

## Plot

O plot é controlado pelo dropdown **Select...** (barra inferior).

Opções:

- Raw + Filtered
- Envelope
- Peak Frequency (Hz)
- Mean Frequency (Hz)

## Barra inferior

### Type Message + SEND

Permite enviar uma mensagem/linha para o Arduino (para sketches que aceitem comandos via Serial).

### New Line

Escolhe qual “fim de linha” usar no envio:

- New Line / LF (`\n`)
- CRLF (`\r\n`)
- None (sem newline)

### Select...

Escolhe qual sinal desenhar no plot.

## Travamentos e constância

Se o gráfico travar, normalmente é por:

- Porta COM ocupada (Acesso negado)
- Sketch errado / baud errado (dados viram lixo)
- Stream chegando em “burst” (cabo ruim, buffer serial, travamento do Arduino)

Checklist rápido:

- Fechar Serial Plotter/Monitor
- Rodar `python tools/emg_serial_test.py --port COM20 --baud 115200 --seconds 5`

