# Espirit's Save Workshop (ESW)

Experimental Windows save editor for Metal Gear Solid: Peace Walker.

Includes Soldier Editor, Save Editor, and Loadout Editor. The Advanced Save Viewer tab has been removed. Loadouts support seven item slots and seven weapon slots; extended in-game capacity requires the corresponding runtime patch. The program icon contains a single 256x256 image.

## Run from source

Install Python 3.14 for Windows with Tcl/Tk support, then run:

```powershell
python -m pip install -r requirements.txt
python ssw/ssw.py
```

## Build

```powershell
powershell -ExecutionPolicy Bypass -File ./build.ps1
```

The build creates `dist/EspiritSaveWorkshop/EspiritSaveWorkshop.exe` alongside an `_internal` folder containing dependencies and resources. Distribute the entire `EspiritSaveWorkshop` folder; the executable requires `_internal` to remain beside it. This is a folder-based build, not an all-in-one executable. Build outputs and personal saves are excluded from Git.

Keep an untouched backup of your save. Experimental IDs and mission switches are not guaranteed playable. This editor does not install the seven-slot runtime patch automatically.

Optional local resource folders: `portrait_assets`, `staff_tag_assets`, `quote_assets`, `font_assets`, `voice_previews`, and `quote_plugin`. The build includes any present folders. Game-extracted artwork/audio and native game plugins are not included in this source repository; provide your own authorized copies locally for those features.
