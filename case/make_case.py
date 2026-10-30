"""Caixa do ClickDeck (parametrica): base com a Pro Micro + placa superior com encaixes MX.

Gera ficheiros STEP (e STL) de: base, placa superior e montagem completa.

    pip install build123d
    python make_case.py              # 3x2 = 6 botoes
    python make_case.py --cols 4     # 4x2 = 8 botoes

Eixos: X para a direita, Y para o fundo (longe de ti), Z para cima. Unidades em mm.
Origem = canto interior frente-esquerdo da cavidade. O USB-C sai pela parede da direita.
"""

import argparse
from pathlib import Path

from build123d import Axis, Box, Compound, Cylinder, Pos, export_step, export_stl, fillet

# ---- Parametros ---------------------------------------------------------------
PITCH = 19.05        # distancia entre centros dos switches (padrao MX / keycaps 1U)
SW_CUT = 14.1        # furo quadrado do switch (14.0 nominal + folga de impressao)
PLATE_T = 1.5        # espessura da placa superior (os clips MX pedem <= 1.5-1.6)
WALL = 2.4           # espessura das paredes
FLOOR = 2.0          # espessura do fundo
INNER_H = 12.0       # altura interior (fundo -> parte de baixo da placa)
MARGIN = 1.5         # folga entre a grelha de switches e as paredes
CORNER_R = 3.0       # raio dos cantos exteriores

BOARD_L, BOARD_W, BOARD_T = 33.5, 18.2, 1.6   # Pro Micro USB-C (medir a tua e ajustar)
USB_W, USB_H = 9.0, 3.2                       # conector USB-C
USB_OVERHANG = 0.8                            # quanto o conector sai alem da placa
SLOT_W, SLOT_H = 13.0, 7.5                    # abertura na parede (folga para a ficha)
RAIL_H = 2.0                                  # apoios sob a placa (deixa soldar por baixo)

BOSS_R = 3.2         # raio dos pilares dos parafusos (M2 auto-roscante)
PILOT_D = 1.8        # furo piloto no pilar
CLEAR_D = 2.2        # furo de passagem na placa superior


def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def build(cols: int, rows: int):
    wi = cols * PITCH + 2 * MARGIN
    grid_end = MARGIN + rows * PITCH
    y0 = grid_end + 0.5                       # inicio da faixa da placa Arduino
    by0 = y0 + 1.4                            # y da placa Arduino (borda da frente)
    by1 = by0 + BOARD_W
    di = by1 + 3.7                            # profundidade interior (deixa espaco ao pilar de tras)
    h = FLOOR + INNER_H

    ox0, ox1, oy0, oy1 = -WALL, wi + WALL, -WALL, di + WALL
    corners = [(0, 0), (wi, 0), (0, di), (wi, di)]

    # ---- base ------------------------------------------------------------------
    shell = fillet(box(ox0, ox1, oy0, oy1, 0, h).edges().filter_by(Axis.Z), CORNER_R)
    base = shell - box(0, wi, 0, di, FLOOR, h + 1)
    for cx, cy in corners:
        base += Pos(cx, cy, (FLOOR + h) / 2) * Cylinder(BOSS_R, h - FLOOR)
    # recorte da cavidade nos cantos exteriores nao e necessario: os pilares ficam dentro da parede
    base = base & box(ox0, ox1, oy0, oy1, 0, h)
    for cx, cy in corners:
        base -= Pos(cx, cy, h - 4) * Cylinder(PILOT_D / 2, 8.1)

    # Arduino: USB-C encostado a parede da direita
    bx0 = wi - BOARD_L
    z_board = FLOOR + RAIL_H
    for ya, yb in ((by0, by0 + 2.5), (by1 - 2.5, by1)):               # apoios por baixo
        base += box(bx0 + 2.0, wi - 0.5, ya, yb, FLOOR - 0.1, z_board)
    base += box(bx0, wi - 4.5, by0 - 1.4, by0 - 0.4, FLOOR - 0.1, z_board + 4)   # guia da frente
    base += box(bx0, wi - 4.5, by1 + 0.4, by1 + 1.4, FLOOR - 0.1, z_board + 4)   # guia de tras
    for ya, yb in ((by0, by0 + 4.0), (by1 - 4.0, by1)):               # batente do lado esquerdo
        base += box(bx0 - 1.6, bx0 - 0.4, ya, yb, FLOOR - 0.1, z_board + 4)
    # abertura do USB-C
    yc = (by0 + by1) / 2
    zc = z_board + BOARD_T + USB_H / 2
    base -= box(wi - 0.5, wi + WALL + 1, yc - SLOT_W / 2, yc + SLOT_W / 2, zc - SLOT_H / 2, zc + SLOT_H / 2)

    # ---- placa superior ---------------------------------------------------------
    plate = fillet(box(ox0, ox1, oy0, oy1, h, h + PLATE_T).edges().filter_by(Axis.Z), CORNER_R)
    centers = [(MARGIN + (c + 0.5) * PITCH, MARGIN + (r + 0.5) * PITCH)
               for r in range(rows) for c in range(cols)]
    for sx, sy in centers:
        plate -= box(sx - SW_CUT / 2, sx + SW_CUT / 2, sy - SW_CUT / 2, sy + SW_CUT / 2, h - 1, h + PLATE_T + 1)
    for cx, cy in corners:
        plate -= Pos(cx, cy, h + PLATE_T / 2) * Cylinder(CLEAR_D / 2, PLATE_T + 2)

    # ---- verificacoes de interferencia --------------------------------------------
    checks = {}
    sw_body = Compound([box(sx - 7, sx + 7, sy - 7, sy + 7, h - 5.0, h) for sx, sy in centers])
    checks["switches x base"] = (base & sw_body).volume
    pcb = box(bx0, wi, by0, by1, z_board, z_board + BOARD_T)
    usb = box(wi - 8, wi + USB_OVERHANG, yc - USB_W / 2, yc + USB_W / 2, z_board + BOARD_T, z_board + BOARD_T + USB_H)
    checks["Arduino x base"] = (base & pcb).volume + (base & usb).volume
    checks["placa x base"] = (plate & base).volume
    return base, plate, checks, (ox1 - ox0, oy1 - oy0, h + PLATE_T)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--rows", type=int, default=2)
    args = ap.parse_args()
    out = Path(__file__).parent
    n = args.cols * args.rows
    base, plate, checks, size = build(args.cols, args.rows)
    print(f"{n} botoes, exterior {size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm")
    for name, vol in checks.items():
        print(f"  interferencia {name}: {vol:.3f} mm3")
    assembly = Compound([base, plate])
    for part, name in ((base, "base"), (plate, "placa"), (assembly, "montagem")):
        stem = out / f"clickdeck_{n}btn_{name}"
        export_step(part, str(stem) + ".step")
        export_stl(part, str(stem) + ".stl")
    print("Ficheiros escritos em", out)
