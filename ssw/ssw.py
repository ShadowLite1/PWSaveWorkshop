from __future__ import annotations

import shutil
import struct
import sys
import json
import re
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from edit_save import update_internal_checks
from save_cipher import derive_state, filename_checksum, transform
from soldier_editor import SoldierEditor

SAVE_SIZE = 0x4F950
ROSTER_BASE = 0x1FA80
ROSTER_RECORD_SIZE = 0xA0
ROSTER_COUNT = 350
NAME_OFFSET = 0x20
NAME_SIZE = 16
ASSIGNMENT_OFFSET = 0x30
COMBAT_UNIT_ASSIGNMENT = 0x02
# The Mission Prep records begin here.  The earlier B800 table is record 3,
# not the active Campaign/Co-op record shown by Mission Prep.
PRESET_BASE = 0xB61A
PRESET_STRIDE = 0xA2
ITEM_OFFSET = 0x04
WEAPON_OFFSET = 0x54
ITEM_SLOT_COUNT = 7
WEAPON_SLOT_COUNT = 7
ACTIVE_SOLDIER_NAME_OFFSET = 0x44C
ACTIVE_SOLDIER_RECORD_OFFSET = 0x42C
UNIFORM_OFFSETS = (0xB5E4, 0xB5E8, 0xB7D2)
UNIFORM_NAMES = (
    "SNEAKING", "BATTLE W/H", "J.FATIGUES", "LEAF", "T-STRIPE", "CHOCO-CHIP",
    "AUSCAM", "SQUARES", "SPLITTER", "SNAKE", "NEO MOSS", "STENCH", "TIGREX",
    "RATHALOS", "GEAR REX", "NAKED", "NKD(LEAF)", "NKD(TIGER)", "NKD(CHOCO)",
    "NKD(AUSY)", "NKD(SQRS)", "NKD(SPLIT)", "NKD(SNAKE)", "TUXEDO", "MILLER",
    "SWIM TRNKS", "T-SHIRT", "BLACK", "KHAKI", "NAVY BLUE", "WHITE", "RED",
    "YELLOW", "PINK", "GREEN", "WATER", "TREE BARK", "DPM", "COMRADE", "G&J",
    "NKD(BLACK)", "NKD(KHAKI)", "NKD(N.BLU)", "NKD(WHITE)", "NKD(RED)",
    "NKD(YELW)", "NKD(PINK)", "NKD(GRN)", "NKD(WATR)", "NKD(T.B)", "NKD(DPM)",
    "LOVE BOX",
)
UNIFORMS = {index: name for index, name in enumerate(UNIFORM_NAMES, start=1)}

# Recruited-soldier Versus uniforms use a character-specific interpretation of
# the middle persisted uniform byte.  ESCORT=55 is confirmed by a controlled
# SEA LION save; the contiguous preceding values follow the game's ordered
# role catalog and remain labeled inferred until individually captured.
VERSUS_ROLE_UNIFORMS = {
    47: "R.COMMANDO (inferred)",
    48: "R.SOLDIER (inferred)",
    49: "SCOUT (inferred)",
    50: "GUARD (inferred)",
    51: "COMMANDO (inferred)",
    52: "M.POW (inferred)",
    53: "PATROLMAN (inferred)",
    54: "MECHANIC (inferred)",
    55: "ESCORT (confirmed)",
}
VERSUS_ROLE_UNIFORM_OFFSET = 0xB5E8
LEAVE_ROLE_UNCHANGED = "Leave recruited-soldier role unchanged"

WARNING = (
    "Debug features might be unstable and we are not responsible for save "
    "corruption, continue?"
)

def load_equipment_catalogs() -> tuple[
    dict[int, str], dict[int, str], dict[int, dict], dict[int, dict]
]:
    # Ghidra/runtime inspection confirmed that OLANG keys and STW storage IDs
    # are separate namespaces.  Never label a storage ID merely because the
    # same number exists in an OLANG table.  Unknown values remain available
    # so an existing save can be inspected and round-tripped without loss.
    # Preserve the complete raw storage-ID ranges for inspection. Known
    # values are overlaid below. Unknown values remain visible but are unsafe
    # so an accidental OLANG-key-as-storage-ID write requires confirmation.
    items = {value: "Unmapped storage ID" for value in range(0x200)}
    weapons = {value: "Unmapped storage ID" for value in range(0x400)}
    items[0] = "Empty"
    weapons[0] = "Empty"
    item_info: dict[int, dict] = {
        value: {"confidence": "unmapped", "selectable": False, "evidence": []}
        for value in items
    }
    weapon_info: dict[int, dict] = {
        value: {"confidence": "unmapped", "selectable": False, "evidence": []}
        for value in weapons
    }
    item_info[0] = {"confidence": "confirmed", "selectable": True, "evidence": ["empty value"]}
    weapon_info[0] = {"confidence": "confirmed", "selectable": True, "evidence": ["empty value"]}
    try:
        crosswalk = ROOT / "loadout_catalogs" / "storage_olang_crosswalk.json"
        legacy_mapping = ROOT / "loadout_catalogs" / "storage_id_map.json"
        # Load the broad OLANG-assisted crosswalk first, then overlay the
        # direct in-game storage-ID observations.  The latter is authoritative
        # for the exact names/ranks displayed by Mission Prep.
        external_reference = ROOT / "loadout_catalogs" / "external_equipped_weapon_names.json"
        catalog_paths = (external_reference, crosswalk, legacy_mapping)
        loaded_any = False
        for catalog_path in catalog_paths:
            if not catalog_path.exists():
                continue
            mapping = json.loads(catalog_path.read_text(encoding="utf-8"))
            loaded_any = True
            for key, record in mapping.get("items", {}).items():
                value = int(key, 16)
                items[value] = str(record["name"])
                item_info[value] = {
                    "confidence": str(record.get("confidence", "candidate")),
                    "selectable": bool(record.get("selectable", True)),
                    "evidence": list(record.get("evidence", [])),
                }
            for key, record in mapping.get("weapons", {}).items():
                value = int(key, 16)
                # Keep blank, debug and pseudo entries visible.  Hiding them
                # made existing values appear to vanish and prevented exact
                # raw-ID inspection.  Their safety state is shown separately.
                weapons[value] = str(record["name"])
                weapon_info[value] = {
                    "confidence": str(record.get("confidence", "candidate")),
                    "selectable": bool(record.get("selectable", True)),
                    "evidence": list(record.get("evidence", [])),
                }
        manual_weapon_map = (
            ROOT / "loadout_catalogs" / "manual_weapon_storage_ids_2026-09-30.json"
        )
        if manual_weapon_map.exists():
            document = json.loads(manual_weapon_map.read_text(encoding="utf-8"))
            source = str(document.get("source", "direct in-game manual testing"))
            for key, name_value in document.get("weapons", {}).items():
                value = int(key, 16)
                name = str(name_value)
                normalized_name = name.strip().upper()
                is_unsafe = (
                    normalized_name == "BLANK"
                    or "UNKNOWNVAR" in normalized_name
                    or "UNSUPPRESSED VARIANT" in normalized_name
                )
                weapons[value] = name
                weapon_info[value] = {
                    "confidence": "manual-observation",
                    "selectable": not is_unsafe,
                    "evidence": [source],
                }
        if not loaded_any:
            raise OSError("No loadout storage-ID catalog was found")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        pass
    return items, weapons, item_info, weapon_info


ITEMS, WEAPONS, ITEM_INFO, WEAPON_INFO = load_equipment_catalogs()
LOADOUT_MODES = {
    "Active selected character — Campaign / Co-op": (0,),
    "Versus Ops — original preset": (3,),
    "Versus Ops — MSF soldier": (4,),
    "Mission Prep record 2 — experimental": (1,),
    "Mission Prep record 3 — experimental": (2,),
}


@dataclass(frozen=True)
class MissionFlag:
    name: str
    offsets: tuple[int, ...]
    mask: int
    note: str


@dataclass(frozen=True)
class MissionProfile:
    name: str
    writes: tuple[tuple[int, int], ...]
    note: str


# Exact mission-menu state shared by the save that visibly displays the SBM
# cutscenes and the earlier isolated working probe.  This is a visibility
# profile, not a completion bit.  Keep it separate from MISSION_FLAGS so the
# ordinary bit-toggle code cannot silently reduce it to one byte.
SBM_PROFILE = MissionProfile(
    "SBM025 / 027 / 028 / 035 / 039",
    (
        (0xB530, 0x08), (0xB567, 0x1F),
        (0x1C46A, 0x7F), (0x1C46C, 0x77), (0x1C46F, 0xFB),
        (0x1C470, 0xDA), (0x1C471, 0x67), (0x1C473, 0x13),
        (0x1C478, 0x25), (0x1C47A, 0x10), (0x1C47B, 0xAA),
        (0x1C47C, 0xBF), (0x1C47D, 0x7F), (0x1C481, 0x1E),
        (0x1C483, 0x42), (0x1C484, 0x00), (0x1C485, 0xFC),
        (0x1C487, 0x1F), (0x1C489, 0x00),
    ),
    "Verified menu profile; may alter normal mission visibility",
)


MISSION_FLAGS = (
    MissionFlag("M0140 / ABOUT M0140", (0x1C46C,), 0x08, "Internal Main Ops entry"),
    MissionFlag("M0230 / Pursue Peace Walker", (0x1C46A,), 0x80, "Internal Main Ops entry"),
    MissionFlag("[017] FULTON RECOVERY", (0x1C46F,), 0x04, "Internal duplicate"),
    MissionFlag("[058] DEFEND KEY SUPPLIES", (0x1C470,), 0x20, "Internal duplicate"),
    MissionFlag("[120] METAL GEAR ZEKE — CROSS BATTLE", (0x1C483,), 0x80, "Menu entry confirmed; requires Cross Battle ASI"),
)

MISSION_REFERENCE = {}
_mission_catalog = ROOT / "mission_catalogs" / "internal_missions.json"
if _mission_catalog.is_file():
    _reference_entries = json.loads(_mission_catalog.read_text(encoding="utf-8"))["entries"]
    _known_bits = {(m.offsets[0], m.mask) for m in MISSION_FLAGS}
    _extra_flags = []
    for _entry in _reference_entries:
        _id = _entry["reference_id_decimal"]
        _bit = (0x1C468 + _id // 8, 1 << (_id % 8))
        MISSION_REFERENCE[_bit] = _entry
        if _bit not in _known_bits:
            _extra_flags.append(MissionFlag(
                (re.search(r"\b(?:sbm\d+|m\d{4})\b", _entry['title'], re.IGNORECASE).group(0).upper()
                 if re.search(r"\b(?:sbm\d+|m\d{4})\b", _entry['title'], re.IGNORECASE)
                 else f"Internal ID {_id:03d}"), (_bit[0],), _bit[1],
                "Reference marks not incorporated" if _entry["marked_not_incorporated"] else "Experimental reference-ID mapping",
            ))
            _known_bits.add(_bit)
    MISSION_FLAGS += tuple(_extra_flags)


class SaveSession:
    def __init__(self) -> None:
        self.data: bytearray | None = None
        self.source: Path | None = None
        self.header_index: int | None = None
        self.listeners: list[callable] = []

    def subscribe(self, callback) -> None:
        self.listeners.append(callback)

    def notify(self) -> None:
        for callback in self.listeners:
            callback()

    def open(self, path: Path) -> None:
        encrypted = bytearray(path.read_bytes())
        if len(encrypted) != SAVE_SIZE:
            raise ValueError(f"Expected {SAVE_SIZE:,} bytes; found {len(encrypted):,}.")
        index, *_ = derive_state(encrypted)
        transform(encrypted, index)
        if encrypted[0x40:0x44] != b"oEbN":
            raise ValueError("This is not a supported Peace Walker PC STW save.")
        self.data = encrypted
        self.source = path
        self.header_index = index
        self.notify()

    def save_as(self, path: Path) -> str:
        if self.data is None or self.header_index is None:
            raise ValueError("Open a save first.")
        output = bytearray(self.data)
        update_internal_checks(output)
        transform(output, self.header_index)
        expected = f"STW000000{filename_checksum(output):04x}01"
        if self.source and path.resolve() == self.source.resolve():
            shutil.copy2(self.source, self.source.with_name(self.source.name + ".backup"))
        path.write_bytes(output)
        return expected


class InternalMissionTab(ttk.Frame):
    def __init__(self, master, session: SaveSession) -> None:
        super().__init__(master, padding=16)
        self.session = session
        self.vars = [tk.BooleanVar() for _ in MISSION_FLAGS]
        self.sbm_var = tk.BooleanVar()
        self.sbm_original: dict[int, int] | None = None
        self.unlocked = False
        ttk.Label(self, text="SAVE EDITOR", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(
            self,
            text="Internal Missions are experimental. Always keep an untouched backup.",
            foreground="#c93b31",
        ).pack(anchor="w", pady=(0, 12))
        self.columnconfigure(0, weight=1, uniform="mission_panes")
        self.columnconfigure(2, weight=1, uniform="mission_panes")
        self.rowconfigure(2, weight=1)
        # Convert the title area to grid before creating the split panes.
        title_widgets = self.winfo_children()
        for widget in title_widgets:
            widget.pack_forget()
        for row, widget in enumerate(title_widgets):
            widget.grid(row=row, column=0, sticky="w", pady=(0, 12))
        left = ttk.Frame(self)
        left.grid(row=2, column=0, sticky="new", padx=(0, 6))
        tk.Frame(self, bg="#111111", width=3).grid(row=0, column=1, rowspan=3, sticky="ns")
        right = ttk.Frame(self)
        right.grid(row=2, column=2, sticky="new", padx=(6, 0))
        panels = []
        scroll_handlers = []
        for pane in (left, right):
            group = ttk.LabelFrame(pane, text="Internal Missions", padding=8)
            group.pack(fill="x", anchor="n")
            canvas = tk.Canvas(group, height=200, highlightthickness=0, bg="#d6d5bd")
            scrollbar = ttk.Scrollbar(group, orient="vertical", command=canvas.yview)
            scrollbar.pack(side="right", fill="y")
            canvas.pack(fill="both", expand=True)
            canvas.configure(yscrollcommand=scrollbar.set)
            panel = ttk.Frame(canvas, padding=4)
            window = canvas.create_window((0, 0), window=panel, anchor="nw")
            panel.bind("<Configure>", lambda _e, c=canvas: c.configure(scrollregion=c.bbox("all")))
            canvas.bind("<Configure>", lambda e, c=canvas, w=window: c.itemconfigure(w, width=e.width))
            def scroll(event, c=canvas):
                c.yview_scroll(-int(event.delta / 120), "units")
            canvas.bind("<MouseWheel>", scroll)
            panel.bind("<MouseWheel>", scroll)
            panels.append(panel)
            scroll_handlers.append(scroll)
        split = (len(MISSION_FLAGS) + 1) // 2
        for index, mission in enumerate(MISSION_FLAGS):
            column = 0 if index < split else 1
            line = ttk.Frame(panels[column])
            line.pack(fill="x", pady=4)
            check = ttk.Checkbutton(
                line,
                text=mission.name.split(" / ", 1)[0],
                variable=self.vars[index],
                command=lambda i=index: self.changed(i),
            )
            check.pack(anchor="w")
            check.bind("<MouseWheel>", scroll_handlers[column])
        sbm_line = ttk.Frame(panels[1])
        sbm_line.pack(fill="x", pady=4)
        ttk.Checkbutton(
            sbm_line,
            text=SBM_PROFILE.name,
            variable=self.sbm_var,
            command=self.sbm_changed,
        ).pack(side="left")
        self.session.subscribe(self.refresh)

    def flag_value(self, mission: MissionFlag) -> bool:
        assert self.session.data is not None
        return all(self.session.data[offset] & mission.mask for offset in mission.offsets)

    def refresh(self) -> None:
        if self.session.data is None:
            for variable in self.vars:
                variable.set(False)
            self.sbm_var.set(False)
            self.sbm_original = None
            return
        for variable, mission in zip(self.vars, MISSION_FLAGS):
            variable.set(self.flag_value(mission))
        self.sbm_var.set(all(self.session.data[offset] == value for offset, value in SBM_PROFILE.writes))

    def changed(self, index: int) -> None:
        if self.session.data is None:
            messagebox.showinfo("No save open", "Open a save first.")
            self.vars[index].set(False)
            return
        if not self.unlocked:
            if not messagebox.askyesno("Experimental debug features", WARNING, icon="warning"):
                self.refresh()
                return
            self.unlocked = True
        mission = MISSION_FLAGS[index]
        enabled = self.vars[index].get()
        for offset in mission.offsets:
            if enabled:
                self.session.data[offset] |= mission.mask
            else:
                self.session.data[offset] &= (~mission.mask) & 0xFF

    def sbm_changed(self) -> None:
        if self.session.data is None:
            messagebox.showinfo("No save open", "Open a save first.")
            self.sbm_var.set(False)
            return
        if not self.unlocked:
            if not messagebox.askyesno("Experimental debug features", WARNING, icon="warning"):
                self.refresh()
                return
            self.unlocked = True
        if self.sbm_var.get():
            self.sbm_original = {
                offset: self.session.data[offset] for offset, _ in SBM_PROFILE.writes
            }
            for offset, value in SBM_PROFILE.writes:
                self.session.data[offset] = value
            messagebox.showwarning(
                "SBM visibility profile applied",
                "This applies the mission-menu state from a confirmed SBM-visible save. "
                "It can change which normal missions appear. Save to a new slot and keep your original.",
            )
        elif self.sbm_original is not None:
            for offset, value in self.sbm_original.items():
                self.session.data[offset] = value
            self.sbm_original = None
        else:
            messagebox.showinfo(
                "Cannot reconstruct the previous profile",
                "Reopen the untouched original save instead. ESW will not guess the overwritten mission bytes.",
            )
            self.refresh()


class ViewerTab(ttk.Frame):
    def __init__(self, master, session: SaveSession) -> None:
        super().__init__(master, padding=12)
        self.session = session
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Label(bar, text="ADVANCED SAVE VIEWER", style="Heading.TLabel").pack(side="left")
        self.mode = tk.StringVar(value="Strings")
        ttk.Combobox(bar, textvariable=self.mode, state="readonly", values=("Strings", "Hex"), width=12).pack(side="right")
        ttk.Button(bar, text="REFRESH", command=self.refresh).pack(side="right", padx=8)
        self.text = tk.Text(self, wrap="none", font=("Consolas", 10), undo=False)
        self.text.pack(fill="both", expand=True, pady=(10, 0))
        self.session.subscribe(self.refresh)

    def refresh(self) -> None:
        self.text.delete("1.0", "end")
        data = self.session.data
        if data is None:
            self.text.insert("end", "Open a save to inspect its decoded payload.")
            return
        if self.mode.get() == "Hex":
            for offset in range(0, len(data), 16):
                block = data[offset:offset + 16]
                hexes = " ".join(f"{value:02X}" for value in block)
                chars = "".join(chr(value) if 32 <= value < 127 else "." for value in block)
                self.text.insert("end", f"{offset:08X}  {hexes:<47}  {chars}\n")
        else:
            start = None
            for index, value in enumerate(data + b"\0"):
                if 32 <= value < 127:
                    if start is None:
                        start = index
                elif start is not None:
                    if index - start >= 4:
                        value_text = bytes(data[start:index]).decode("ascii", errors="replace")
                        self.text.insert("end", f"{start:08X}  {value_text}\n")
                    start = None


class LoadoutTab(ttk.Frame):
    def __init__(self, master, session: SaveSession) -> None:
        super().__init__(master, padding=16)
        self.session = session
        self.mode = tk.StringVar(value="Active selected character — Campaign / Co-op")
        self.soldier_choice = tk.StringVar()
        self.soldier_choice_slots: dict[str, int | None] = {}
        self.items = [tk.StringVar() for _ in range(ITEM_SLOT_COUNT)]
        self.weapons = [tk.StringVar() for _ in range(WEAPON_SLOT_COUNT)]
        self.uniform = tk.StringVar()
        self.versus_role_uniform = tk.StringVar(value=LEAVE_ROLE_UNCHANGED)
        self.id_detail = tk.StringVar(
            value="Select an item or weapon to see how strongly its storage ID is verified."
        )
        ttk.Label(self, text="LOADOUT EDITOR", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(
            self,
            text=(
                "Campaign and Co-op share the active Mission Prep record. Seven item and seven weapon slots are editable. "
                "The seventh weapon requires the seven-slot runtime patch for in-game use. "
                "Cross-mode equipment is experimental: ESW will store it, but the game may still enforce a runtime mode filter."
            ),
            wraplength=950,
        ).pack(anchor="w", pady=(0, 12))
        modes = ttk.Frame(self)
        modes.pack(fill="x")
        for number, label in enumerate(LOADOUT_MODES):
            ttk.Radiobutton(modes, text=label, value=label, variable=self.mode, command=self.refresh).grid(row=number // 3, column=number % 3, sticky="w", padx=(0, 12), pady=2)
        soldier_line = ttk.Frame(self)
        soldier_line.pack(fill="x", pady=(8, 0))
        ttk.Label(soldier_line, text="Combat Unit soldier").pack(side="left")
        self.soldier_box = ttk.Combobox(
            soldier_line, textvariable=self.soldier_choice, state="readonly", width=44
        )
        self.soldier_box.pack(side="left", padx=10)
        self.soldier_box.bind("<<ComboboxSelected>>", self.soldier_changed)
        self.active_character_status = tk.StringVar(value="Active saved character: unknown")
        ttk.Label(self, textvariable=self.active_character_status).pack(anchor="w", pady=(8, 0))
        grid = ttk.LabelFrame(self, text="Preset", padding=12)
        grid.pack(fill="x", pady=12)
        ttk.Label(grid, text="Items").grid(row=0, column=0, sticky="w")
        ttk.Label(grid, text="Weapons").grid(row=0, column=1, sticky="w")
        self.item_boxes = []
        self.weapon_boxes = []
        for slot in range(max(ITEM_SLOT_COUNT, WEAPON_SLOT_COUNT)):
            if slot < ITEM_SLOT_COUNT:
                item = ttk.Combobox(grid, textvariable=self.items[slot], width=38)
                item.grid(row=slot + 1, column=0, padx=(0, 12), pady=5, sticky="ew")
                item.bind("<<ComboboxSelected>>", self.equipment_selected)
                self.item_boxes.append(item)
            if slot < WEAPON_SLOT_COUNT:
                weapon = ttk.Combobox(grid, textvariable=self.weapons[slot], width=38)
                weapon.grid(row=slot + 1, column=1, pady=5, sticky="ew")
                weapon.bind("<<ComboboxSelected>>", self.equipment_selected)
                self.weapon_boxes.append(weapon)
        grid.columnconfigure((0, 1), weight=1)
        ttk.Label(
            grid, textvariable=self.id_detail, wraplength=1050, foreground="#555555"
        ).grid(row=max(ITEM_SLOT_COUNT, WEAPON_SLOT_COUNT) + 1, column=0, columnspan=2,
               sticky="w", pady=(8, 0))
        uniform_line = ttk.Frame(self)
        uniform_line.pack(fill="x", pady=(0, 8))
        ttk.Label(uniform_line, text="Costume / uniform").pack(side="left")
        self.uniform_box = ttk.Combobox(
            uniform_line, textvariable=self.uniform, state="readonly", width=38,
            values=[f"{key:02X} — {name}" for key, name in UNIFORMS.items()],
        )
        self.uniform_box.pack(side="left", padx=10)
        role_line = ttk.Frame(self)
        role_line.pack(fill="x", pady=(0, 8))
        ttk.Label(role_line, text="Recruited-soldier role costume").pack(side="left")
        self.versus_role_box = ttk.Combobox(
            role_line,
            textvariable=self.versus_role_uniform,
            state="disabled",
            width=38,
            values=[LEAVE_ROLE_UNCHANGED] + [
                f"{key:02X} — {name}" for key, name in VERSUS_ROLE_UNIFORMS.items()
            ],
        )
        self.versus_role_box.pack(side="left", padx=10)
        self.mapping_status = tk.StringVar()
        actions = ttk.Frame(self)
        actions.pack(anchor="w")
        ttk.Button(actions, text="APPLY PRESET", command=self.apply).pack(side="left")
        ttk.Button(actions, text="EXPORT ID SNAPSHOT", command=self.export_snapshot).pack(side="left", padx=8)
        self.session.subscribe(self.refresh)

    def record_indexes(self) -> tuple[int, ...]:
        return LOADOUT_MODES[self.mode.get()]

    def active_character(self) -> str:
        if self.session.data is None:
            return "unknown"
        raw = bytes(self.session.data[ACTIVE_SOLDIER_NAME_OFFSET:ACTIVE_SOLDIER_NAME_OFFSET + NAME_SIZE])
        name = raw.split(b"\0", 1)[0].decode("ascii", errors="replace").strip() or "unknown"
        # Names are not unique.  The first 0x20 bytes of the active soldier
        # copy retain the identity signature of the source roster record.
        active_signature = bytes(
            self.session.data[ACTIVE_SOLDIER_RECORD_OFFSET:ACTIVE_SOLDIER_RECORD_OFFSET + 0x20]
        )
        for index in range(ROSTER_COUNT):
            record = ROSTER_BASE + index * ROSTER_RECORD_SIZE
            if bytes(self.session.data[record:record + 0x20]) == active_signature:
                return f"{name} — roster slot {index + 1}"
        # Unique characters are not always backed by the ordinary roster.
        # Name matching is retained only as a fallback and is marked as such.
        if name == "SNAKE":
            return "SNAKE — unique character"
        matches = []
        for index in range(ROSTER_COUNT):
            offset = ROSTER_BASE + index * ROSTER_RECORD_SIZE + NAME_OFFSET
            roster_raw = bytes(self.session.data[offset:offset + NAME_SIZE])
            roster_name = roster_raw.split(b"\0", 1)[0].decode("ascii", errors="replace").strip()
            if roster_name == name:
                matches.append(index + 1)
        if len(matches) == 1:
            return f"{name} — roster slot {matches[0]} (name match)"
        if matches:
            return f"{name} — duplicate name; roster slot unresolved"
        return name

    def active_roster_index(self) -> int | None:
        if self.session.data is None:
            return None
        active_signature = bytes(
            self.session.data[ACTIVE_SOLDIER_RECORD_OFFSET:ACTIVE_SOLDIER_RECORD_OFFSET + 0x20]
        )
        for index in range(ROSTER_COUNT):
            record = ROSTER_BASE + index * ROSTER_RECORD_SIZE
            if bytes(self.session.data[record:record + 0x20]) == active_signature:
                return index
        return None

    def populate_soldier_selector(self) -> None:
        if self.session.data is None:
            return
        current_text = self.soldier_choice.get()
        active_index = self.active_roster_index()
        choices: list[str] = []
        mapping: dict[str, int | None] = {}

        if active_index is None:
            current = f"CURRENT — {self.active_character()}"
            choices.append(current)
            mapping[current] = None

        for index in range(ROSTER_COUNT):
            record = ROSTER_BASE + index * ROSTER_RECORD_SIZE
            if self.session.data[record + ASSIGNMENT_OFFSET] != COMBAT_UNIT_ASSIGNMENT:
                continue
            raw = bytes(self.session.data[record + NAME_OFFSET:record + NAME_OFFSET + NAME_SIZE])
            name = raw.split(b"\0", 1)[0].decode("ascii", errors="replace").strip()
            if not name:
                name = "<unnamed>"
            label = f"{index + 1:03d} — {name}"
            choices.append(label)
            mapping[label] = index

        self.soldier_choice_slots = mapping
        self.soldier_box.configure(values=choices)
        active_label = next((label for label, index in mapping.items() if index == active_index), None)
        if current_text in mapping:
            self.soldier_choice.set(current_text)
        elif active_label is not None:
            self.soldier_choice.set(active_label)
        elif choices:
            self.soldier_choice.set(choices[0])
        else:
            self.soldier_choice.set("No Combat Unit soldiers found")

    def update_selected_soldier_status(self) -> None:
        if self.mode.get().startswith("Versus Ops"):
            self.active_character_status.set(
                f"Saved active character: {self.active_character()} — editing the selected Versus preset"
            )
            return
        selected = self.soldier_choice.get()
        index = self.soldier_choice_slots.get(selected)
        if index is None:
            self.active_character_status.set(f"Active saved character: {self.active_character()}")
        else:
            self.active_character_status.set(
                f"Selected for Campaign / Co-op: {selected} (applied when APPLY PRESET is pressed)"
            )

    def soldier_changed(self, _event=None) -> None:
        self.update_selected_soldier_status()

    @staticmethod
    def base(index: int) -> int:
        return PRESET_BASE + index * PRESET_STRIDE

    @staticmethod
    def parse(text: str, catalog: dict[int, str]) -> int:
        for value, name in catalog.items():
            if text == f"{value:04X} — {name}":
                return value
        return int(text.split("—", 1)[0].strip(), 16)

    @staticmethod
    def confidence_text(info: dict) -> str:
        confidence = str(info.get("confidence", "unmapped")).replace("-", " ").title()
        safety = "Selectable" if info.get("selectable", True) else "Unsafe/unresolved"
        evidence = info.get("evidence") or []
        suffix = f" Evidence: {'; '.join(str(value) for value in evidence)}" if evidence else ""
        return f"{confidence} · {safety}.{suffix}"

    def equipment_selected(self, event) -> None:
        widget = event.widget
        text = widget.get()
        try:
            value = int(text.split("—", 1)[0].strip(), 16)
        except (ValueError, IndexError):
            self.id_detail.set("Enter a four-digit hexadecimal storage ID.")
            return
        if widget in self.item_boxes:
            kind, catalog, info_catalog = "Item", ITEMS, ITEM_INFO
        else:
            kind, catalog, info_catalog = "Weapon", WEAPONS, WEAPON_INFO
        name = catalog.get(value, "Unmapped storage ID")
        info = info_catalog.get(value, {"confidence": "unmapped", "selectable": True})
        self.id_detail.set(
            f"{kind} storage ID {value:04X}: {name}. {self.confidence_text(info)} "
            "OLANG text is used only when a separate storage-ID link exists."
        )

    def refresh(self) -> None:
        if self.session.data is None:
            return
        self.versus_role_uniform.set(LEAVE_ROLE_UNCHANGED)
        self.populate_soldier_selector()
        self.update_selected_soldier_status()
        indexes = self.record_indexes()
        base = self.base(indexes[0])
        item_choices = [f"{key:04X} — {name}" for key, name in ITEMS.items()]
        weapon_choices = [f"{key:04X} — {name}" for key, name in WEAPONS.items()]
        for slot in range(ITEM_SLOT_COUNT):
            item_value = struct.unpack_from("<H", self.session.data, base + ITEM_OFFSET + slot * 2)[0]
            self.item_boxes[slot]["values"] = item_choices
            self.items[slot].set(f"{item_value:04X} — {ITEMS.get(item_value, 'Unmapped')}")
        for slot in range(WEAPON_SLOT_COUNT):
            weapon_value = struct.unpack_from("<H", self.session.data, base + WEAPON_OFFSET + slot * 2)[0]
            self.weapon_boxes[slot]["values"] = weapon_choices
            self.weapons[slot].set(f"{weapon_value:04X} — {WEAPONS.get(weapon_value, 'Unmapped storage ID')}")
        uniform_value = self.session.data[UNIFORM_OFFSETS[0]]
        self.uniform.set(f"{uniform_value:02X} — {UNIFORMS.get(uniform_value, 'Unmapped')}")
        if self.mode.get().startswith("Versus Ops"):
            self.soldier_box.configure(state="disabled")
            self.uniform_box.configure(state="disabled" if self.mode.get().endswith("MSF soldier") else "readonly")
            self.versus_role_box.configure(state="readonly")
            self.mapping_status.set(
                "MSF Versus preset at 0xB8A2: confirmed against RAVEN's saved M16A1(STG), C4 and Claymore loadout. "
                "This is a preset record, not a verified per-soldier table. The roster selector does not change it."
                if self.mode.get().endswith("MSF soldier") else
                "Earlier verified Versus Ops record at 0xB800. Snake uniform and "
                "recruited-soldier role are separate fields. The full item list is available for experimental cross-mode use."
            )
        elif self.mode.get().startswith("Active selected character"):
            self.soldier_box.configure(state="readonly")
            self.uniform_box.configure(state="readonly")
            self.versus_role_box.configure(state="readonly")
            self.mapping_status.set(
                "Controlled-save verified active Mission Prep record at 0xB61A. "
                "Seven item and seven weapon fields are editable here; extended in-game capacity requires the runtime patch. APPLY PRESET copies the selected "
                "soldier and the displayed STW preset into the game's active Mission Prep record."
            )
        else:
            self.soldier_box.configure(state="disabled")
            self.uniform_box.configure(state="disabled")
            self.versus_role_box.configure(state="disabled")
            self.mapping_status.set(
                "Experimental neighboring Mission Prep record. It is edited independently."
            )

    def apply(self) -> None:
        if self.session.data is None:
            messagebox.showinfo("No save open", "Open a save first.")
            return
        try:
            item_values = [self.parse(value.get(), ITEMS) for value in self.items]
            weapon_values = [self.parse(value.get(), WEAPONS) for value in self.weapons]
            unsafe = []
            for value in item_values:
                if not ITEM_INFO.get(value, {}).get("selectable", True):
                    unsafe.append(f"item {value:04X}")
            for value in weapon_values:
                if not WEAPON_INFO.get(value, {}).get("selectable", True):
                    unsafe.append(f"weapon {value:04X}")
            if unsafe and not messagebox.askyesno(
                "Unsafe or unresolved IDs",
                "This preset contains entries the game has not accepted as ordinary equipment:\n\n"
                + ", ".join(unsafe)
                + "\n\nKeep these exact raw IDs and continue?",
            ):
                return
            if self.mode.get().startswith("Active selected character"):
                selected = self.soldier_choice.get()
                roster_index = self.soldier_choice_slots.get(selected)
                if roster_index is not None:
                    source = ROSTER_BASE + roster_index * ROSTER_RECORD_SIZE
                    self.session.data[
                        ACTIVE_SOLDIER_RECORD_OFFSET:ACTIVE_SOLDIER_RECORD_OFFSET + ROSTER_RECORD_SIZE
                    ] = self.session.data[source:source + ROSTER_RECORD_SIZE]
            for index in self.record_indexes():
                base = self.base(index)
                for slot in range(ITEM_SLOT_COUNT):
                    struct.pack_into("<H", self.session.data, base + ITEM_OFFSET + slot * 2, item_values[slot])
                for slot in range(WEAPON_SLOT_COUNT):
                    struct.pack_into("<H", self.session.data, base + WEAPON_OFFSET + slot * 2, weapon_values[slot])
            if self.mode.get().startswith(("Versus Ops", "Active selected character")):
                uniform_value = int(self.uniform.get().split("—", 1)[0].strip(), 16)
                if uniform_value not in UNIFORMS:
                    raise ValueError(f"Unknown Versus uniform ID {uniform_value:02X}")
                # These three bytes are not mirrors. Controlled captures show
                # B5E4 = Campaign/Co-op uniform, B5E8 = recruited-soldier
                # Versus role, and B7D2 = Versus uniform. Writing one uniform
                # into all three can crash when Mission Prep is unloaded.
                uniform_offset = (
                    UNIFORM_OFFSETS[2]
                    if self.mode.get().startswith("Versus Ops")
                    else UNIFORM_OFFSETS[0]
                )
                if not self.mode.get().endswith("MSF soldier"):
                    self.session.data[uniform_offset] = uniform_value
                role_text = self.versus_role_uniform.get()
                if role_text != LEAVE_ROLE_UNCHANGED:
                    role_value = int(role_text.split("—", 1)[0].strip(), 16)
                    if role_value not in VERSUS_ROLE_UNIFORMS:
                        raise ValueError(f"Unknown recruited-soldier role ID {role_value:02X}")
                    # Do not synchronize this across the Snake bytes: the
                    # controlled ESCORT capture was 03,55,03.
                    self.session.data[VERSUS_ROLE_UNIFORM_OFFSET] = role_value
        except ValueError as exc:
            messagebox.showerror("Invalid equipment ID", str(exc))
            return
        self.refresh()
        messagebox.showinfo(
            "Preset applied",
            f"The {self.mode.get()} preset was applied in memory. "
            "Use Save As to write it.",
        )

    def export_snapshot(self) -> None:
        if self.session.data is None:
            messagebox.showinfo("No save open", "Open a save first.")
            return
        base = self.base(self.record_indexes()[0])
        snapshot = {
            "source_save": self.session.source.name if self.session.source else None,
            "mode": self.mode.get(),
            "active_character": self.active_character(),
            "record_base": f"0x{base:06X}",
            "items": [
                {
                    "slot": slot + 1,
                    "storage_id": f"{struct.unpack_from('<H', self.session.data, base + ITEM_OFFSET + slot * 2)[0]:04X}",
                    "current_label": self.items[slot].get().split("—", 1)[-1].strip(),
                    "confidence": ITEM_INFO.get(
                        struct.unpack_from('<H', self.session.data, base + ITEM_OFFSET + slot * 2)[0], {}
                    ).get("confidence", "unmapped"),
                }
                for slot in range(ITEM_SLOT_COUNT)
            ],
            "weapons": [
                {
                    "slot": slot + 1,
                    "storage_id": f"{struct.unpack_from('<H', self.session.data, base + WEAPON_OFFSET + slot * 2)[0]:04X}",
                    "current_label": self.weapons[slot].get().split("—", 1)[-1].strip(),
                    "confidence": WEAPON_INFO.get(
                        struct.unpack_from('<H', self.session.data, base + WEAPON_OFFSET + slot * 2)[0], {}
                    ).get("confidence", "unmapped"),
                }
                for slot in range(WEAPON_SLOT_COUNT)
            ],
        }
        chosen = filedialog.asksaveasfilename(
            title="Export loadout storage-ID snapshot",
            defaultextension=".json",
            filetypes=[("JSON mapping snapshot", "*.json")],
            initialfile="loadout_id_snapshot.json",
        )
        if not chosen:
            return
        Path(chosen).write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        messagebox.showinfo("Snapshot exported", "The current raw storage IDs were exported for mapping.")


class ESW(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Espirit's Save Workshop — Experimental")
        self.geometry("1280x820")
        self.minsize(980, 650)
        self.session = SaveSession()
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Heading.TLabel", font=("Segoe UI", 18, "bold"))
        self.status = tk.StringVar(value="Open an encrypted Peace Walker PC save to begin.")
        self.build_menu()
        tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True)
        self.soldier_editor = SoldierEditor(tabs, embedded=True, open_callback=self.open_save)
        tabs.add(self.soldier_editor, text="Soldier Editor")
        tabs.add(InternalMissionTab(tabs, self.session), text="Save Editor")
        self.loadout_tab = LoadoutTab(tabs, self.session)
        tabs.add(self.loadout_tab, text="Loadout Editor")
        ttk.Label(self, textvariable=self.status, anchor="w", padding=6).pack(fill="x")

    def build_menu(self) -> None:
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Open Save…", command=self.open_save)
        file_menu.add_command(label="Save As…", command=self.save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menu.add_cascade(label="File", menu=file_menu)
        self.config(menu=menu)

    def open_save(self) -> None:
        chosen = filedialog.askopenfilename(title="Open Peace Walker PC STW save")
        if not chosen:
            return
        try:
            path = Path(chosen)
            self.soldier_editor.load_save_path(path)
            # Every ESW tab edits the same decoded bytearray as the full
            # embedded Soldier Editor.
            self.session.data = self.soldier_editor.data
            self.session.source = path
            self.session.header_index = self.soldier_editor.header_index
            self.session.notify()
        except Exception as exc:
            messagebox.showerror("Cannot open save", str(exc))
            return
        self.status.set(f"Opened and decoded {path.name} across all ESW tabs")

    def save_as(self) -> None:
        # The full editor applies pending edits, restores remembered quote IDs,
        # and writes the destination's quote companion together with the STW.
        self.soldier_editor.save_as()
        self.session.data = self.soldier_editor.data
        self.session.source = self.soldier_editor.source_path
        self.session.header_index = self.soldier_editor.header_index
        self.session.notify()
        self.status.set(self.soldier_editor.status_var.get())


if __name__ == "__main__":
    ESW().mainloop()
