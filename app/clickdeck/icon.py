"""Ícone do ClickDeck: um macropad com 6 teclas coloridas (desenhado em código)."""

from PIL import Image, ImageDraw

from .config import COLORS


def _lighten(rgb, t):
    return tuple(round(c + (255 - c) * t) for c in rgb)


def make_icon(size: int = 256) -> Image.Image:
    s = 4  # supersampling para bordas suaves
    n = size * s
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # corpo do macropad com um degradê vertical subtil
    body = Image.new("RGBA", (n, n))
    bd = ImageDraw.Draw(body)
    for y in range(n):
        t = y / n
        bd.line([(0, y), (n, y)], fill=(int(44 - 18 * t), int(48 - 18 * t), int(64 - 24 * t), 255))
    mask = Image.new("L", (n, n), 0)
    ImageDraw.Draw(mask).rounded_rectangle((n * 0.04, n * 0.04, n * 0.96, n * 0.96), radius=n * 0.2, fill=255)
    img.paste(body, (0, 0), mask)
    d.rounded_rectangle((n * 0.04, n * 0.04, n * 0.96, n * 0.96), radius=n * 0.2,
                        outline=(255, 255, 255, 40), width=max(1, n // 128))

    # 6 teclas (3x2), cada uma com sombra, topo mais claro
    pad, gap = n * 0.15, n * 0.05
    kw = (n - 2 * pad - 2 * gap) / 3
    kh = (n - 2 * pad - gap) / 2 * 0.86
    top = (n - (2 * kh + gap)) / 2
    for i in range(6):
        rgb = tuple(int(COLORS[i][j:j + 2], 16) for j in (1, 3, 5))
        x = pad + (i % 3) * (kw + gap)
        y = top + (i // 3) * (kh + gap)
        d.rounded_rectangle((x, y + n * 0.025, x + kw, y + kh + n * 0.025), radius=n * 0.05,
                            fill=tuple(int(c * 0.55) for c in rgb) + (255,))
        d.rounded_rectangle((x, y, x + kw, y + kh), radius=n * 0.05, fill=rgb + (255,))
        d.rounded_rectangle((x + kw * 0.12, y + kh * 0.1, x + kw * 0.88, y + kh * 0.38),
                            radius=n * 0.03, fill=_lighten(rgb, 0.35) + (255,))
    return img.resize((size, size), Image.LANCZOS)


def save_ico(path: str) -> None:
    make_icon(256).save(path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    save_ico("clickdeck.ico")
