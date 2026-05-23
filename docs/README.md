# handsOfGod — Documentação

Este repositório implementa um sistema de aquisição e interpretação de sinais de EMG (eletromiografia) com:

- Arduino (Nano/UNO) lendo o eletrodo no pino A0 e enviando dados via Serial
- Python lendo a Serial, processando o sinal e exibindo uma interface em tempo real (Qt)
- (Opcional) controle de servos e treinamento/predição via ML

## Comece por aqui

1) Setup e instalação (Windows):
- [01_setup_windows.md](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/docs/01_setup_windows.md)

2) Arduino (sketch EMG no A0 e formato de dados):
- [02_arduino_emg.md](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/docs/02_arduino_emg.md)

3) Aplicativo Python (CLI e fluxo de execução):
- [03_python_app.md](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/docs/03_python_app.md)

4) Interface Qt (igual ao “Serial Plotter”-style do print):
- [04_ui_qt.md](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/docs/04_ui_qt.md)

5) Calibração e “leitura limpa” (baseline/ruído/envelope):
- [05_calibracao_e_sinal.md](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/docs/05_calibracao_e_sinal.md)

6) Interpretação do EMG (repouso/contração leve/contração forte):
- [06_interpretacao.md](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/docs/06_interpretacao.md)

7) Troubleshooting (porta COM, baud, dados “lixo”, travamentos):
- [07_troubleshooting.md](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/docs/07_troubleshooting.md)

8) Recursos opcionais (API HTTP, servos, ML):
- [08_opcionais_api_servo_ml.md](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/docs/08_opcionais_api_servo_ml.md)

## Arquitetura (visão geral)

- Arduino envia um fluxo contínuo via Serial em `115200`
  - formato mais comum: `raw<TAB>filtered` (2 colunas) ou `raw` (1 coluna)
- Python lê a Serial, faz processamento leve e calcula features por janela
- UI Qt renderiza os sinais em tempo real e mostra estado interpretado

Arquivos principais:
- App Python: [project/emg_interface.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/emg_interface.py)
- UI Qt: [project/qt_emg_plotter.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/qt_emg_plotter.py)
- Captura Serial: [project/signal_capture.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/signal_capture.py)
- Features: [project/feature_extraction.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/feature_extraction.py)
- Interpretação (estados): [project/emg_interpretation.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/emg_interpretation.py)

