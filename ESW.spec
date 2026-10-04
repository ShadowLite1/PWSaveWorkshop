from pathlib import Path

root = Path(SPECPATH)
datas = [(str(root / 'ssw' / 'assets' / 'app_icon.ico'), '.')]
for folder in ('portrait_assets', 'staff_tag_assets', 'quote_assets', 'font_assets', 'voice_previews', 'loadout_catalogs'):
    path = root / folder
    if path.exists():
        datas.append((str(path), folder))
plugin = root / 'quote_plugin' / 'PeaceWalkerCustomQuotes.asi'
if plugin.exists():
    datas.append((str(plugin), 'quote_plugin'))
a = Analysis([str(root / 'ssw' / 'ssw.py')], pathex=[str(root)], binaries=[], datas=datas, hiddenimports=['PIL._tkinter_finder'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='EspiritSaveWorkshop', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          contents_directory='_internal', icon=str(root / 'ssw' / 'assets' / 'app_icon.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='EspiritSaveWorkshop')
