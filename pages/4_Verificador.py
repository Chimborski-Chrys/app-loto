import os as _os

_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
with open(_os.path.join(_root, "app_verificador.py"), encoding="utf-8") as _f:
    exec(_f.read())
