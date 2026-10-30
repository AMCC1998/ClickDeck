"""Keycaps do ClickDeck para switches MX (haste em cruz), parametricas.

    python make_keycaps.py

Gera clickdeck_keycap_1u.step/.stl (uma capa) e folhas de impressao para 6 e 8 capas.
Imprimir de pe (haste a apontar para cima), com o furo da cruz virado para a mesa
ou usar suportes; camada 0,12-0,16 mm da melhor haste. Unidades em mm.
"""

from pathlib import Path

from build123d import (Axis, Box, BuildPart, BuildSketch, Compound, Cylinder, Plane, Pos,
                       RectangleRounded, Sphere, export_step, export_stl, fillet, loft)

# ---- Parametros ---------------------------------------------------------------
BASE = 18.0          # largura em baixo (cabe no passo de 19,05 mm com 1 mm de folga)
TOP = 15.2           # largura em cima
HEIGHT = 9.0
WALL = 1.2
TOP_T = 1.6          # espessura do topo
BASE_R, TOP_R = 2.4, 3.2
EDGE_FILLET = 1.0
DISH_R, DISH_DEPTH = 30.0, 0.8     # concavidade no topo para o dedo

STEM_D = 5.5
CROSS_L, CROSS_W = 4.2, 1.4        # cruz MX 4,0 x 1,3 + folga de impressao
STEM_BOTTOM = 2.9                  # altura do fundo da haste (a contar da base da capa)
RIB_W = 0.8


def _loft(w0, r0, w1, r1, z1, z0=0.0):
    with BuildPart() as p:
        with BuildSketch(Plane.XY.offset(z0)):
            RectangleRounded(w0, w0, r0)
        with BuildSketch(Plane.XY.offset(z1)):
            RectangleRounded(w1, w1, r1)
        loft()
    return p.part


def keycap():
    outer = _loft(BASE, BASE_R, TOP, TOP_R, HEIGHT)
    outer = fillet(outer.faces().sort_by(Axis.Z)[-1].edges(), EDGE_FILLET)

    z_in = HEIGHT - TOP_T
    shrink = (BASE - TOP) * (z_in / HEIGHT)
    inner = _loft(BASE - 2 * WALL, BASE_R - WALL, BASE - shrink - 2 * WALL, TOP_R - WALL, z_in, z0=-0.01)
    cap = outer - inner

    # costelas + haste, ligadas ao teto
    stem_h = z_in - STEM_BOTTOM + 0.2
    stem = Pos(0, 0, STEM_BOTTOM + stem_h / 2) * Cylinder(STEM_D / 2, stem_h)
    ribs = Pos(0, 0, 5.2) * Box(BASE, RIB_W, 2.6) + Pos(0, 0, 5.2) * Box(RIB_W, BASE, 2.6)
    cap += (stem + ribs) & outer

    # cruz MX
    cross_top = z_in - 0.5
    cut_h = cross_top - STEM_BOTTOM + 0.1
    zc = STEM_BOTTOM - 0.1 + cut_h / 2
    cap -= Pos(0, 0, zc) * Box(CROSS_L, CROSS_W, cut_h) + Pos(0, 0, zc) * Box(CROSS_W, CROSS_L, cut_h)

    # concavidade
    cap -= Pos(0, 0, HEIGHT + DISH_R - DISH_DEPTH) * Sphere(DISH_R)
    return cap


def sheet(cap, n, cols, spacing=22.0):
    parts = [Pos((i % cols) * spacing, -(i // cols) * spacing, 0) * cap for i in range(n)]
    return Compound(parts)


if __name__ == "__main__":
    out = Path(__file__).parent
    cap = keycap()
    print(f"keycap: volume {cap.volume:.0f} mm3, caixa {cap.bounding_box().size.X:.1f} x "
          f"{cap.bounding_box().size.Y:.1f} x {cap.bounding_box().size.Z:.1f} mm, valida={cap.is_valid}")
    for name, part in (("keycap_1u", cap), ("keycaps_6", sheet(cap, 6, 3)), ("keycaps_8", sheet(cap, 8, 4))):
        stem = out / f"clickdeck_{name}"
        export_step(part, str(stem) + ".step")
        export_stl(part, str(stem) + ".stl")
    print("Ficheiros escritos em", out)
