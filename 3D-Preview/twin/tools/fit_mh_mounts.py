"""Fittet die Montage-Orientierung der Moving Heads aus finotopia-Positions-Presets.

Modell (alle MOVO Beam 100): Strahl = cos(th)*u + sin(th)*(cos(ph)*f + sin(ph)*(u x f))
  th = (Tilt - 0.5) * 270 deg,  ph = pan_sign * (Pan - 0.5) * 540 deg
  u = Strahlrichtung bei Tilt-Mitte (Sockel-Normale), f = Pan-Nullrichtung (senkrecht zu u)
Kalibrierung: DMX-Werte (Pan, Tilt) der Presets 'Down' (alle senkrecht nach unten) und
'Center' (alle treffen sich auf dem Boden in C). Decken-MHs: u = (0,-1,0) fest.
Wand-MHs (31/32): u frei, als Spiegelpaar (x gespiegelt, Pan-Vorzeichen gespiegelt).

Aufruf: python3 fit_mh_mounts.py calib.json fixtures.json  -> schreibt 'mount' je MH in fixtures.json
"""
import json, sys
import numpy as np

P_RANGE, T_RANGE = 540.0, 270.0


def beam(u, f, pan, tilt, sp):
    r = np.cross(u, f)
    th = np.radians((tilt - 0.5) * T_RANGE)
    ph = np.radians(sp * (pan - 0.5) * P_RANGE)
    return np.cos(th) * u + np.sin(th) * (np.cos(ph) * f + np.sin(ph) * r)


def ang(a, b):
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    return np.degrees(np.arccos(np.clip(a @ b, -1, 1)))


def frame(u, alpha):
    u = u / np.linalg.norm(u)
    ref = np.array([0, 0, -1.0]) if abs(u[2]) < 0.9 else np.array([1.0, 0, 0])
    b1 = ref - u * (ref @ u); b1 /= np.linalg.norm(b1); b2 = np.cross(u, b1)
    return u, np.cos(alpha) * b1 + np.sin(alpha) * b2


def head_pos(mh):
    return np.array(mh['pos']) + np.array([0, -0.32, 0])


def err(mh, cal, u, f, sp, C):
    hp = head_pos(mh)
    e1 = ang(beam(u, f, *cal['down'][mh['name']], sp), np.array([0, -1.0, 0]))
    e2 = ang(beam(u, f, *cal['center'][mh['name']], sp), C - hp)
    return e1 + e2, e1, e2


def fit_ceiling(mh, cal, C):
    u = np.array([0, -1.0, 0]); best = None
    for sp in (1, -1):
        for a in np.radians(np.arange(0, 360, 0.25)):
            uu, f = frame(u, a)
            e = err(mh, cal, uu, f, sp, C)
            if best is None or e[0] < best[0][0]:
                best = (e, uu, f, sp)
    return best


def fit_wall_pair(m_left, m_right, cal, C):
    best = None
    mirror = np.array([-1.0, 1, 1])
    for el in np.radians(np.arange(-89, 0, 1.0)):
        for az in np.radians(np.arange(0, 360, 2.0)):
            u = np.array([np.cos(el) * np.sin(az), np.sin(el), np.cos(el) * np.cos(az)])
            for a in np.radians(np.arange(0, 360, 4.0)):
                uu, f = frame(u, a)
                for sp in (1, -1):
                    eL = err(m_left, cal, uu, f, sp, C)
                    uR, fR = uu * mirror, f * mirror
                    eR = err(m_right, cal, uR, fR, -sp, C)
                    tot = eL[0] + eR[0]
                    if best is None or tot < best[0]:
                        best = (tot, (eL, uu, f, sp), (eR, uR, fR, -sp))
    return best


if __name__ == '__main__' and not (len(sys.argv) > 3 and sys.argv[3] == 'wall'):
    cal = json.load(open(sys.argv[1]))
    path = sys.argv[2]
    fx = json.load(open(path))
    C = np.array(cal['center_target'])
    mhs = {m['name']: m for m in fx['movingheads']}
    for name, m in mhs.items():
        if name in ('MOVO31', 'MOVO32'):
            continue
        e, u, f, sp = fit_ceiling(m, cal, C)
        m['mount'] = {'u': np.round(u, 4).tolist(), 'f': np.round(f, 4).tolist(), 'pan_sign': sp}
        print(f"{name}: err down {e[1]:.1f} / center {e[2]:.1f} deg  f={np.round(f, 3)} sp={sp}")
    tot, L, R = fit_wall_pair(mhs['MOVO31'], mhs['MOVO32'], cal, C)
    for name, (e, u, f, sp) in (('MOVO31', L), ('MOVO32', R)):
        mhs[name]['mount'] = {'u': np.round(u, 4).tolist(), 'f': np.round(f, 4).tolist(), 'pan_sign': sp}
        print(f"{name}: err down {e[1]:.1f} / center {e[2]:.1f} deg  u={np.round(u, 3)} f={np.round(f, 3)} sp={sp}")
    fx['settings']['mh_model'] = 'mount: beam = cos(th)u + sin(th)(cos(ph)f + sin(ph)(u x f)); th=(Tilt-0.5)*270, ph=pan_sign*(Pan-0.5)*540'
    json.dump(fx, open(path, 'w'), indent=2)


def solve_wall(mh, cal, C):
    """u liegt auf dem Schnitt zweier Kegel (Tilt-Winkel zu 'Down' und zu 'Center');
    fuer diese Kandidaten werden Pan-Nullrichtung f und Pan-Vorzeichen mit dem echten Modell gesucht."""
    hp = head_pos(mh)
    pd, td = cal['down'][mh['name']]
    pc, tc = cal['center'][mh['name']]
    dd = np.array([0, -1.0, 0]); dc = (C - hp) / np.linalg.norm(C - hp)
    thd, thc = np.radians((td - 0.5) * T_RANGE), np.radians((tc - 0.5) * T_RANGE)
    best = None
    for beta in np.radians(np.arange(0, 360, 0.1)):
        u = np.array([np.sin(abs(thd)) * np.sin(beta), -np.cos(abs(thd)), np.sin(abs(thd)) * np.cos(beta)])
        if abs(np.degrees(np.arccos(np.clip(u @ dc, -1, 1))) - np.degrees(abs(thc))) > 1.0:
            continue
        for a in np.radians(np.arange(0, 360, 0.5)):
            uu, f = frame(u, a)
            for sp in (1, -1):
                e1 = ang(beam(uu, f, pd, td, sp), dd); e2 = ang(beam(uu, f, pc, tc, sp), dc)
                if best is None or e1 + e2 < best[0][0]:
                    best = ((e1 + e2, e1, e2), uu, f, sp)
    return best


if __name__ == '__main__' and len(sys.argv) > 3 and sys.argv[3] == 'wall':
    cal = json.load(open(sys.argv[1])); path = sys.argv[2]; fx = json.load(open(path))
    C = np.array(cal['center_target'])
    for m in fx['movingheads']:
        if m['name'] in ('MOVO31', 'MOVO32'):
            e, u, f, sp = solve_wall(m, cal, C)
            m['mount'] = {'u': np.round(u, 4).tolist(), 'f': np.round(f, 4).tolist(), 'pan_sign': sp}
            vb = beam(u, f, *cal['v'][m['name']], sp)
            print(f"{m['name']}: err down {e[1]:.2f} / center {e[2]:.2f} deg  u={np.round(u,3)} f={np.round(f,3)} sp={sp}  V-dir={np.round(vb,2)}")
    json.dump(fx, open(path, 'w'), indent=2)
