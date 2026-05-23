# App Python (emg_interface)

## Entrypoint

O comando recomendado é executar o launcher na raiz:

```bash
python emg_interface.py
```

Ele chama o app real em:
- [project/emg_interface.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/emg_interface.py)

Launcher:
- [emg_interface.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/emg_interface.py)

## Módulos principais

- Captura serial:
  - [project/signal_capture.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/signal_capture.py)
- Processamento de sinal:
  - [project/signal_processing.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/signal_processing.py)
- Extração de features:
  - [project/feature_extraction.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/feature_extraction.py)
- Interpretação do estado (repouso/contração):
  - [project/emg_interpretation.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/emg_interpretation.py)
- UI Qt (tempo real):
  - [project/qt_emg_plotter.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/qt_emg_plotter.py)
- Utilidades (listar portas, autodetect, robustez na abertura):
  - [project/utils.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/utils.py)

## Fluxo de execução (simplificado)

1) `SerialSignalCapture` abre uma porta (COM) e começa a ler linhas.
2) Cada linha é parseada para 1–2 valores:
   - raw (obrigatório)
   - filtered (opcional)
3) O loop principal:
   - decide o modo (arduino/processed)
   - calcula `filtered/envelope`
   - calcula features em janelas (FFT e domínio do tempo)
   - gera `interpretation` (“repouso/contração…”) usando calibração
4) A UI consome amostras e renderiza.

## CLI (opções importantes)

Listar portas:

```bash
python emg_interface.py --list-ports
```

Executar usando uma porta específica:

```bash
python emg_interface.py --emg-port COM20 --emg-baud 115200
```

Atalhos úteis:

- `--ui qt` (padrão): UI Qt
- `--ui mpl`: UI legado em matplotlib (útil para depuração)
- `--plot-mode arduino`: usa 2 colunas (raw + filtrado) quando disponível
- `--plot-mode processed`: aplica processamento no Python

## Sobre performance

Os maiores custos de CPU costumam vir de:

- cálculo de FFT/features em janelas muito frequentes
- plot com pontos demais
- escrita em disco (logs CSV)

Mitigações implementadas:

- UI Qt consome incrementalmente (fila) e limita pontos
- escrita em CSV é criada sob demanda e pode ficar desabilitada quando não grava

## Arquivos de dados gerados

Por padrão, o repositório já possui:

- datasets de features:
  - [project/datasets/emg_features.csv](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/datasets/emg_features.csv)
- runtime log (quando gravando):
  - [project/datasets/runtime_log.csv](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/datasets/runtime_log.csv)

