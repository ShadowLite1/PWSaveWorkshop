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

Resources are stored in `portrait_assets`, `staff_tag_assets`, `quote_assets`, `font_assets`, and `voice_previews`, matching the Soldier Editor source layout. Native plugin source is in `quote_plugin` and `plugins`, with MinHook in `third_party/minhook`.

The `asi` folder contains complete plugin files: Custom Quotes (user-confirmed working), Seven Slots v3 (seven items/weapons tested in gameplay), Eight Skills (stable release), and Cross Battle Input v1 (accepted after successful initialization and controls testing). The Cross Battle filename retains its original Test name; the shipped file is the accepted auto-activating build. Prototype, observer, capture, and unfinished box/Versus effect plugins are excluded.

The build copies `asi` beside the executable, separately from `_internal`. To install a plugin, copy the desired ASI into the game's `mgspw/scripts` folder with a compatible ASI loader. Restart the game after changing plugins. ESW's quote installation button reads its plugin from `asi`.

The package also includes `PeaceWalkerStrikeTableTest_v1.asi` (strike arrival confirmed in testing) and `PeaceWalkerVersusEquipment_v4.asi` (Versus equipment access). Equipment access does not restore every Co-op effect; ASSN/Rescue Box behavior remains unfinished.

To rebuild the native plugins, install Visual Studio C++ Build Tools and run `build_plugins.bat`. This replaces the six files in `asi` with newly compiled versions. The checked-in ASIs are the existing working builds.
