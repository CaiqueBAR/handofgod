# Calibração e “leitura limpa”

## O que é calibração no nosso sistema

A calibração mede o comportamento do sinal em **repouso** para estimar:

- baseline (offset) do sinal filtrado (o “nível” quando não há contração)
- ruído (desvio padrão) do sinal em repouso

Esses valores são usados para:

- calcular envelope como “amplitude real” da contração
- normalizar thresholds e interpretar estados (repouso/contração)

Implementação:
- `SharedState.request_calibration()` e armazenamento de `calibration`:
  - [project/emg_interface.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/emg_interface.py)

## Como calibrar (passo a passo)

1) Inicie a leitura (RUN).
2) Deixe o músculo em repouso (relaxado) e sem mexer no eletrodo.
3) Menu (≡) → `Calibrate (5s)` (recomendado).

## Envelope (amplitude)

### Modo arduino (2 colunas)

Quando o Arduino já manda `raw` e `filtered` (EMA), o sistema usa:

- `filtered = emgFiltrado` (do Arduino)
- `envelope = abs(filtered - baseline_filtered)`

Isso produz um envelope “limpo”:

- repouso → envelope ~ 0
- contração → envelope sobe proporcionalmente

### Modo processed (1 coluna)

Quando o Arduino manda só `raw`, o Python aplica processamento:

- remover DC
- envelope por EMA

Implementação:
- [project/signal_processing.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/signal_processing.py)

## Frequência (pico/média)

O sistema calcula features espectrais (FFT) por janela:

- `mean_freq_hz`
- `median_freq_hz`
- `peak_freq_hz`

Implementação:
- [compute_features](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/feature_extraction.py#L57-L105)

Importante:

- “Frequência de EMG” aqui é um resumo espectral do sinal na janela.
- Não é a mesma coisa que “quantas contrações por segundo”.

## O que é “sinal limpo” na prática

Um sinal limpo depende de:

- eletrodos bem fixados (boa impedância)
- referência/terra estáveis (GND correto)
- fio curto e sem interferência
- cabo USB bom
- sketch correto e baud correto

## Ajustes finos recomendados

Se o sinal está muito “nervoso”:

- aumente alpha do filtro EMA no Arduino (ex.: 0.2 → 0.3)
- aumente o tempo de calibração (5–10s)
- use o modo `Select... -> Envelope` para observar somente a amplitude

