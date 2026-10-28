"""room.json -> room.ply (Low-Poly-Raum mit Vertexfarben, flache Faces).

Aufruf:  python3 build_room.py [twin-ordner]
Der File In POP in TD liest room.ply; Normalen berechnet dort ein Normal POP.
"""
import json, math, sys
from pathlib import Path

base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
R = json.loads((base / "room.json").read_text())
D, MAT = R["dims"], R["materials"]
L = D["length"]


def half_width(z):
    return 0.5 * (D["width_front"] + (D["width_back"] - D["width_front"]) * z / L)


def ceil_y(z):
    return D["ceil_front"] + (D["ceil_back"] - D["ceil_front"]) * z / L


verts, faces = [], []


def poly(pts, mat):
    """Ein Face mit eigenen Vertices (flat shading). pts gegen den Uhrzeigersinn von der Sichtseite."""
    col = MAT[mat] if isinstance(mat, str) else mat
    i0 = len(verts)
    for p in pts:
        verts.append((*p, *col))
    faces.append(list(range(i0, i0 + len(pts))))


def box(c, s, mat):
    (cx, cy, cz), (w, h, d) = c, s
    x0, x1, y0, y1, z0, z1 = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2, cz - d / 2, cz + d / 2
    poly([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], mat)  # +z
    poly([(x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0)], mat)  # -z
    poly([(x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1)], mat)  # +x
    poly([(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)], mat)  # -x
    poly([(x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)], mat)  # +y
    poly([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], mat)  # -y


def tube(a, b, r, mat, sides=8):
    ax, ay, az = a
    bx, by, bz = b
    d = [bx - ax, by - ay, bz - az]
    n = math.sqrt(sum(v * v for v in d))
    d = [v / n for v in d]
    up = [0, 1, 0] if abs(d[1]) < 0.9 else [1, 0, 0]
    u = [d[1] * up[2] - d[2] * up[1], d[2] * up[0] - d[0] * up[2], d[0] * up[1] - d[1] * up[0]]
    un = math.sqrt(sum(v * v for v in u))
    u = [v / un for v in u]
    v = [d[1] * u[2] - d[2] * u[1], d[2] * u[0] - d[0] * u[2], d[0] * u[1] - d[1] * u[0]]
    ring = []
    for k in range(sides):
        t = 2 * math.pi * k / sides
        ring.append([r * (math.cos(t) * u[i] + math.sin(t) * v[i]) for i in range(3)])
    for k in range(sides):
        p, q = ring[k], ring[(k + 1) % sides]
        poly([(ax + p[0], ay + p[1], az + p[2]), (bx + p[0], by + p[1], bz + p[2]),
              (bx + q[0], by + q[1], bz + q[2]), (ax + q[0], ay + q[1], az + q[2])], mat)


# --- Huelle (Normalen zeigen nach innen)
S = R["surfaces"]
hf, hb, cf, cb = half_width(0), half_width(L), ceil_y(0), ceil_y(L)
poly([(-hf, 0, 0), (hf, 0, 0), (hb, 0, L), (-hb, 0, L)][::-1], S["floor"])
poly([(-hf, cf, 0), (hf, cf, 0), (hb, cb, L), (-hb, cb, L)], S["ceiling"])
poly([(-hf, 0, 0), (hf, 0, 0), (hf, cf, 0), (-hf, cf, 0)], S["wall_front"])
poly([(hb, 0, L), (-hb, 0, L), (-hb, cb, L), (hb, cb, L)], S["wall_back"])
poly([(-hb, 0, L), (-hf, 0, 0), (-hf, cf, 0), (-hb, cb, L)][::-1], S["wall_left"])
poly([(hf, 0, 0), (hb, 0, L), (hb, cb, L), (hf, cf, 0)][::-1], S["wall_right"])

# --- Boxen
for b in R["boxes"]:
    cx, cy, cz = b["center"]
    w, h, d = b["size"]
    if b.get("span"):
        w = 2 * half_width(cz)
    if cy == "ceil":
        cy = ceil_y(cz) - h / 2
    if b.get("on_wall") == "left":
        cx = -half_width(cz) + w / 2
    elif b.get("on_wall") == "right":
        cx = half_width(cz) - w / 2
    box((cx, cy, cz), (w, h, d), b["mat"])

# --- Fenster / Tueren als dunkle Flaechen knapp vor der Wand
for wdw in R["windows"]:
    sgn = -1 if wdw["wall"] == "left" else 1
    z0, z1 = wdw["z"] - wdw["w"] / 2, wdw["z"] + wdw["w"] / 2
    y0, y1 = wdw["y"] - wdw["h"] / 2, wdw["y"] + wdw["h"] / 2
    x0, x1 = sgn * (half_width(z0) - 0.02), sgn * (half_width(z1) - 0.02)
    pts = [(x0, y0, z0), (x1, y0, z1), (x1, y1, z1), (x0, y1, z0)]
    poly(pts if sgn > 0 else pts[::-1], "glass")

# --- Rohre / Truss
for t in R["tubes"]:
    a, b = list(t["from"]), list(t["to"])
    if t.get("y_from_ceil"):
        a[1] += ceil_y(a[2])
        b[1] += ceil_y(b[2])
    tube(a, b, t["radius"], t["mat"])

out = base / "room.ply"
with out.open("w") as f:
    f.write("ply\nformat ascii 1.0\n")
    f.write(f"element vertex {len(verts)}\nproperty float x\nproperty float y\nproperty float z\n")
    f.write("property float red\nproperty float green\nproperty float blue\n")
    f.write(f"element face {len(faces)}\nproperty list uchar int vertex_indices\nend_header\n")
    for x, y, z, r, g, b_ in verts:
        f.write(f"{x:.4f} {y:.4f} {z:.4f} {r:.4f} {g:.4f} {b_:.4f}\n")
    for fc in faces:
        f.write(f"{len(fc)} {' '.join(map(str, fc))}\n")
print(f"{out}: {len(verts)} verts, {len(faces)} faces")
