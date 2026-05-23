# Interpretação (repouso / contração leve / contração forte)

## Objetivo

Você descreveu o comportamento esperado de um EMG saudável em 3 estados. O sistema implementa uma interpretação automática desses estados a partir de features por janela.

Arquivo:
- [project/emg_interpretation.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/emg_interpretation.py)

O resultado é anexado em cada amostra como:

- `status.interpretation = {"state": "...", "activation": ..., "note": ...}`

## Como funciona

1) O loop calcula features em uma janela de tempo:
   - RMS, MAV, zero crossings, frequências (mean/peak)
2) A interpretação usa a calibração para obter `noise_filtered_std`
3) Define um índice de ativação:

```
activation = rms / noise_filtered_std
```

4) Mapeia para estados (heurística inicial):

- `repouso`:
  - ativação baixa e MAV baixo
- `contracao_leve`:
  - ativação moderada
- `contracao_forte`:
  - ativação alta

5) Notas adicionais:

- `ruido_em_repouso`:
  - indica atividade “estranha” durante repouso (muito ZC / frequências altas)
- `sinal_fraco_ou_instavel`:
  - frequências muito baixas mesmo em contração (pode ser janela pequena/instabilidade/baixa qualidade)

## Como usar na prática

1) Clique RUN
2) Faça `Calibrate (5s)` em repouso
3) Observe no topo o estado (ex.: `repouso x1.7`)
4) Faça contração leve:
   - esperado: `contracao_leve x...`
5) Faça contração forte:
   - esperado: `contracao_forte x...`

## Limitações importantes

- Não é diagnóstico médico.
- O sistema atual usa heurísticas (thresholds) e depende muito:
  - do seu amplificador
  - do posicionamento de eletrodos
  - do ruído do ambiente
  - da janela e passo das features

## Como ajustar (tuning)

Se estiver “muito sensível” (repouso vira contração):

- calibre com 5–10s em repouso
- aumente os thresholds em `interpret_emg()` (activation)

Se estiver “pouco sensível” (contração forte ainda vira leve):

- calibre corretamente em repouso
- reduza os thresholds de activation

Próximo passo recomendado para evoluir:

- gravar dataset rotulado (repouso/leve/forte)
- treinar um classificador simples (SVM/RandomForest) usando as features já existentes

