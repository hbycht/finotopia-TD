# Gemeinsame Callbacks fuer alle Script CHOPs der Twin-Base.
# Script CHOP 'xyz' -> twin_lib.cook_xyz(scriptOp, root, t)

# Diese Script CHOPs haengen nur von statischen Daten ab und muessen nicht jeden Frame kochen.
STATIC = ('pix_pos', 'shades', 'probe_pix_tab', 'probe_ctrl_tab')


def onCook(scriptOp):
    lib = op('twin_lib').module
    lib.TEST['on'] = bool(parent.Twin.par.Testmode) if hasattr(parent.Twin.par, 'Testmode') else False
    lib.TEST['t'] = absTime.seconds
    lib.GPU['on'] = bool(parent.Twin.par.Exhibition) if hasattr(parent.Twin.par, 'Exhibition') else False
    try:
        getattr(lib, 'cook_' + scriptOp.name)(scriptOp, parent.Project, absTime.seconds)
    except Exception as e:
        # sichtbar machen statt still einzufrieren
        scriptOp.addError(f'{type(e).__name__}: {e}')
        raise
    return


def onGetCookLevel(scriptOp):
    if scriptOp.name in STATIC:
        return CookLevel.AUTOMATIC
    # im Ausstellungsmodus kommen die Pixelfarben direkt aus twin_probe_pix
    if scriptOp.name == 'pix_col' and getattr(parent.Twin.par, 'Exhibition', False):
        return CookLevel.WHEN_USED
    return CookLevel.ALWAYS


def onSetupParameters(scriptOp):
    return


def onPulse(par):
    return
