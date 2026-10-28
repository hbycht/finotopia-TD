# Parameter Execute der Twin-Base: schaltet den Ausstellungsmodus (Par 'Exhibition').
#
# An:  node*-Fixtures, Prototypes und DMX-Controller kochen nicht mehr (kein DMX, keine
#      toptoCHOP-Readbacks). Der Twin tastet die map_*-Texturen selbst ab:
#      /project1/twin_probe_pix  -> LED-Farben direkt ins Instancing
#      /project1/twin_probe_ctrl -> MH/Bulbs/Fog ueber VISUAL_PREVIEW/twin/ctrl (1 Readback)
# Aus: alles wie im Clubbetrieb, der Twin liest col_out / DMX_CH_RENAMER der Fixtures.
# Pulse 'Rebuild': Pixel-Layout und Abtasttabellen neu aus den Fixtures (geo_out, Master, White) lesen.
# Die 2D-Punkte der Fixtures liegen zusaetzlich in twin/fixture_points.json, damit der Twin auch nach einem
# Neustart mit abgeschalteten Fixtures (gespeicherter Ausstellungsmodus) funktioniert.

PREFIXES = ('node', 'DMX_Controller', 'prototype_', 'dimmer_prototype', 'ColorPicker_prototype')


def apply(on):
    root = parent.Project
    lib = parent.Twin.op('twin_lib').module
    if on:
        # Fixture-Punkte sichern, solange die Fixtures noch kochen (Twin liest sie danach aus dem Cache)
        lib.cache_all_fixture_points(root)
    for c in root.children:
        if c.isCOMP and c.name.startswith(PREFIXES):
            c.allowCooking = not on
    geo = parent.Twin.op('geo_pixels')
    if on:
        geo.par.instancecolorop.expr = "parent.Project.op('twin_probe_pix')"
    else:
        geo.par.instancecolorop.expr = "parent.Twin.op('pix_col')"
    for n in ('pix_col', 'mh', 'bulbs', 'lights', 'fog'):
        parent.Twin.op(n).cook(force=True)


def onValueChange(par, prev):
    if par.name == 'Exhibition':
        apply(bool(par.eval()))
    return


def onPulse(par):
    if par.name == 'Rebuild':
        lib = parent.Twin.op('twin_lib').module
        lib.cache_all_fixture_points(parent.Project)
        lib.rebuild_probes()
        for n in ('pix_pos', 'shades', 'probe_pix_tab', 'probe_ctrl_tab'):
            parent.Twin.op(n).cook(force=True)
    return


def onValuesChanged(changes):
    return


def onExpressionChange(par, val, prev):
    return


def onExportChange(par, val, prev):
    return


def onEnableChange(par, val, prev):
    return


def onModeChange(par, val, prev):
    return
