# Compilation : pyinstaller recherche_globale.spec
a = Analysis(
    ["recherche_globale.py"],
    datas=[("web/index.html", "web")],
    excludes=["tkinter", "unittest", "pydoc"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="RechercheGlobale",
    console=True,
    upx=False,
)
