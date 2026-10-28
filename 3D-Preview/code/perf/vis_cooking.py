# CHOP Execute auf play_states (Visual_Content_Controller).
# Performance: visMix (Composite) zieht sonst alle 8 Visuals jeden Frame, auch bei Deckkraft 0.
# Hier darf ein vis_*-COMP nur kochen, solange sein play_state > 0 ist (beim Ueberblenden also beide).
# level<i>.opacity = play_states[i-1]; level<i> haengt am out1 des jeweiligen vis_*-COMPs.

THRESHOLD = 0.0005


def _vis_for_level(i):
    lvl = parent().op(f'level{i}')
    if lvl is None or not lvl.inputs:
        return None
    return lvl.inputs[0].parent()


def update():
    states = op('play_states')
    for i in range(1, states.numChans + 1):
        vis = _vis_for_level(i)
        if vis is not None and vis.name.startswith('vis_'):
            vis.allowCooking = states[i - 1].eval() > THRESHOLD


def onValueChange(channel, sampleIndex, val, prev):
    update()
    return


def onOffToOn(channel, sampleIndex, val, prev):
    return


def whileOn(channel, sampleIndex, val, prev):
    return


def onOnToOff(channel, sampleIndex, val, prev):
    return


def whileOff(channel, sampleIndex, val, prev):
    return
