# Setup (Windows)

Este documento cobre:

- Instalação/validação do Python
- Instalação das dependências do projeto
- Como listar e validar portas seriais (USB/COM)
- Problemas típicos no Windows (“Acesso negado”, porta inexistente, drivers CH340)

## Pré-requisitos

- Windows 10/11
- Arduino IDE 2.x (para upload do sketch e validação no Serial Plotter)
- Python 3.11+ (o projeto já foi executado com Python da Microsoft Store)
- Cabo USB de dados (muitos cabos “só carga” não funcionam)

## Instalação das dependências Python

No diretório raiz do repositório:

```bash
python -m pip install --upgrade pip
python -m pip install pyserial numpy
python -m pip install PySide6==6.9.0 pyqtgraph==0.13.7
```

Observações:

- `PySide6` + `pyqtgraph` são usados pela interface Qt.
- `scipy` é opcional (backend de filtro mais pesado). Só instale se for usar `--backend scipy`.
- `scikit-learn/joblib` são opcionais (ML). Só instale se for habilitar predição/treino.

## Listar portas seriais

Para ver as portas detectadas (COM):

```bash
python emg_interface.py --list-ports
```

O que procurar:

- Portas USB reais costumam aparecer como:
  - “USB-SERIAL CH340”
  - “Arduino Nano/Uno/Mega”
- Portas virtuais/splitters podem aparecer como:
  - “HHD Software Shared Serial Port”

## Teste rápido de leitura da Serial

Antes de abrir a interface gráfica, valide se está chegando dado na serial:

```bash
python tools/emg_serial_test.py --port COM20 --baud 115200 --seconds 5
```

Resultados esperados:

- Você deve ver linhas com números (ex.: `512` ou `512\t480.123`).
- Se não aparecer nenhuma linha: o Arduino pode não estar enviando, a porta/baud estão errados, ou a porta está ocupada.

## Erros comuns no Windows

### 1) PermissionError(13) “Acesso negado”

Isso significa que algum programa já abriu a porta e o Python não consegue usar.

Feche:

- Arduino IDE → Serial Monitor / Serial Plotter
- Qualquer “serial splitter” (HHD / com0com / etc.)
- Outros apps que usam COM (ex.: Termite, PuTTY, Serial Studio)

Depois:

- desconecte e reconecte o Arduino no USB
- rode o teste `tools/emg_serial_test.py`

### 2) FileNotFoundError “O sistema não pode encontrar o arquivo especificado”

Geralmente:

- a COM mudou (Windows renumerou a porta)
- o Arduino está desconectado

Rode `--list-ports` e use a porta correta.

### 3) Saída “lixo”/caracteres estranhos

Quase sempre é baud errado ou sketch errado no Arduino.

Exemplo:

- Seu sketch EMG usa `Serial.begin(115200)`
- Se o Python estiver em 9600 (ou vice-versa), a leitura vira “lixo”

## Driver CH340 (Arduino clones)

Se seu Arduino Nano/UNO usa CH340 e não aparece porta USB:

- Instale o driver CH340 (normalmente o Windows instala sozinho, mas pode falhar)
- Troque o cabo USB
- Troque a porta USB do PC

