# Opcionais: API HTTP, Servo, ML

Este documento descreve recursos que existem no código, mas podem estar desabilitados por padrão dependendo do modo de execução.

## 1) API HTTP (opcional)

O servidor HTTP existe em:

- [project/emg_interface.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/emg_interface.py)

Ele não sobe por padrão. Para ativar:

```bash
python emg_interface.py --http --http-host 127.0.0.1 --http-port 8000
```

Endpoints:

- `GET /health` → `{"ok": true}`
- `GET /ports` → lista portas seriais detectadas
- `GET /latest` → última amostra (raw/filtered/envelope/features/interpretation)
- `GET /history` → histórico em memória
- `GET /stream` → SSE (event-stream) com eventos `emg`
- `GET /set_label?label=...` → define rótulo ativo
- `GET /recording?on=0|1` → habilita gravação (features)
- `GET /servo?on=0|1` → habilita envio para servos
- `GET /config?key=...&value=...` → envia `key=value` para o Arduino via serial (quando o sketch entende isso)

## 2) Controle de Servo via Serial (opcional)

Módulo:

- [project/servo_controller.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/servo_controller.py)

Como funciona:

- o Python abre uma porta serial “servo” (pode ser outro Arduino)
- quando a predição gera um rótulo e `servo_enabled=True`, o Python envia um comando por linha

Mapeamento padrão de rótulo → comando:

```text
mao_aberta  -> OPEN_HAND
mao_fechada -> CLOSE_HAND
flexao      -> FLEX
extensao    -> EXTEND
```

Importante:

- o Arduino que recebe comandos precisa interpretar essas strings (protocolo ASCII).
- existe também um sketch no repo que usa comandos numéricos (1..11):
  - [hand_servo_control/hand_servo_control.ino](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/hand_servo_control/hand_servo_control.ino)
- se você for usar esse sketch (numérico), o `DEFAULT_LABEL_TO_COMMAND` deve ser ajustado para enviar números, ou o sketch deve ser ajustado para aceitar strings.

## 3) ML (treino e predição)

Arquivos:

- Predição:
  - [project/model_predict.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/model_predict.py)
- Treinamento:
  - [project/model_training.py](file:///c:/Users/super/OneDrive/Área%20de%20Trabalho/handsOfGod/project/model_training.py)

Dependências (opcionais):

```bash
python -m pip install joblib scikit-learn
```

Conceito:

- a cada janela, o sistema calcula um `FeatureVector`
- o classificador (Pipeline sklearn) retorna:
  - `label`
  - `confidence`
  - probabilidades por classe (quando disponível)

Observação prática:

- ML pode aumentar o custo de CPU e o tempo de import no Windows.
- por isso, o código tenta carregar modelo de forma “lazy” (apenas quando habilita).

