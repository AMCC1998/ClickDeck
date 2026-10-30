# ClickDeck

Macropad USB com 8 botões (Arduino Pro Micro) e uma app Windows para escolher o que cada botão faz, com uma barra de 8 LEDs controlada a partir do PC. Inclui o firmware, a app, a caixa e as capas para imprimir em 3D.

## Funcionalidades

- 8 botões que a Pro Micro envia como teclado USB (F13–F20); a app trata-os como atalhos globais, sem administrador.
- Cada botão pode abrir um programa ou ficheiro, um site, correr um comando, enviar um atalho de teclado, ou abrir/focar uma app.
- **Perfis por aplicação:** as teclas mudam sozinhas conforme a janela que está à frente (por exemplo, outras ações no Fusion 360).
- Nome e cor da capa por tecla, para coincidir com as capas impressas de várias cores.
- **Barra de LEDs WS2812** controlada pela app: cores das teclas, uma cor por LED, cor única, arco-íris, respirar, brilho e clarão ao premir.
- Ícone na bandeja, início com o Windows, uma só instância, seletor de porta COM.
- Caixa e capas MX em STEP/STL (6 e 8 botões), geradas por scripts Python.

## Estado

- Testado: arranque da app, simulação, ações, perfis, deteção da placa e envio das cores (resposta `CLICKDECK 1` na porta série).
- Por confirmar em hardware completo: botões soldados na caixa e a barra de LEDs montada. A caixa ainda não tem sítio para a barra.
- O firmware não foi compilado fora do Arduino IDE; precisa das bibliotecas Bounce2 e Adafruit NeoPixel.

## Material e ligações

- 1 × Arduino Pro Micro (ATmega32U4) e cabo USB (dados)
- 8 × switches mecânicos (MX)
- 1 × barra de 8 LEDs WS2812 (Mateksys 2812-8slim), opcional (só 2 contactos elétricos); sem resistências nem díodos

Um contacto de cada switch vai ao pino indicado e o outro a um **GND comum**. O firmware usa `INPUT_PULLUP` (premido = LOW).

| Botão | Pino | Tecla enviada |
|-------|------|---------------|
| 1 | D2 | F13 |
| 2 | D3 | F14 |
| 3 | D4 | F15 |
| 4 | D5 | F16 |
| 5 | D6 | F17 |
| 6 | D7 | F18 |
| 7 | D8 | F19 |
| 8 | D9 | F20 |

```
 Pro Micro (USB para cima)        Cada switch (2 contactos usados)

   TXO  [ ]  [ ] RAW
   RXI  [ ]  [ ] GND                 pino ──┐
   GND  [ ]  [ ] RST                        ○ ── switch ──○
   GND  [ ]  [ ] VCC                              │
    D2  [x]  [ ] A3                    GND comum ─┘
    D3  [x]  [ ] A2
    D4  [x]  [ ] A1
    D5  [x]  [ ] A0
    D6  [x]  [ ] D15
    D7  [x]  [ ] D14
    D8  [x]  [ ] D16
    D9  [x]  [ ] D10
```

Botão 1 → D2, botão 2 → D3, … botão 8 → D9. Os outros 8 terminais vão todos ao mesmo fio de GND (ligado a um dos pinos GND ao lado do D2). Sem resistências nem díodos.

Barra de LEDs WS2812 (Mateksys 2812-8slim, 8 LEDs), fios como na foto:

| Fio | Marcação na barra | Liga a |
|-----|-------------------|--------|
| preto | G | GND (qualquer pino GND da Pro Micro) |
| vermelho | 5V | RAW (os 5 V do USB) |
| azul | DIN | D10 (opcional: resistência de 330 Ω pelo meio) |
| roxo | DO | não ligar (isolar a ponta com fita) |

O LED n acompanha o botão n. O firmware limita o brilho para a barra não passar de ~250 mA (o USB dá 500 mA). A Pro Micro tem de ser de 5 V; numa de 3,3 V o sinal de dados fica no limite.

Os pinos e as teclas estão em constantes no topo de [firmware/clickdeck/clickdeck.ino](firmware/clickdeck/clickdeck.ino).

## Carregar o firmware

1. Instala o [Arduino IDE](https://www.arduino.cc/en/software).
2. Biblioteca **Bounce2**: `Sketch → Include Library → Manage Libraries…`, procura «Bounce2» (Thomas O Fredericks) e instala. Instala também **Adafruit NeoPixel** (Adafruit). A biblioteca `Keyboard` já vem com o IDE.
3. `Tools → Board`: escolhe **Arduino Leonardo** (serve para a Pro Micro de 5 V / 16 MHz). Para a versão de 3,3 V / 8 MHz instala o pacote *SparkFun AVR Boards* e escolhe *SparkFun Pro Micro* com o processador correto.
4. Liga a placa por USB e escolhe a porta em `Tools → Port`.
5. Abre `firmware/clickdeck/clickdeck.ino` e carrega em **Upload**.
6. Se o upload falhar (a Pro Micro muda de porta ao fazer reset), carrega no Upload e **faz curto-circuito RST–GND duas vezes seguidas** durante a mensagem «Uploading…».
7. Teste: abre o Bloco de Notas, carrega num botão e confirma que não aparece nada (F13–F20 não escrevem texto) — a verificação a sério é feita pela app.

## Correr a app

Requer Python 3.11+ no Windows.

```bash
cd app
pip install -r requirements.txt
python main.py
```

- A janela mostra as 8 teclas desenhadas (acendem quando carregas no botão físico). **Clica numa tecla** para a configurar no painel da direita: nome, cor e o que faz (programa/ficheiro, site, comando, atalho de teclado, abrir ou focar app). **Duplo clique** numa tecla experimenta-a; o botão **Testar** faz o mesmo. Nos atalhos, o botão ⏺ grava a combinação que premires.
- As alterações são guardadas automaticamente. Fechar a janela deixa a app na bandeja (clica no ícone para reabrir, ou «Sair» no menu).
- Só corre uma instância: se abrires o ClickDeck outra vez, a janela da que já está aberta aparece (a porta da placa e as teclas F13–F20 só podem ter um dono).
- **Luzes:** o cartão «Luzes» controla a barra de LEDs (modo, brilho, cor, «acender ao premir»). No modo «Cores das teclas» cada LED mostra a cor da capa da tecla correspondente; em «Cores personalizadas» escolhes a cor de cada LED (cliques nos círculos 1–8); «Cor única» usa o botão «Cor». O seletor «Porta» (⟳ para atualizar) permite escolher a porta COM se a deteção automática não a encontrar. A app fala com a placa pela porta série USB (procura sozinha a porta da Arduino/SparkFun e confirma que é o ClickDeck); se não houver barra ou firmware com luzes, só mostra o aviso. Não funciona no modo «Série».
- **Perfis por app:** o seletor «Perfil» (＋ novo, ✎ renomear, 🗑 apagar) permite ter teclas diferentes para cada programa. O perfil «Geral» é o de base; num perfil novo usa «Detetar» (muda para a app em 4 segundos) para dizer quando fica ativo, por exemplo `Fusion360.exe`. Uma tecla deixada vazia nesse perfil faz o mesmo que no Geral. A app muda de perfil sozinha conforme a janela que estiver à frente.
- Modo **Simulação** (no seletor «Modo»): não escuta hardware; usa o duplo clique nas teclas.
- Por omissão: botão 1 abre `https://claude.ai/new` e botão 2 abre `calc.exe`.
- A configuração fica em `%APPDATA%\ClickDeck\config.json`. «Iniciar com o Windows» escreve em `HKCU\...\Run` (sem administrador) e arranca já na bandeja.
- Modo HID: a app regista F13–F20 como hotkeys globais (`RegisterHotKey`, sem administrador). Se outra app já as usa, a barra de estado avisa quais falharam.
- Modo Série: serve para placas sem USB nativo (Uno/Nano) que enviem `D1`…`D8` / `U1`…`U8` a 9600 baud. Com a Pro Micro usa o modo HID.

## Protocolo das luzes

A app e o firmware falam por linhas de texto na porta série virtual USB (115200 baud, terminadas em `
`):

| Comando | Efeito |
|---------|--------|
| `?` | a placa responde `CLICKDECK 1` (a app usa isto para a encontrar) |
| `M0`…`M4` | modo: 0 desligado, 1 cores das teclas, 2 cor única, 3 arco-íris, 4 respirar |
| `B0`…`B255` | brilho |
| `Crrggbb` | cor única (hex) |
| `K1`…`K8` + `rrggbb` | cor do LED n |
| `R0` / `R1` | acender ao premir desligado / ligado |

## Caixa 3D e capas

Em `case/` (STEP e STL): `clickdeck_8btn_base/placa/montagem` (8 botões, 4×2) e `clickdeck_keycaps_8` (folha de capas). Também existem as versões de 6 botões. Parâmetros nos scripts `make_case.py` e `make_keycaps.py` (`pip install build123d`).

## Gerar um .exe

```bash
cd app
pip install pyinstaller
pyinstaller --noconsole --onefile --name ClickDeck main.py
```

O executável fica em `app/dist/ClickDeck.exe`. «Iniciar com o Windows» passa a apontar para ele.

## Estrutura

```
firmware/clickdeck/clickdeck.ino   firmware da Pro Micro
app/main.py                 arranque e ligação dos módulos
app/clickdeck/config.py     JSON em %APPDATA%
app/clickdeck/actions.py    execução das ações
app/clickdeck/listener.py   hotkeys F13–F20 / série / simulação
app/clickdeck/gui.py        janela de configuração
app/clickdeck/tray.py       ícone da bandeja
app/clickdeck/autostart.py  iniciar com o Windows
app/clickdeck/leds.py       controlo da barra de LEDs pela porta série
app/clickdeck/foreground.py janela ativa (perfis por aplicação)
app/clickdeck/singleton.py  uma só instância
app/clickdeck/icon.py       ícone da app
case/                       caixa e capas (STEP/STL) e scripts que as geram
```
