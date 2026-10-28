# Hilfsfunktionen fuer die Analyse per TDMCP execute_code:
#   exec(open(project.folder + '/twin/tools/td_inspect.py').read())
#   print(chain(op('...')))


def chain(o, depth=0, seen=None, maxdepth=12):
    """Upstream-Kette eines Operators als eingerueckter Text, mit nicht-default Parametern."""
    seen = seen if seen is not None else set()
    if o.path in seen or depth > maxdepth:
        return ''
    seen.add(o.path)
    pars = {}
    for p in o.pars():
        try:
            if p.isCustom or p.isDefault or (p.page and p.page.name == 'Common'):
                continue
            pars[p.name] = p.expr if p.mode == ParMode.EXPRESSION else p.eval()
        except Exception:
            pass
    lines = ['  ' * depth + f"{o.name}:{o.OPType} {str(pars)[:240]}"]
    for i in o.inputs:
        if i:
            sub = chain(i, depth + 1, seen, maxdepth)
            if sub:
                lines.append(sub)
    return '\n'.join(lines)
