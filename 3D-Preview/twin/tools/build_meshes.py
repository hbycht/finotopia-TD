"""Erzeugt die Fixture-Meshes als PLY (float-Vertexfarben) nach twin/meshes/.

Aufruf:  python3 build_meshes.py [twin-ordner]

Konventionen (lokale Achsen, Einheit m):
  mh_yoke.ply  Buegel, Aufhaengepunkt im Ursprung, haengt nach -y.  Dreht per Instancing um y (Pan).
  mh_head.ply  Kopf, Zentrum im Ursprung, Linse zeigt nach -y.       Instancing: rotate-to-vector, forward = negy.
  beam.ply     offener Zylinder, Radius 1, von y=0 bis y=-1. Die Aufweitung (Startradius an der Linse ->
               Endradius) rechnet beam.glsl (uStart). Instancing: sx=sz=Endradius, sy=Laenge.
  shade.ply    Industrieschirm (Halbkugel-Schuessel), Oeffnung zeigt nach +z, Durchmesser 1.
  bulb.ply     laengliches Ellipsoid (Bulb), Durchmesser 1, Hoehe 1.6.
  ring_seg.ply ein Viertel des LED-Rings vor der Linse (Kreisbogen um +x, -38..38 Grad, Ebene y=-0.135).
               Instancing: Kopf-Orientierung * Ry(45 + 90*k) fuer Segment k.
"""
import math, sys
from pathlib import Path

base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
out_dir = base / "meshes"
out_dir.mkdir(exist_ok=True)


class Mesh:
    def __init__(self):
        self.v, self.f = [], []

    def quad(self, pts, col):
        i0 = len(self.v)
        self.v += [(*p, *col) for p in pts]
        self.f.append(list(range(i0, i0 + len(pts))))

    def box(self, c, s, col):
        (cx, cy, cz), (w, h, d) = c, s
        x0, x1, y0, y1, z0, z1 = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2, cz - d / 2, cz + d / 2
        self.quad([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], col)
        self.quad([(x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0)], col)
        self.quad([(x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1)], col)
        self.quad([(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)], col)
        self.quad([(x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)], col)
        self.quad([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], col)

    def lathe(self, profile, col, sides=16, axis="y", cap=None):
        """Rotationskoerper. profile = [(r, h), ...] entlang der Achse."""
        def pt(r, h, a):
            c, s = r * math.cos(a), r * math.sin(a)
            return (c, h, s) if axis == "y" else (c, s, h)
        for k in range(sides):
            a0, a1 = 2 * math.pi * k / sides, 2 * math.pi * (k + 1) / sides
            for (r0, h0), (r1, h1) in zip(profile[:-1], profile[1:]):
                self.quad([pt(r0, h0, a0), pt(r1, h1, a0), pt(r1, h1, a1), pt(r0, h0, a1)], col)
        if cap is not None:
            r, h = profile[cap]
            ring = [pt(r, h, 2 * math.pi * k / sides) for k in range(sides)]
            for k in range(sides):
                self.quad([(0, h, 0) if axis == "y" else (0, 0, h), ring[k], ring[(k + 1) % sides]], col)

    def write(self, name):
        p = out_dir / name
        with p.open("w") as f:
            f.write("ply\nformat ascii 1.0\n")
            f.write(f"element vertex {len(self.v)}\nproperty float x\nproperty float y\nproperty float z\n")
            f.write("property float red\nproperty float green\nproperty float blue\n")
            f.write(f"element face {len(self.f)}\nproperty list uchar int vertex_indices\nend_header\n")
            for x, y, z, r, g, b in self.v:
                f.write(f"{x:.5f} {y:.5f} {z:.5f} {r:.4f} {g:.4f} {b:.4f}\n")
            for fc in self.f:
                f.write(f"{len(fc)} {' '.join(map(str, fc))}\n")
        print(f"{p}: {len(self.v)} verts, {len(self.f)} faces")


BODY = (0.035, 0.035, 0.04)
METAL = (0.45, 0.46, 0.48)

# Moving Head: Buegel (Basis oben, zwei Arme nach unten)
m = Mesh()
m.box((0, -0.04, 0), (0.30, 0.08, 0.22), BODY)            # Basis
m.box((-0.16, -0.20, 0), (0.04, 0.28, 0.10), BODY)        # Arm links
m.box((0.16, -0.20, 0), (0.04, 0.28, 0.10), BODY)         # Arm rechts
m.write("mh_yoke.ply")

# Moving Head: Kopf, Linse zeigt nach -y
m = Mesh()
m.lathe([(0.0, 0.12), (0.10, 0.12), (0.12, 0.0), (0.11, -0.12), (0.09, -0.13)], BODY, sides=16)
m.write("mh_head.ply")

# Beam: offener Zylinder (Form macht der Shader)
m = Mesh()
m.lathe([(1.0, 0.0), (1.0, -1.0)], (1, 1, 1), sides=24)
m.write("beam.ply")

# Blinder-Schirm: Schuessel, Oeffnung nach +z
m = Mesh()
prof = [(0.5 * math.sin(t), -0.5 * math.cos(t) + 0.0) for t in [i * (math.pi / 2) / 6 for i in range(7)]]
m.lathe([(r, h * 0.6) for r, h in prof], METAL, sides=20, axis="z")
m.write("shade.ply")

# Bulb: laengliches Ellipsoid
m = Mesh()
prof = [(0.5 * math.sin(t), 0.8 * math.cos(t)) for t in [i * math.pi / 8 for i in range(9)]]
m.lathe(prof, (1, 1, 1), sides=12)
m.write("bulb.ply")

# LED-Ring-Segment (Viertel), Normale -y (vor der Linse)
m = Mesh()
r0, r1, y = 0.088, 0.112, -0.136
steps = 8
for i in range(steps):
    a0 = math.radians(-38 + 76 * i / steps)
    a1 = math.radians(-38 + 76 * (i + 1) / steps)
    m.quad([(r0 * math.cos(a0), y, r0 * math.sin(a0)), (r1 * math.cos(a0), y, r1 * math.sin(a0)),
            (r1 * math.cos(a1), y, r1 * math.sin(a1)), (r0 * math.cos(a1), y, r0 * math.sin(a1))], (1, 1, 1))
m.write("ring_seg.ply")
