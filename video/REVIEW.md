# Revisão — ClickDeck, motion social 9:16

**Formato:** 1080×1920, 30 fps, 19,9 s, sem som. A versão 16:9 (1920×1080) está em `../video-16x9`, com as mesmas cenas e tempos e o layout recomposto: texto à esquerda, foto/app à direita.

## Cenas

| Tempo | Cena | Texto | Transição de saída |
|-------|------|-------|--------------------|
| 0–2,8 s | hook (foto1, LEDs acesos) | «8 teclas.» → «Os teus atalhos.» com punch-in | whip para cima |
| 2,8–6,4 s | actions (montagem foto2/1/3/2) | «Um clique abre» + slot: programas / sites / comandos / atalhos | a tecla laranja cresce até encher o ecrã |
| 6,4–10,2 s | app (captura da app) | «A tua cor.» → «Perfis por app.»; chip Geral → Fusion 360; barra de LEDs | o laranja encolhe até à tecla 1; no fim, zoom através do ecrã da app |
| 10,2–13,2 s | usb (foto3) | «Impresso em 3D.» → «Liga por USB-C.» com punch-in na porta | dip de 3 frames |
| 13,2–16,6 s | open | «Open source.» + firmware/ · app/ · case/ + «MIT · github.com/AMCC1998/ClickDeck» → «Faz o teu.» | blur out |
| 16,6–19,9 s | end (foto2) | «ClickDeck» letra a letra, 8 pontos nas cores das capas, «Macropad USB + app Windows» | — |

Por cima de tudo há uma barra de 8 segmentos (cena progress), abaixo dos 1330 px, que acende um segmento a cada ~2,5 s. Fica na zona onde a plataforma desenha a UI.

## Decisões

- O frame 0 já mostra a foto e «8 teclas.», porque é a miniatura.
- Usei foto1–3 e a captura da app. As fotos em `originais/melhoradas` ficaram com pouco contraste e de fora.
- Todas as cores saem da app (tecla 1 = #ff7850, …). As cores do perfil «Fusion 360» na barra de LEDs são ilustrativas.

## O que foi medido

- `check` passa. Ficam dois avisos de propósito: `film_silent` (não há fonte de música configurada) e `duplicate_media_discovery_risk` (a foto2 aparece duas vezes na montagem, de propósito).
- Vi as folhas de revisão e as costuras entre cenas. Não ouvi nada, porque não há som.

## O ponto mais fraco

- O zoom da app para a cena USB: a foto chega grande, mas dentro da moldura e não em ecrã inteiro. Com mais tempo, a moldura inteira entraria escalada.
- As fotos têm 1264 px de largura, por isso os punch-ins (1,45× a 1,8×) ficam um pouco suaves.

## Para adicionar som

Põe um MP3 em `assets/` e acrescenta ao `index.html` `<audio id="bgm" class="clip" src="assets/musica.mp3" data-start="0" data-duration="19.9" data-track-index="3" data-volume="0.8" data-fade-out="0.8"></audio>`.
