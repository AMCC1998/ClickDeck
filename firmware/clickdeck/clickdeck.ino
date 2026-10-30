/*
 * ClickDeck - firmware para Arduino Pro Micro (ATmega32U4)
 *
 * - 8 botões entre o pino e GND (INPUT_PULLUP, premido = LOW). A placa aparece no PC como
 *   teclado USB e envia F13..F20.
 * - Barra de 8 LEDs WS2812 no pino 10, controlada pela app por USB (porta série virtual,
 *   linhas de texto a 115200 baud, ver handleLine).
 *
 * Bibliotecas (Gestor de Bibliotecas): Bounce2 e Adafruit NeoPixel. A Keyboard já vem com o IDE.
 */

#include <Keyboard.h>
#include <Bounce2.h>
#include <Adafruit_NeoPixel.h>

// ---- Botões -----------------------------------------------------------------

// Pino de cada botão (botão 1 = primeiro elemento).
// 8 botões: D2..D9 e F13..F20 (para 6: remove 8, 9, KEY_F19, KEY_F20 e põe NUM_BUTTONS = 6 na app).
const uint8_t BUTTON_PINS[] = {2, 3, 4, 5, 6, 7, 8, 9};

// Tecla enviada por cada botão. Tem de coincidir com a app (F13, F14, ...).
const uint8_t BUTTON_KEYS[] = {
  KEY_F13, KEY_F14, KEY_F15, KEY_F16, KEY_F17, KEY_F18, KEY_F19, KEY_F20
};

constexpr uint8_t NUM_BUTTONS = sizeof(BUTTON_PINS);
static_assert(sizeof(BUTTON_KEYS) == sizeof(BUTTON_PINS), "BUTTON_PINS e BUTTON_KEYS têm de ter o mesmo tamanho");

const uint16_t DEBOUNCE_MS = 10;

// ---- Luzes ------------------------------------------------------------------

const uint8_t LED_PIN = 10;              // DIN da barra
const uint8_t NUM_LEDS = 8;              // LED n acompanha o botão n
const uint8_t MAX_BRIGHTNESS = 120;      // limite de corrente: o USB dá 500 mA
const uint16_t FLASH_MS = 160;           // duração do clarão ao premir
const uint32_t SERIAL_BAUD = 115200;

// -----------------------------------------------------------------------------

enum LedMode : uint8_t { LED_OFF, LED_KEYS, LED_SOLID, LED_RAINBOW, LED_BREATHE };

Bounce buttons[NUM_BUTTONS];
Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);

uint8_t ledMode = LED_KEYS;
uint8_t ledBrightness = 40;              // 0..255 (a app envia o valor dela)
uint32_t solidColor = 0xFFFFFF;          // 0xRRGGBB
bool reactive = true;                    // clarão ao premir
uint32_t keyColors[NUM_LEDS] = {         // cores por omissão, a app substitui-as ao ligar
  0xFF7850, 0xFFBE46, 0x6ED278, 0x50B4F0, 0x9682FA, 0xF06EB4, 0x2DD4BF, 0xEF4444
};
unsigned long flashUntil[NUM_LEDS];

char lineBuf[24];
uint8_t lineLen = 0;
unsigned long lastFrame = 0;

uint32_t scaleColor(uint32_t c, uint8_t s) {            // s: 0..255
  uint8_t r = ((c >> 16) & 0xFF) * s / 255;
  uint8_t g = ((c >> 8) & 0xFF) * s / 255;
  uint8_t b = (c & 0xFF) * s / 255;
  return ((uint32_t)r << 16) | ((uint32_t)g << 8) | b;
}

uint32_t towardsWhite(uint32_t c, uint8_t amount) {     // amount: 0..255
  uint8_t r = (c >> 16) & 0xFF, g = (c >> 8) & 0xFF, b = c & 0xFF;
  r += (255 - r) * amount / 255;
  g += (255 - g) * amount / 255;
  b += (255 - b) * amount / 255;
  return ((uint32_t)r << 16) | ((uint32_t)g << 8) | b;
}

void renderLeds() {
  unsigned long now = millis();
  if (now - lastFrame < 20) return;
  lastFrame = now;

  strip.setBrightness(ledBrightness < MAX_BRIGHTNESS ? ledBrightness : MAX_BRIGHTNESS);

  uint16_t phase = (now / 8) % 512;                      // onda triangular para "respirar"
  uint8_t tri = phase < 256 ? phase : 511 - phase;
  uint8_t breathe = 30 + (uint16_t)tri * 225 / 255;

  for (uint8_t i = 0; i < NUM_LEDS; i++) {
    uint32_t c = 0;
    switch (ledMode) {
      case LED_KEYS:    c = keyColors[i]; break;
      case LED_SOLID:   c = solidColor; break;
      case LED_RAINBOW: c = strip.ColorHSV((uint16_t)(now * 6) + i * (65536UL / NUM_LEDS), 255, 255); break;
      case LED_BREATHE: c = scaleColor(keyColors[i], breathe); break;
      default: break;                                    // LED_OFF
    }
    if (reactive && ledMode != LED_OFF && (long)(flashUntil[i] - now) > 0) {
      c = towardsWhite(c, 200);
    }
    strip.setPixelColor(i, c);
  }
  strip.show();
}

// Comandos (uma linha de texto cada):
//   ?        -> responde "CLICKDECK 1" (a app usa isto para encontrar a porta certa)
//   M<0-4>   modo: 0 desligadas, 1 cores das teclas, 2 cor única, 3 arco-íris, 4 respirar
//   B<0-255> brilho
//   C<rrggbb> cor única
//   K<1-8><rrggbb> cor do LED/tecla n
//   R<0|1>   clarão ao premir
void handleLine(const char *s) {
  switch (s[0]) {
    case '?': Serial.println(F("CLICKDECK 1")); break;
    case 'M': { int v = atoi(s + 1); ledMode = v < 0 ? 0 : (v > LED_BREATHE ? LED_BREATHE : v); } break;
    case 'B': { int v = atoi(s + 1); ledBrightness = v < 0 ? 0 : (v > 255 ? 255 : v); } break;
    case 'C': solidColor = strtoul(s + 1, NULL, 16) & 0xFFFFFF; break;
    case 'R': reactive = atoi(s + 1) != 0; break;
    case 'K': {
      int k = s[1] - '1';
      if (k >= 0 && k < NUM_LEDS) keyColors[k] = strtoul(s + 2, NULL, 16) & 0xFFFFFF;
    } break;
    default: break;
  }
}

void readSerial() {
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n' || ch == '\r') {
      if (lineLen) {
        lineBuf[lineLen] = 0;
        handleLine(lineBuf);
        lineLen = 0;
      }
    } else if (lineLen < sizeof(lineBuf) - 1) {
      lineBuf[lineLen++] = ch;
    }
  }
}

void setup() {
  for (uint8_t i = 0; i < NUM_BUTTONS; i++) {
    buttons[i].attach(BUTTON_PINS[i], INPUT_PULLUP);
    buttons[i].interval(DEBOUNCE_MS);
  }
  Keyboard.begin();
  Serial.begin(SERIAL_BAUD);             // não esperar pela porta: o teclado tem de funcionar sem a app
  strip.begin();
  strip.show();
}

void loop() {
  for (uint8_t i = 0; i < NUM_BUTTONS; i++) {
    buttons[i].update();
    if (buttons[i].fell()) {             // HIGH -> LOW: premido
      Keyboard.press(BUTTON_KEYS[i]);
      if (i < NUM_LEDS) flashUntil[i] = millis() + FLASH_MS;
    } else if (buttons[i].rose()) {      // LOW -> HIGH: libertado
      Keyboard.release(BUTTON_KEYS[i]);
    }
  }
  readSerial();
  renderLeds();
}
