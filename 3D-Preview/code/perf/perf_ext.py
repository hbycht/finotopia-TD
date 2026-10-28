"""PERF - Performance-Schalter fuer finotopia (Base COMP /project1/PERF, Parameter Execute).

Hintergrund (gemessen 2026-10-16, M1 Max / macOS 26 / TD 2025.33230): jeder TOP kostet pauschal
~0,4 ms CPU pro Cook. Darum werden TOP-Ketten, die nur rechnen, zu einzelnen GLSL TOPs zusammengefasst
bzw. nicht benoetigte Teile vom Kochen ausgenommen. Alles ist umschaltbar, die Originale bleiben erhalten.

Par 'Groupglsl'  : map_<G> wird von grp_<G> (code/perf/group_mix.glsl) statt von der Kette
                   ColorPicker_<G> -> dimmer_<G> -> correction_<G> gespeist.
Par 'Viscooking' : nur Visuals mit play_state > 0 kochen (Visual_Content_Controller/perf_vis_cooking).
Par 'Smallfixes' : MH_Move_Controller: math6 -> math1 -> math2 als ein Range-Math (math_mh_comb);
                   Visual_Content_Controller: switchFX Input 0 direkt von null1 statt ueber fx_NO_FX (Durchreichung).
"""

GROUPS = ('Beams', 'Rings', 'Blinder', 'Panel', 'Penta', 'Bulbs', 'Fog')


def _root():
    return parent.Project


def _top_out(comp):
    """Erster Ausgang eines COMPs, der von einem TOP gespeist wird (COMPs haben teils CHOP- und TOP-Ausgaenge)."""
    for c in comp.outputConnectors:
        if c.outOP is not None and c.outOP.isTOP:
            return c
    return None


def _orig_source(g):
    """Urspruenglicher Input von map_<G>."""
    r = _root()
    return r.op('correction_' + g) or _top_out(r.op('dimmer_' + g))


def _global_lut(gradientcomp):
    """Ein gemeinsamer Select auf <Gradientcomp>/gradient fuer alle Gruppen (kocht 1x statt 5x)."""
    r = _root()
    name = 'sel_lut_' + gradientcomp.name
    s = r.op(name) or r.create(selectTOP, name)
    s.par.top = gradientcomp.path + '/gradient'
    s.nodeX, s.nodeY = r.op('map_Beams').nodeX + 328, r.op('map_Beams').nodeY + 150
    return s


def build_groups():
    """Legt grp_<G> (+ sel_lut_<G>) an bzw. aktualisiert sie. Idempotent."""
    r = _root()
    for g in GROUPS:
        m = r.op('map_' + g)
        cp = r.op('ColorPicker_' + g)
        dm = r.op('dimmer_' + g)
        cr = r.op('correction_' + g)
        name = 'grp_' + g
        t = r.op(name) or r.create(glslmultiTOP, name)
        # Layout: je Gruppe eine Zeile rechts neben map_<G>: grp | sel_ramp | _pixel | _info
        t.nodeX, t.nodeY = m.nodeX + 178, m.nodeY
        for suf in ('_compute',):
            d = r.op(name + suf)
            if d:
                d.destroy()
        px = r.op(name + '_pixel')
        px.par.file = 'code/perf/group_mix.glsl'
        px.par.syncfile = True
        px.par.language = 'glsl'
        t.par.pixeldat = px.name
        px.nodeX, px.nodeY = t.nodeX + 300, t.nodeY
        info = r.op(name + '_info')
        if info:
            info.nodeX, info.nodeY = t.nodeX + 450, t.nodeY
        t.par.format = 'rgba16float'
        t.viewer = True

        src = (cp or dm).inputs[0]
        t.inputConnectors[0].connect(src)
        if cp:
            ramp = r.op('sel_ramp_' + g) or r.create(selectTOP, 'sel_ramp_' + g)
            ramp.nodeX, ramp.nodeY = t.nodeX + 150, t.nodeY
            ramp.par.top = 'ColorPicker_' + g + '/ramp1'
            t.inputConnectors[1].connect(ramp)
            t.inputConnectors[2].connect(_global_lut(cp.par.Gradientcomp.eval()))
            old = r.op('sel_lut_' + g)
            if old:
                old.destroy()
        else:
            # Shader referenziert Input 1/2 statisch; ohne LUT dieselbe Quelle anhaengen (wird nicht gelesen)
            t.inputConnectors[1].connect(src)
            t.inputConnectors[2].connect(src)

        t.par.vec.sequence.numBlocks = 3
        t.par.vec0name = 'uState'
        t.par.vec0valuex.expr = f"op('ColorPicker_{g}/saturation')['sat']" if cp else '1'
        t.par.vec0valuey.expr = f"op('dimmer_{g}/strobe_state')['strobe']"
        t.par.vec0valuez.expr = f"op('dimmer_{g}/strobe_phase')['strobe']"
        t.par.vec0valuew.expr = f"op('dimmer_{g}/dimmer')['master_fader']"
        t.par.vec1name = 'uFlash'
        t.par.vec1valuex.expr = f"op('dimmer_{g}/flash_state')['flash']"
        t.par.vec1valuey = 1 if cp else 0
        t.par.vec1valuez.expr = f"op('ColorPicker_{g}/gradient')['Value']" if cp else '0'
        t.par.vec2name = 'uHigh'
        for ch in 'rgb':
            p = getattr(t.par, 'vec2value' + {'r': 'x', 'g': 'y', 'b': 'z'}[ch])
            if cr:
                p.expr = f"op('correction_{g}').par.high{ch}"
            else:
                p.val = 1.0
    return [r.op('grp_' + g) for g in GROUPS]


PROBE_INPUTS = {'twin_probe_pix': ('Blinder', 'Panel', 'Penta'),
                'twin_probe_ctrl': ('Beams', 'Rings', None, 'Bulbs', 'Fog')}


def set_groups(on):
    r = _root()
    if on:
        build_groups()
    for g in GROUPS:
        m = r.op('map_' + g)
        m.inputConnectors[0].connect(r.op('grp_' + g) if on else _orig_source(g))
    # Twin-Probes lesen die Gruppen direkt (spart die map_*-Nulls, wenn die Fixtures aus sind)
    for probe, groups in PROBE_INPUTS.items():
        t = r.op(probe)
        if t is None:
            continue
        for i, g in enumerate(groups):
            if g:
                t.inputConnectors[i].connect(r.op(('grp_' if on else 'map_') + g))


def set_vis_cooking(on):
    v = _root().op('Visual_Content_Controller')
    e = v.op('perf_vis_cooking')
    if e is not None:
        e.par.active = on
    if on and e is not None:
        e.module.update()
    elif not on:
        # alle per Level angebundenen Visuals wieder freigeben
        for i in range(1, 9):
            lvl = v.op(f'level{i}')
            if lvl is not None and lvl.inputs:
                lvl.inputs[0].parent().allowCooking = True


def set_small(on):
    r = _root()
    m = r.op('MH_Move_Controller')
    m.op('movement').inputConnectors[0].connect(m.op('math_mh_comb') if on else m.op('math2'))
    v = r.op('Visual_Content_Controller')
    v.op('switchFX').inputConnectors[0].connect(v.op('null1') if on else _top_out(v.op('fx_NO_FX')))


def onValueChange(par, prev):
    if par.name == 'Groupglsl':
        set_groups(bool(par.eval()))
    elif par.name == 'Viscooking':
        set_vis_cooking(bool(par.eval()))
    elif par.name == 'Smallfixes':
        set_small(bool(par.eval()))
    return


def onPulse(par):
    if par.name == 'Rebuild':
        build_groups()
    return
