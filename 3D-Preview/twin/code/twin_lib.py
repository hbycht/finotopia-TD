"""twin_lib - Datenbruecke finotopia -> digitaler Zwilling.

Wird als Module-DAT 'twin_lib' in der Twin-Base geladen und von den Script CHOPs aufgerufen.
Liest twin/fixtures.json (bei Aenderung automatisch neu) und die Live-Daten der node*-Fixtures:
  Pixel-Fixtures : <src>/geo_out (Layout, 2D Preview-Raum) + <src>/col_out (r,g,b[,w] 0..1 je Pixel)
  MH/Bulbs/Fog   : <src>/DMX_CH_RENAMER/in1 (benannte DMX-Kanaele 0..255)
Die finotopia-Fixtures werden nur gelesen, nie veraendert.
"""
import json
import math
import os

import numpy as np

_cache = {}


# ---------------------------------------------------------------- Konfiguration

def cfg():
    path = os.path.join(project.folder, 'twin', 'fixtures.json')
    mtime = os.path.getmtime(path)
    if _cache.get('mtime') != mtime:
        try:
            with open(path) as f:
                data = json.load(f)
        except ValueError:
            # Datei wird gerade geschrieben (halb leer) -> letzte gueltige Version behalten, naechster Cook liest neu
            if 'cfg' in _cache:
                return _cache['cfg']
            raise
        _cache.clear()
        _cache['cfg'] = data
        _cache['mtime'] = mtime
    return _cache['cfg']


def _rot(deg):
    """Euler XYZ in Grad -> 3x3 Matrix (erst X, dann Y, dann Z)."""
    rx, ry, rz = (math.radians(a) for a in deg)
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    mx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    my = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    mz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return mz @ my @ mx


def _dmx(root, src):
    """Benannte DMX-Werte eines Fixtures als dict, normiert auf 0..1."""
    if TEST['on']:
        return _test_dmx(src, TEST['t'])
    if GPU['on']:
        return _gpu_dmx(root, src)
    c = root.op(src + '/DMX_CH_RENAMER/in1')
    if c is None:
        return {}
    return {ch.name: ch.eval() / 255.0 for ch in c.chans()}


def _col_out(root, src):
    """Pixelfarben eines Fixtures, shape (Kanaele, Pixel), 0..1."""
    if TEST['on']:
        n = len(fixture_points(root, src))
        return _test_pixels(src, n, TEST['t'])
    return root.op(src + '/col_out').numpyArray()


# ---------------------------------------------------------------- Testmodus
# Synthetische Daten ohne laufende Show (Custom Par 'Testmode' der Twin-Base).
# Die finotopia-Fixtures werden dabei nicht angefasst.

TEST = {'on': False, 't': 0.0}


def _hsv(h):
    h = np.asarray(h) % 1.0
    return np.clip(np.abs(((h[..., None] * 6.0 + np.array([0.0, 4.0, 2.0])) % 6.0) - 3.0) - 1.0, 0.0, 1.0)


def _test_pixels(src, n, t):
    rgb = _hsv(np.linspace(0, 1, n, endpoint=False) + t * 0.15 + (hash(src) % 100) / 100.0)
    return rgb.T * (0.6 + 0.4 * math.sin(t * 2.0 + hash(src) % 7))


def _test_dmx(src, t):
    k = (hash(src) % 97) / 97.0
    if 'MOVO' in src:
        col = _hsv(np.array(t * 0.1 + k))
        d = {'Pan': 0.5 + 0.12 * math.sin(t * 0.7 + k * 6.3), 'Tilt': 0.62 + 0.12 * math.sin(t * 0.5 + k * 3.1),
             'Dimmermain': 1.0, 'Dimmerring': 1.0, 'Led0r': col[0], 'Led0g': col[1], 'Led0b': col[2]}
        for i in range(1, 5):
            rc = _hsv(np.array(t * 0.2 + k + i * 0.25))
            d.update({f'Led{i}r': rc[0], f'Led{i}g': rc[1], f'Led{i}b': rc[2]})
        return d
    if 'BULB' in src:
        return {f'Bulb{i}': 0.5 + 0.5 * math.sin(t + i) for i in range(1, 5)}
    if 'FOG' in src:
        return {'Fog': 0.6, 'Fan': 0.5}
    return {}


# ---------------------------------------------------------------- Pixel-Fixtures

def pixel_layout(root):
    """Statisches 3D-Layout aller Pixel. Returns dict mit pos (N,3), nrm (N,3), fid (N,), counts."""
    c = cfg()
    pos, nrm, fid, counts = [], [], [], []
    for i, f in enumerate(c['pixels']):
        pts = np.array(fixture_points(root, f['src']), dtype=np.float64)
        ctr = (pts.min(0) + pts.max(0)) / 2.0
        ext = max((pts.max(0) - pts.min(0)).max(), 1e-6)
        local = np.c_[(pts - ctr) * (f['size'] / ext), np.zeros(len(pts))]
        R = _rot(f.get('rot', [0, 0, 0]))
        pos.append(local @ R.T + np.array(f['pos']))
        nrm.append(np.tile(R @ np.array([0.0, 0.0, 1.0]), (len(pts), 1)))
        fid.append(np.full(len(pts), i))
        counts.append(len(pts))
    return {'pos': np.vstack(pos), 'nrm': np.vstack(nrm), 'fid': np.concatenate(fid), 'counts': counts}


def pixel_colors(root):
    """Live-Farben aller Pixel (N,3), Reihenfolge wie pixel_layout. W wird auf RGB addiert."""
    cols = []
    for f in cfg()['pixels']:
        a = _col_out(root, f['src'])
        n = len(fixture_points(root, f['src']))
        if a.shape[0] < 3 or a.shape[1] != n:
            # Fixture kocht nicht (Ausstellungsmodus) -> col_out leer; schwarz statt Fehler
            cols.append(np.zeros((n, 3)))
            continue
        rgb = a[:3]
        if a.shape[0] > 3:
            rgb = rgb + a[3:4]
        cols.append(rgb.T)
    return np.clip(np.vstack(cols), 0.0, None)


def pixel_fixture_avg(root):
    """Mittlere Farbe je Pixel-Fixture (fuer die Raumbeleuchtung)."""
    if GPU['on'] and not TEST['on']:
        return _gpu_fixture_avg(root)
    out = []
    for f in cfg()['pixels']:
        a = _col_out(root, f['src'])
        rgb = a[:3].mean(1)
        if a.shape[0] > 3:
            rgb = rgb + a[3].mean()
        out.append(rgb)
    return np.array(out)


# ---------------------------------------------------------------- Moving Heads
# Cameo MovoBeam 100 (CLMB100), 35-Kanal-Modus. Pan/Tilt sind endlos drehbar; die Positionskanaele
# decken laut Kalibrierung (twin/ref/mh_calibration.json, tools/fit_mh_mounts.py) 540 deg Pan / 270 deg Tilt ab.
# Montage je MH in fixtures.json ('mount'):
#   u  = Strahlrichtung bei Tilt-Mitte (Sockel -> Kopf), f = Pan-Nullrichtung, pan_sign
#   Strahl = cos(th) u + sin(th) (cos(ph) f + sin(ph) (u x f)),  th = (Tilt-0.5)*270,  ph = sign*(Pan-0.5)*540

MH_HEAD_DROP = 0.32        # Abstand Aufhaengepunkt -> Kopfzentrum entlang u (m)
RING_RADIUS = 0.098        # Radius des LED-Rings um die Linse (m)


def _unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def _euler_xyz(R):
    """Rotationsmatrix -> Euler (Grad) fuer TD-Instancing mit Rotationsreihenfolge 'xyz' (R = Rz Ry Rx)."""
    ry = math.asin(max(-1.0, min(1.0, -R[2, 0])))
    rx = math.atan2(R[2, 1], R[2, 2])
    rz = math.atan2(R[1, 0], R[0, 0])
    return math.degrees(rx), math.degrees(ry), math.degrees(rz)


def _frame(y_axis, z_hint):
    """Orthonormale Basis (Spalten x, y, z) mit vorgegebener y-Achse und z moeglichst nahe z_hint."""
    y = _unit(y_axis)
    z = np.asarray(z_hint, float) - y * (np.dot(z_hint, y))
    if np.linalg.norm(z) < 1e-6:
        z = np.cross(y, [1.0, 0.0, 0.0])
    z = _unit(z)
    x = np.cross(y, z)
    return np.column_stack([x, y, z])


def _smooth_pan_tilt(name, pan, tilt, s):
    """Begrenzt die Kopfbewegung auf eine maximale Geschwindigkeit (keine Spruenge) und glaettet leicht.
    Zustand liegt im Modul-Cache; dt aus der Framezahl, damit Mehrfach-Cooks im selben Frame nichts verfaelschen."""
    st = _cache.setdefault('mh_motion', {})
    frame = absTime.frame
    rate = max(project.cookRate, 1.0)
    cur = st.get(name)
    if cur is None or TEST['on'] and cur.get('test') is False:
        st[name] = {'pan': pan, 'tilt': tilt, 'frame': frame, 'test': TEST['on']}
        return pan, tilt
    dt = min(max((frame - cur['frame']) / rate, 0.0), 0.25)
    if dt == 0.0:
        return cur['pan'], cur['tilt']
    out = []
    for key, target, speed in (('pan', pan, s['mh_pan_speed'] / s['mh_pan_range']),
                               ('tilt', tilt, s['mh_tilt_speed'] / s['mh_tilt_range'])):
        delta = target - cur[key]
        step = max(-speed * dt, min(speed * dt, delta))           # max. Geschwindigkeit
        alpha = 1.0 - math.exp(-dt / s['mh_smoothing'])           # weiches Ein-/Auslaufen
        cur[key] += step * (alpha if abs(delta) < speed * dt else 1.0)
        out.append(cur[key])
    cur['frame'] = frame
    cur['test'] = TEST['on']
    return out[0], out[1]


def mh_state(root, t=0.0):
    """Zustand aller Moving Heads. Returns dict von Arrays (M,) bzw. (M,3)/(M,3,3)."""
    c = cfg()
    s = c['settings']
    keys = ('mount', 'head', 'dir', 'yoke_R', 'head_R', 'beam', 'ring', 'ring4', 'inten')
    st = {k: [] for k in keys}
    for mh in c['movingheads']:
        d = _dmx(root, mh['src'])
        pan = d.get('Pan', 0.5) + d.get('Panfine', 0.0) / 256.0
        tilt = d.get('Tilt', 0.5) + d.get('Tiltfine', 0.0) / 256.0
        pan, tilt = _smooth_pan_tilt(mh['name'], pan, tilt, s)

        m = mh.get('mount', {'u': [0, -1, 0], 'f': [0, 0, 1], 'pan_sign': 1})
        u = _unit(m['u'])
        f = _unit(np.asarray(m['f'], float) - u * np.dot(m['f'], u))   # f exakt senkrecht zu u (gerundete Werte)
        r = np.cross(u, f)
        th = math.radians((tilt - 0.5) * s['mh_tilt_range'])
        ph = math.radians(m['pan_sign'] * (pan - 0.5) * s['mh_pan_range'])
        heading = math.cos(ph) * f + math.sin(ph) * r              # Bügel-Ausrichtung (Pan)
        direction = math.cos(th) * u + math.sin(th) * heading      # Strahl

        yoke_R = _frame(-u, heading)                    # Bügel haengt entlang u, dreht mit Pan
        # Kopf: lokales -y = Strahl, Kipp-Achse = Bügel-x
        head_R = np.column_stack([yoke_R[:, 0], -direction, np.cross(yoke_R[:, 0], -direction)])

        white = d.get('Led0white', 0.0)
        beam = np.array([d.get('Led0r', 0.0), d.get('Led0g', 0.0), d.get('Led0b', 0.0)]) + white
        dim = d.get('Dimmermain', 0.0) + d.get('Dimmermainfine', 0.0) / 256.0
        beam = beam * dim * _strobe_main(d.get('Strobemain', 0.0), t, mh['name'])

        ring_gate = d.get('Dimmerring', 0.0) * _strobe_ring(d.get('Strobering', 0.0), t)
        ring4 = np.array([[d.get(f'Led{k}{ch}', 0.0) for ch in 'rgb'] for k in range(1, 5)]) * ring_gate

        mount = np.array(mh['pos'])
        st['mount'].append(mount)
        st['head'].append(mount + u * MH_HEAD_DROP)
        st['dir'].append(direction)
        st['yoke_R'].append(yoke_R)
        st['head_R'].append(head_R)
        st['beam'].append(beam)
        st['ring'].append(ring4.mean(0))
        st['ring4'].append(ring4)
        st['inten'].append(float(beam.max()))
    return {k: np.array(v) for k, v in st.items()}


def _strobe_main(v, t, name=''):
    """Strobe-Kanal (CH9) laut Handbuch MovoBeam 100 -> Gate 0..1."""
    dmx = v * 255.0
    if dmx <= 5 or dmx >= 251:
        return 1.0                                                  # offen
    if dmx <= 10:
        return 0.0                                                  # geschlossen
    if dmx >= 128:                                                  # Strobe <1 .. 20 Hz
        hz = 0.8 + (dmx - 128) / (250 - 128) * 19.2
        return 1.0 if (t * hz) % 1.0 < 0.25 else 0.0
    # 11-127: Zufalls-Effekte (Pulse/Ramp/Random/Break) -> angenaehert als zufaelliges Blitzen
    speed = 1.0 + ((dmx - 11) % 23) / 23.0 * 10.0
    seed = (int(t * speed) * 7919 + hash(name)) % 1000 / 1000.0
    return 1.0 if seed < 0.35 else 0.0


def _strobe_ring(v, t):
    """Ring-Strobe (CH21): 0-5 offen, 6-255 Strobe <1 .. 20 Hz."""
    dmx = v * 255.0
    if dmx <= 5:
        return 1.0
    hz = 0.8 + (dmx - 6) / (255 - 6) * 19.2
    return 1.0 if (t * hz) % 1.0 < 0.25 else 0.0


# ---------------------------------------------------------------- Bulbs / Fog

def bulbs(root):
    vals = []
    for b in cfg()['bulbs']:
        vals.append(_dmx(root, b['src']).get(b['chan'], 0.0))
    return np.array(vals)


def fog(root):
    d = _dmx(root, cfg()['fog']['src'])
    return d.get('Fog', 0.0), d.get('Fan', 0.0)


# ---------------------------------------------------------------- Lichtliste fuer room_lit

BULB_COLOR = np.array([1.0, 0.55, 0.22])
BULB_FALLOFF = 8.0         # Bulbs: steilerer Abfall als die Pixel-Lichter -> lokales Glimmen statt Raum-Ambient


def lights(root, t=0.0, mh_gain=6.0, bulb_gain=0.5, pixel_gain=0.6):
    """Alle Lichtquellen als Arrays fuer den GLSL MAT.
    kind: 0 = Spot, 1 = Punkt.  Returns dict pos (L,3), dir (L,3), col (L,3), kind, cosout, cosin.
    Bei Punktlichtern steht in cosout der Falloff-Faktor (Multiplikator auf uFalloff)."""
    c = cfg()
    s = c['settings']
    pos, dirs, col, kind, cout, cin = [], [], [], [], [], []

    half = math.radians(s['mh_beam_angle'] / 2.0)
    m = root.op('VISUAL_PREVIEW/twin/mh')
    a = {n: m[n].numpyArray() for n in ('hx', 'hy', 'hz', 'dx', 'dy', 'dz', 'r', 'g', 'b')}
    for i in range(m.numSamples):
        pos.append([a['hx'][i], a['hy'][i], a['hz'][i]]); dirs.append([a['dx'][i], a['dy'][i], a['dz'][i]])
        col.append(np.array([a['r'][i], a['g'][i], a['b'][i]]) * mh_gain)
        kind.append(0); cout.append(math.cos(half * 1.8)); cin.append(math.cos(half * 0.7))

    for b, v in zip(c['bulbs'], bulbs(root)):
        pos.append(b['pos']); dirs.append([0, -1, 0]); col.append(BULB_COLOR * v * bulb_gain)
        kind.append(1); cout.append(BULB_FALLOFF); cin.append(-1.0)

    for f, avg in zip(c['pixels'], pixel_fixture_avg(root)):
        n = _rot(f.get('rot', [0, 0, 0])) @ np.array([0.0, 0.0, 1.0])
        pos.append(np.array(f['pos']) + n * 0.25); dirs.append(n); col.append(avg * pixel_gain)
        kind.append(1); cout.append(1.0); cin.append(-1.0)

    return {'pos': np.array(pos), 'dir': np.array(dirs), 'col': np.array(col),
            'kind': np.array(kind, dtype=float), 'cosout': np.array(cout), 'cosin': np.array(cin)}


# ---------------------------------------------------------------- Script-CHOP-Helfer

def write_chop(scriptOp, n, chans):
    """chans = {name: array(n)} -> Script CHOP mit n Samples."""
    scriptOp.clear()
    scriptOp.numSamples = n
    for name, arr in chans.items():
        # copyNumpyArray braucht ein zusammenhaengendes float32-Array (Spalten-Slices sind es nicht)
        scriptOp.appendChan(name).copyNumpyArray(np.ascontiguousarray(arr, dtype=np.float32))


# ---------------------------------------------------------------- cook_<scriptCHOP-Name>
# Die gemeinsame Callback-DAT ruft fuer Script CHOP 'xyz' die Funktion cook_xyz(scriptOp, root, t) auf.

def cook_pix_pos(scriptOp, root, t):
    lay = pixel_layout(root)
    p, n = lay['pos'], lay['nrm']
    # Up-Vektor fuer rotate-to-vector: bei (fast) senkrechten Normalen z statt y verwenden
    vertical = np.abs(n[:, 1]) > 0.9
    up = np.where(vertical[:, None], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0])
    write_chop(scriptOp, len(p), {'tx': p[:, 0], 'ty': p[:, 1], 'tz': p[:, 2],
                                  'nx': n[:, 0], 'ny': n[:, 1], 'nz': n[:, 2],
                                  'ux': up[:, 0], 'uy': up[:, 1], 'uz': up[:, 2], 'fid': lay['fid']})


def cook_pix_col(scriptOp, root, t):
    c = pixel_colors(root)
    write_chop(scriptOp, len(c), {'r': c[:, 0], 'g': c[:, 1], 'b': c[:, 2]})


def cook_mh(scriptOp, root, t):
    s = cfg()['settings']
    m = mh_state(root, t)
    n = len(m['head'])
    length = np.full(n, s['mh_beam_length'])
    rad = length * math.tan(math.radians(s['mh_beam_angle'] / 2.0))
    ye = np.array([_euler_xyz(R) for R in m['yoke_R']])
    he = np.array([_euler_xyz(R) for R in m['head_R']])
    write_chop(scriptOp, n, {
        'mx': m['mount'][:, 0], 'my': m['mount'][:, 1], 'mz': m['mount'][:, 2],
        'hx': m['head'][:, 0], 'hy': m['head'][:, 1], 'hz': m['head'][:, 2],
        'dx': m['dir'][:, 0], 'dy': m['dir'][:, 1], 'dz': m['dir'][:, 2],
        'yrx': ye[:, 0], 'yry': ye[:, 1], 'yrz': ye[:, 2],
        'rx': he[:, 0], 'ry': he[:, 1], 'rz': he[:, 2], 'len': length, 'rad': rad,
        'r': m['beam'][:, 0], 'g': m['beam'][:, 1], 'b': m['beam'][:, 2],
        'rr': m['ring'][:, 0], 'rg': m['ring'][:, 1], 'rb': m['ring'][:, 2], 'inten': m['inten']})
    _cache['mh_last'] = m


def cook_mh_ring(scriptOp, root, t):
    """4 RGB-Ringsegmente je MOVO (Led1..Led4, Dimmerring/Strobering) als Instanzen."""
    m = _cache.get('mh_last') or mh_state(root, t)
    rows = {k: [] for k in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'r', 'g', 'b')}
    for i in range(len(m['head'])):
        R = m['head_R'][i]
        for k in range(4):
            a = math.radians(45.0 + 90.0 * k)                # Segment k um die Linsenachse
            Ry = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
            rx, ry, rz = _euler_xyz(R @ Ry)
            p = m['head'][i]
            for key, val in zip(('tx', 'ty', 'tz', 'rx', 'ry', 'rz'), (*p, rx, ry, rz)):
                rows[key].append(val)
            for key, val in zip('rgb', m['ring4'][i][k]):
                rows[key].append(val)
    write_chop(scriptOp, len(rows['tx']), rows)


def cook_bulbs(scriptOp, root, t):
    c = cfg()
    v = bulbs(root)
    p = np.array([b['pos'] for b in c['bulbs']])
    # Grundglimmen, damit die Bulbs auch ausgeschaltet als Objekt sichtbar bleiben
    col = np.outer(np.maximum(v * 2.0, 0.04), BULB_COLOR)
    write_chop(scriptOp, len(p), {'tx': p[:, 0], 'ty': p[:, 1], 'tz': p[:, 2],
                                  'r': col[:, 0], 'g': col[:, 1], 'b': col[:, 2]})


def cook_shades(scriptOp, root, t):
    bl = [f for f in cfg()['pixels'] if f['kind'] == 'blinder']
    p = np.array([f['pos'] for f in bl])
    n = np.array([_rot(f.get('rot', [0, 0, 0])) @ np.array([0.0, 0.0, 1.0]) for f in bl])
    s = np.array([f['size'] * 1.1 for f in bl])
    write_chop(scriptOp, len(p), {'tx': p[:, 0], 'ty': p[:, 1], 'tz': p[:, 2] - 0.05,
                                  'nx': n[:, 0], 'ny': n[:, 1], 'nz': n[:, 2], 's': s})


def cook_lights(scriptOp, root, t):
    L = lights(root, t)
    p, d, c = L['pos'], L['dir'], L['col']
    write_chop(scriptOp, len(p), {
        'px': p[:, 0], 'py': p[:, 1], 'pz': p[:, 2], 'kind': L['kind'],
        'dx': d[:, 0], 'dy': d[:, 1], 'dz': d[:, 2], 'cosout': L['cosout'],
        'r': c[:, 0], 'g': c[:, 1], 'b': c[:, 2], 'cosin': L['cosin']})


def cook_fog(scriptOp, root, t):
    f, fan = fog(root)
    write_chop(scriptOp, 1, {'fog': [f], 'fan': [fan]})


# ---------------------------------------------------------------- Ausstellungsmodus (GPU-Abtastung)
# Statt die node*-Fixtures (100 TOPs, 38 GPU->CPU-Readbacks) kochen zu lassen, tastet der Twin
# dieselben Map-Texturen selbst auf der GPU ab - an denselben Punkten (geo_out) mit derselben
# UV-Normierung (math_normalize: v = y * g + (1 - g) / 2, g = visual_width / visual_height)
# und denselben Vorfiltern (Blur/Mono/Level wie in den Fixtures, nachgebaut in der Twin-Base).
#   probe_pix : alle LED-Pixel -> Farbe direkt ins Instancing (kein Readback)
#   probe_ctrl: MH-Beam/Ring/Movement, Bulbs, Fog, Mittelwert je Pixel-Fixture -> 1 kleiner Readback

GPU = {'on': False}

# Quellen-Indizes fuer probe_ctrl (Reihenfolge = Inputs 1.. des GLSL TOP)
SRC_BEAM, SRC_RING, SRC_MOVE, SRC_BULB, SRC_FOG, SRC_PIXAVG = 0, 1, 2, 3, 4, 5


def _uv_gain(root):
    s = root.op('settings')
    return s['visual_width'].eval() / s['visual_height'].eval()


POINTS_FILE = 'fixture_points.json'


def fixture_points(root, src):
    """2D-Punkte (x, y) aus <src>/geo_out. Kocht das Fixture nicht (Ausstellungsmodus, frisch geladene .toe),
    ist geo_out leer -> Fallback auf den Platten-Cache twin/fixture_points.json."""
    path = os.path.join(project.folder, 'twin', POINTS_FILE)
    disk = _cache.get('points_disk')
    if disk is None:
        disk = json.load(open(path)) if os.path.exists(path) else {}
        _cache['points_disk'] = disk
    g = root.op(src + '/geo_out')
    pts = [[p.x, p.y] for p in g.points] if g is not None else []
    if pts:
        if disk.get(src) != pts:
            disk[src] = pts
            with open(path, 'w') as f:
                json.dump(disk, f)
        return pts
    if src in disk:
        return disk[src]
    raise RuntimeError(f'Keine Punkte fuer {src}: Fixture kocht nicht und kein Cache in {POINTS_FILE}')


def cache_all_fixture_points(root):
    """Kocht alle Fixtures kurz, damit geo_out gefuellt ist, und schreibt den Platten-Cache."""
    c = cfg()
    srcs = [f['src'] for f in c['pixels']] + [m['src'] for m in c['movingheads']] + \
           [b['src'] for b in c['bulbs']] + [c['fog']['src']]
    for src in dict.fromkeys(srcs):
        comp = root.op(src)
        was = comp.allowCooking
        comp.allowCooking = True
        comp.op('geo_out').cook(force=True)
        fixture_points(root, src)
        comp.allowCooking = was


def _geo_uv(root, src, g):
    return [(x, y * g + (1.0 - g) / 2.0) for x, y in fixture_points(root, src)]


def pixel_maps(root):
    """Verschiedene Map-TOPs der Pixel-Fixtures (Input des Fixture-COMPs), in fester Reihenfolge."""
    maps = []
    for f in cfg()['pixels']:
        m = root.op(f['src']).inputs[0].path
        if m not in maps:
            maps.append(m)
    return maps


def probe_tables(root):
    """Statische Abtasttabellen (gecacht bis fixtures.json sich aendert oder rebuild_probes()).
    Returns dict pix (N,6), ctrl (M,6), keys (Name -> ctrl-Index)."""
    c = cfg()
    if 'probes' in _cache:
        return _cache['probes']
    g = _uv_gain(root)
    maps = pixel_maps(root)
    pix, ctrl, keys = [], [], {}

    starts = []
    for f in c['pixels']:
        fx = root.op(f['src'])
        src = maps.index(fx.inputs[0].path)
        master = fx.par.Master.eval() if hasattr(fx.par, 'Master') else 1.0
        white = fx.par.White.eval() if hasattr(fx.par, 'White') else 0.0
        starts.append(len(pix))
        for u, v in _geo_uv(root, f['src'], g):
            pix.append((u, v, src, master, white, 0.0))

    def add(key, u, v, src, start=0.0, count=0.0):
        keys[key] = len(ctrl)
        ctrl.append((u, v, src, start, count, 0.0))

    for i, mh in enumerate(c['movingheads']):
        uv = _geo_uv(root, mh['src'], g)
        add(f'mh{i}_beam', *uv[0], SRC_BEAM)
        for k in range(1, 5):
            add(f'mh{i}_ring{k}', *uv[k], SRC_RING)
        add(f'mh{i}_move', *uv[0], SRC_MOVE)
    for b in c['bulbs']:
        n = int(b['chan'].replace('Bulb', '')) - 1
        add(b['name'], *_geo_uv(root, b['src'], g)[n], SRC_BULB)
    add('fog', *_geo_uv(root, c['fog']['src'], g)[0], SRC_FOG)
    for f, st in zip(c['pixels'], starts):
        n = len(fixture_points(root, f['src']))
        add('avg_' + f['name'], 0.0, 0.0, SRC_PIXAVG, st, n)
    _cache['probes'] = {'pix': np.array(pix), 'ctrl': np.array(ctrl), 'keys': keys, 'maps': maps}
    return _cache['probes']


def rebuild_probes():
    """Nach Aenderungen an Fixture-Layout/Master/White aufrufen (Pulse 'Rebuild' der Twin-Base)."""
    _cache.pop('probes', None)
    _cache.pop('keys', None)


def cook_probe_pix_tab(scriptOp, root, t):
    p = probe_tables(root)['pix']
    write_chop(scriptOp, len(p), {'u': p[:, 0], 'v': p[:, 1], 'src': p[:, 2], 'gain': p[:, 3],
                                  'white': p[:, 4], 'r5': p[:, 5], 'r6': p[:, 5], 'r7': p[:, 5]})


def cook_probe_ctrl_tab(scriptOp, root, t):
    p = probe_tables(root)['ctrl']
    write_chop(scriptOp, len(p), {'u': p[:, 0], 'v': p[:, 1], 'src': p[:, 2], 'start': p[:, 3],
                                  'count': p[:, 4], 'r5': p[:, 5], 'r6': p[:, 5], 'r7': p[:, 5]})


def _ctrl(root):
    """Readback von probe_ctrl als (M,4)-Array, Index ueber probe_tables()['keys']."""
    keys = probe_tables(root)['keys']
    a = root.op('VISUAL_PREVIEW/twin/ctrl').numpyArray()   # Kanaele r,g,b,a, Samples = Probes
    return a.T, keys


def _gpu_dmx(root, src):
    """Rekonstruiert die benannten DMX-Werte (0..1) eines Fixtures aus der GPU-Abtastung
    plus den Custom Pars des Fixtures (die ohne Kochen lesbar bleiben)."""
    c = cfg()
    vals, keys = _ctrl(root)
    fx = root.op(src)
    P = lambda name, d=0.0: fx.par[name].eval() if fx.par[name] is not None else d
    for i, mh in enumerate(c['movingheads']):
        if mh['src'] != src:
            continue
        beam = vals[keys[f'mh{i}_beam']]
        move = vals[keys[f'mh{i}_move']]
        d = {'Pan': P('Pan', 0.5) + P('Panfine') / 255.0 + (move[0] - 0.5), 'Panfine': 0.0,
             'Tilt': P('Tilt', 0.5) + P('Tiltfine') / 255.0 + (move[1] - 0.5), 'Tiltfine': 0.0,
             'Dimmermain': P('Dimmermain', 1.0), 'Dimmerring': P('Dimmerring', 1.0),
             'Strobemain': P('Strobemain'), 'Strobering': P('Strobering'),
             'Led0r': beam[0], 'Led0g': beam[1], 'Led0b': beam[2], 'Led0white': P('Led0white')}
        for k in range(1, 5):
            rc = vals[keys[f'mh{i}_ring{k}']]
            d.update({f'Led{k}r': rc[0], f'Led{k}g': rc[1], f'Led{k}b': rc[2]})
        return d
    if src == c['fog']['src']:
        return {'Fog': vals[keys['fog']][0] * P('Fog', 1.0), 'Fan': P('Fan', 1.0)}
    d = {}
    for b in c['bulbs']:
        if b['src'] == src:
            d[b['chan']] = vals[keys[b['name']]][0] * P('Master', 1.0)
    return d


def _gpu_fixture_avg(root):
    vals, keys = _ctrl(root)
    return np.array([vals[keys['avg_' + f['name']]][:3] for f in cfg()['pixels']])
