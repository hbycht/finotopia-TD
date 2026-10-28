"""Rechnet MH_Move_Controller-Presets (pos_*) aus Zielpunkten im Twin-Raum.

Modell wie twin_lib.mh_state: Strahl = cos(th) u + sin(th) (cos(ph) f + sin(ph) (u x f))
  th = (Tilt_DMX - 0.5) * 270,  ph = pan_sign * (Pan_DMX - 0.5) * 540
Preset -> DMX (Fixture-Pars Pan 0.5 / Tilt 0.28):  Pan_DMX = v1,  Tilt_DMX = v2 - 0.22
Suche: grob ueber alle 256x256 8-Bit-Werte (findet den richtigen Zweig), dann fein (Map seit 2026-10-28 in 32 Bit:
MH_Move_Controller/position_map/comp1 rgba32float, MH_Move_Controller/comp1 rg32float, twin_probe_ctrl rgba32float).

Wand-MHs 31/32 (Plattform auf der DJ-Wand, Grundposition senkrecht von der Wand weg):
  31: Tilt kleiner -> nach unten (Henning 2026-10-28).
  32 haengt um 180 Grad um die eigene Achse gedreht (aus Hennings Presets V/Cross/Bar/Sides/Twin_Spot:
  Pan32 = 2/3 - Pan31 bei gleichem Tilt) -> Montage 32 = Spiegelbild von 31 mit umgedrehter Pan-Null.
  Spiegeln eines 31-Presets auf 32: v1' = 4/3 - v1 oder 2/3 - v1, v2' = v2.

Ausgang sind Hennings alte Presets (ref/presets_backup_2026-10-28.json); die Regeln unten legen fest,
was neu gerechnet wird. Aufruf: python3 solve_presets.py [--write]
  --write -> fixtures.json (Montage 31/32) und ref/presets_new.json (alle Presets, komplett)
"""
import json, math, os, sys
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P_RANGE, T_RANGE, DROP, TILT_OFF = 540.0, 270.0, 0.32, 0.22
POS = {'MOVO11': 'pos1', 'MOVO12': 'pos2', 'MOVO21': 'pos3', 'MOVO22': 'pos4',
       'MOVO23': 'pos5', 'MOVO24': 'pos6', 'MOVO31': 'pos7', 'MOVO32': 'pos8'}
K = np.arange(256) / 255.0
V1, V2 = np.meshgrid(K, K, indexing='ij')
MIRROR = np.diag([-1.0, 1.0, 1.0])


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def ortho_f(mount):
    """Pan-Nullrichtung exakt senkrecht zu u (die Werte in fixtures.json sind gerundet). Wie twin_lib.mh_state."""
    u = unit(mount['u'])
    return unit(np.asarray(mount['f'], float) - u * np.dot(mount['f'], u))


def beams(mount, A1=V1, A2=V2):
    """Strahlrichtungen fuer Wertegitter (A1 = v1, A2 = v2), Default alle 8-Bit-Werte -> (256, 256, 3)."""
    u, f, sp = unit(mount['u']), ortho_f(mount), mount['pan_sign']
    r = np.cross(u, f)
    th = np.radians((A2 - TILT_OFF - 0.5) * T_RANGE)
    ph = np.radians(sp * (A1 - 0.5) * P_RANGE)
    d = (np.cos(th)[..., None] * u + np.sin(th)[..., None] *
         (np.cos(ph)[..., None] * f + np.sin(ph)[..., None] * r))
    valid = ((A2 - TILT_OFF) >= 0.0) & (A1 >= 0.0) & (A1 <= 1.0) & (A2 <= 1.0)
    return d, valid


def fine_grid(v1, v2, span=1.5 / 255, n=151):
    s = np.linspace(-span, span, n)
    return np.meshgrid(v1 + s, v2 + s, indexing='ij')


def refine(mh, v1, v2, cost):
    """Feinsuche um (v1, v2). cost(d, valid) -> Array gleicher Form (kleiner = besser)."""
    for span in (1.5 / 255, 0.03 / 255):
        A1, A2 = fine_grid(v1, v2, span)
        d, valid = beams(mh['mount'], A1, A2)
        c = cost(d, valid); c[~valid] = 1e9
        i, j = np.unravel_index(np.argmin(c), c.shape)
        v1, v2 = float(A1[i, j]), float(A2[i, j])
    return round(v1, 6), round(v2, 6), float(c[i, j])


def head(mh):
    return np.array(mh['pos']) + unit(mh['mount']['u']) * DROP


def solve_dir(mh, want, prefer=None):
    """Bester 8-Bit-Presetwert mit Strahlrichtung want. prefer = (v1, v2): unter allen Loesungen, die hoechstens
    0.5 Grad schlechter sind als die beste, die naechste an prefer (keine unnoetigen 180-Grad-Schwenks)."""
    want = unit(want)
    d, valid = beams(mh['mount'])
    err = np.degrees(np.arccos(np.clip(d @ want, -1, 1)))
    err[~valid] = 1e9
    score = err
    if prefer is not None:
        dist = np.abs(V1 - prefer[0]) + np.abs(V2 - prefer[1])
        score = np.where(err <= err.min() + 0.5, dist, 1e9 + err)
    i, j = np.unravel_index(np.argmin(score), score.shape)
    return refine(mh, float(K[i]), float(K[j]),
                  lambda d, valid: np.degrees(np.arccos(np.clip(d @ want, -1, 1))))


def solve(mh, target, prefer=None):
    return solve_dir(mh, np.asarray(target, float) - head(mh), prefer)


def direction(mh, v1, v2):
    u, f, sp = unit(mh['mount']['u']), ortho_f(mh['mount']), mh['mount']['pan_sign']
    th = math.radians((v2 - TILT_OFF - 0.5) * T_RANGE); ph = math.radians(sp * (v1 - 0.5) * P_RANGE)
    return math.cos(th) * u + math.sin(th) * (math.cos(ph) * f + math.sin(ph) * np.cross(u, f))


def floor_hit(mh, v1, v2):
    h, d = head(mh), direction(mh, v1, v2)
    return h - d * h[1] / d[1]


def mirror_pan(v1, near):
    """Pan von 31 -> 32 (siehe Kopf). Von den gueltigen Loesungen die naechste an 'near'."""
    c = [v for v in (4.0 / 3.0 - v1, 2.0 / 3.0 - v1) if -1e-6 <= v <= 1 + 1e-6]
    return round(min(c, key=lambda v: abs(v - near)), 6)


def rot_a_to_b(a, b):
    a, b = unit(a), unit(b); v = np.cross(a, b); s = np.linalg.norm(v)
    if s < 1e-9:
        return np.eye(3)
    k = v / s; Kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    a = math.atan2(s, a @ b)
    return np.eye(3) + math.sin(a) * Kx + (1 - math.cos(a)) * Kx @ Kx


def half_w(room, z):
    d = room['dims']
    return (d['width_front'] + (d['width_back'] - d['width_front']) * z / d['length']) / 2


if __name__ == '__main__':
    fx = json.load(open(os.path.join(BASE, 'fixtures.json')))
    cal = json.load(open(os.path.join(BASE, 'ref/mh_calibration.json')))
    room = json.load(open(os.path.join(BASE, 'room.json')))
    old = json.load(open(os.path.join(BASE, 'ref/presets_backup_2026-10-28.json')))
    mh = {m['name']: m for m in fx['movingheads']}
    px = {p['name']: p for p in fx['pixels']}
    C = np.array(cal['center_target'])
    new = {k: dict(v) for k, v in old.items() if k.startswith('pos_')}
    log = []

    def get(preset, n):
        return new[preset][POS[n] + '_v1'], new[preset][POS[n] + '_v2']

    def put(preset, n, v1, v2, note=''):
        new[preset][POS[n] + '_v1'] = round(v1, 4)
        new[preset][POS[n] + '_v2'] = round(v2, 4)
        log.append(f'{preset:14s} {n}  v=({v1:.4f}, {v2:.4f})  {note}')

    def put_32_mirror(preset):
        v1, v2 = get(preset, 'MOVO31')
        put(preset, 'MOVO32', mirror_pan(v1, old[preset]['pos8_v1']), v2, 'Spiegel von 31')

    # --- Montage 31: Grundposition senkrecht von der Wand, Tilt kleiner -> nach unten;
    #     Center ueber Preset + minimale Montagekorrektur (8-Bit-Raster). 32 = Spiegelbild, Pan-Null umgedreht.
    m31 = mh['MOVO31']
    m31['mount'] = {'u': [0.0, 0.0, 1.0], 'f': [0.0, 1.0, 0.0], 'pan_sign': 1}
    v1, v2, e = solve(m31, C)
    R = np.eye(3)
    for _ in range(4):
        m31['mount'] = {'u': list(R @ np.array([0, 0, 1.0])), 'f': list(R @ np.array([0, 1.0, 0])), 'pan_sign': 1}
        R = rot_a_to_b(direction(m31, v1, v2), C - head(m31)) @ R
    m31['mount'] = {'u': [round(float(x), 4) for x in R @ np.array([0, 0, 1.0])],
                    'f': [round(float(x), 4) for x in R @ np.array([0, 1.0, 0])], 'pan_sign': 1}
    mh['MOVO32']['mount'] = {'u': [round(float(x), 4) for x in MIRROR @ unit(m31['mount']['u'])],
                             'f': [round(float(x), 4) for x in -(MIRROR @ unit(m31['mount']['f']))], 'pan_sign': 1}
    put('pos_Center', 'MOVO31', v1, v2, f'Treffpunkt {C} (Rest {e:.2f} deg per Montage)')
    put_32_mirror('pos_Center')

    # --- Down: Decke unveraendert; 31 Pan der Grundposition, senkrecht nach unten
    v1, v2, e = solve_dir(m31, [0, -1, 0], (0.5, 0.3867))
    put('pos_Down', 'MOVO31', v1, v2, f'senkrecht nach unten ({e:.2f} deg)')
    put_32_mirror('pos_Down')

    # --- Wall: Decken-MHs optisch mittig in den Blinder; 31/32 kreuzen genau vor der Mitte des Panels.
    #     Der Strahl ist auf 3-5 m so breit wie der Schirm; sein sichtbarer Abschluss (der Rand, der am Schirm vorbei auf die Wand faellt) liegt auf der Wandebene z=0
    #     -> Strahlachse trifft die Wand genau hinter der Blindermitte (Screenshot-Abgleich 2026-10-28).
    def plane_dist(n, v1, v2, target):
        h, d = head(mh[n]), direction(mh[n], v1, v2)
        return float(np.linalg.norm((h + d * (target[2] - h[2]) / d[2])[:2] - target[:2]))
    for n, bl in (('MOVO11', 'BLINDER_UL'), ('MOVO12', 'BLINDER_UR'), ('MOVO21', 'BLINDER_OL'),
                  ('MOVO22', 'BLINDER_ML'), ('MOVO23', 'BLINDER_MR'), ('MOVO24', 'BLINDER_OR')):
        b = px[bl]
        bottom = np.array([b['pos'][0], b['pos'][1], 0.0])
        v1, v2, _ = solve(mh[n], bottom, get('pos_Wall', n))
        dist = plane_dist(n, v1, v2, bottom)
        put('pos_Wall', n, v1, v2, f'Mitte {bl} (Wandebene, Abstand {dist * 100:.1f} cm)')
    pn = px['PANEL']
    cross = [pn['pos'][0], pn['pos'][1], pn['pos'][2] + 0.3]   # 30 cm vor der Panel-Mitte
    v1, v2, e = solve(m31, cross, get('pos_Wall', 'MOVO31'))
    put('pos_Wall', 'MOVO31', v1, v2, f'Kreuzung {np.round(cross, 2)} ({e:.2f} deg)')
    put_32_mirror('pos_Wall')

    # --- V: gegenueberliegende Paare treffen sich auf ihrer z-Ebene in einem Punkt auf der Mittelachse
    #     (Boden; 31/32 auf dem DJ-Podest y=0.2)
    for a, b in (('MOVO11', 'MOVO12'), ('MOVO21', 'MOVO24'), ('MOVO22', 'MOVO23')):
        z = (head(mh[a])[2] + head(mh[b])[2]) / 2
        for n in (a, b):
            v1, v2, e = solve(mh[n], [0.0, 0.0, z], get('pos_V', n))
            put('pos_V', n, v1, v2, f'V-Punkt (0, 0, {z:.2f}) ({e:.2f} deg)')
    z = head(m31)[2]
    v1, v2, e = solve(m31, [0.0, 0.2, z], get('pos_V', 'MOVO31'))
    put('pos_V', 'MOVO31', v1, v2, f'V-Punkt (0, 0.2, {z:.2f}) ({e:.2f} deg)')
    put_32_mirror('pos_V')

    # --- Cross: 31 bleibt, 32 = Spiegel
    put_32_mirror('pos_Cross')

    # --- Bar: alle Paare symmetrisch. Ziel je Paar = gemittelte (gespiegelte) Treffer der alten Werte auf der Bar-Wand
    L = room['dims']['length']
    def bar_hit(n, v1, v2):
        h, d = head(mh[n]), direction(mh[n], v1, v2)
        return h + d * (L - h[2]) / d[2]
    for a, b in (('MOVO11', 'MOVO12'), ('MOVO21', 'MOVO24'), ('MOVO22', 'MOVO23')):
        pa = bar_hit(a, old['pos_Bar'][POS[a] + '_v1'], old['pos_Bar'][POS[a] + '_v2'])
        pb = bar_hit(b, old['pos_Bar'][POS[b] + '_v1'], old['pos_Bar'][POS[b] + '_v2'])
        xa, y = (pa[0] - pb[0]) / 2, (pa[1] + pb[1]) / 2          # Ziel linker MH (a); b = Spiegel
        for n, x in ((a, xa), (b, -xa)):
            prefer = (old['pos_Bar'][POS[n] + '_v1'], old['pos_Bar'][POS[n] + '_v2'])   # kein 180-Grad-Zweig
            v1, v2, e = solve(mh[n], [x, y, L], prefer)
            p = bar_hit(n, v1, v2)
            put('pos_Bar', n, v1, v2, f'Bar-Wand ({p[0]:.3f}, {p[1]:.3f})')
    put_32_mirror('pos_Bar')

    # --- Twin_Spot: Decken-MHs bleiben; 31/32 in die beiden Spots (Mittel der Bodentreffer je Seite)
    hits = {n: floor_hit(mh[n], *get('pos_Twin_Spot', n)) for n in mh if n not in ('MOVO31', 'MOVO32')}
    spot = {s: np.mean([p for p in hits.values() if np.sign(p[0]) == s], axis=0) for s in (-1, 1)}
    v1, v2, e = solve(m31, spot[-1], get('pos_Twin_Spot', 'MOVO31'))
    put('pos_Twin_Spot', 'MOVO31', v1, v2, f'Spot {np.round(spot[-1], 2)} ({e:.2f} deg)')
    put_32_mirror('pos_Twin_Spot')      # trifft den rechten Spot bis auf wenige cm (Spots fast symmetrisch)

    # --- Sides: 31/32 auf die weiter entfernte Seitenwand (Hoehe wie die anderen, ~2.6 m)
    zt = 1.5
    v1, v2, e = solve(m31, [half_w(room, zt), 2.6, zt], get('pos_Sides', 'MOVO31'))
    put('pos_Sides', 'MOVO31', v1, v2, f'Wand rechts z={zt} ({e:.2f} deg)')
    put_32_mirror('pos_Sides')

    print('\n'.join(log))
    print('Montage 31:', m31['mount'], '\nMontage 32:', mh['MOVO32']['mount'])
    if '--write' in sys.argv:
        fx['_doc_mounts'] = (
            'MH-Montage: Decke u~(0,-1,0) (Kalibrierung ref/mh_calibration.json + minimale Korrektur, damit Center '
            'exakt in center_target trifft). Wand 31/32 (Henning 2026-10-28): Plattform auf der DJ-Wand, Grundposition '
            'senkrecht von der Wand weg; 31 Tilt kleiner -> nach unten; 32 um 180 Grad um die eigene Achse gedreht '
            '(aus Hennings Presets). Presets: tools/solve_presets.py.')
        for p, d in ((os.path.join(BASE, 'fixtures.json'), fx), (os.path.join(BASE, 'ref/presets_new.json'), new)):
            tmp = p + '.tmp'; json.dump(d, open(tmp, 'w'), indent=2, ensure_ascii=False); os.replace(tmp, p)
        print('geschrieben')
