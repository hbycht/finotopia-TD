"""Zeigt fuer jedes MH-Preset, wo die Strahlen im Raum auftreffen (Modell wie im Twin).
Aufruf: python3 preset_hits.py [presets.json]   (Default: ref/presets_current.json, sonst Backup + presets_new)"""
import json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from solve_presets import BASE, POS, DROP, TILT_OFF, P_RANGE, T_RANGE, unit, ortho_f

room = json.load(open(os.path.join(BASE, 'room.json')))['dims']


def half_w(z):
    return (room['width_front'] + (room['width_back'] - room['width_front']) * z / room['length']) / 2


def ceil(z):
    return room['ceil_front'] + (room['ceil_back'] - room['ceil_front']) * z / room['length']


def ray(mh, v1, v2):
    u, f, sp = unit(mh['mount']['u']), ortho_f(mh['mount']), mh['mount']['pan_sign']
    th = math.radians((v2 - TILT_OFF - 0.5) * T_RANGE); ph = math.radians(sp * (v1 - 0.5) * P_RANGE)
    d = math.cos(th) * u + math.sin(th) * (math.cos(ph) * f + math.sin(ph) * np.cross(u, f))
    return np.array(mh['pos']) + u * DROP, d


def hit(h, d):
    """Erster Treffer mit Boden/Decke/Waenden -> (Flaeche, Punkt)."""
    best = (1e9, None)
    def cand(t, name):
        nonlocal best
        if 1e-4 < t < best[0]:
            p = h + t * d
            if -1e-3 <= p[2] <= room['length'] + 1e-3 and abs(p[0]) <= half_w(p[2]) + 1e-3 and -1e-3 <= p[1] <= ceil(p[2]) + 1e-3:
                best = (t, name)
    if abs(d[1]) > 1e-9: cand(-h[1] / d[1], 'Boden')
    if abs(d[2]) > 1e-9: cand(-h[2] / d[2], 'DJ-Wand'); cand((room['length'] - h[2]) / d[2], 'Bar-Wand')
    k = (room['width_back'] - room['width_front']) / 2 / room['length']
    for s, name in ((1, 'Wand rechts'), (-1, 'Wand links')):      # x = s*(w0/2 + k z)
        den = d[0] - s * k * d[2]
        if abs(den) > 1e-9: cand((s * (room['width_front'] / 2 + k * h[2]) - h[0]) / den, name)
    for _ in range(1):                                            # Decke (linear in z)
        kc = (room['ceil_back'] - room['ceil_front']) / room['length']
        den = d[1] - kc * d[2]
        if abs(den) > 1e-9: cand((room['ceil_front'] + kc * h[2] - h[1]) / den, 'Decke')
    t, name = best
    return name, (h + t * d) if name else None


if __name__ == '__main__':
    fx = json.load(open(os.path.join(BASE, 'fixtures.json')))
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, 'ref/presets_current.json')
    pres = json.load(open(src))
    for preset, vals in pres.items():
        if not preset.startswith('pos_'): continue
        print('==', preset)
        for mh in fx['movingheads']:
            p = POS[mh['name']]
            v1, v2 = vals[p + '_v1'], vals[p + '_v2']
            h, d = ray(mh, v1, v2)
            name, pt = hit(h, d)
            print(f"  {mh['name']}  v=({v1:.3f},{v2:.3f})  dir={np.round(d, 2)}  -> {name} {np.round(pt, 2) if pt is not None else ''}")
