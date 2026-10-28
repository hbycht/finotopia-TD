# finotopia – 3D-Preview

This folder holds a separate version of finotopia, made for exhibitions. It adds a **digital twin** of the upper floor of the club «fi»: a real-time 3D simulation of the room and its lights. The twin receives the same control data as the real rig, so finotopia can be shown without any DMX hardware. It was first used for the exhibition of the Kölner Design Preis 2026 at MAKK.

The main version in the repository root is unchanged.

## Opening

Open `3D-Preview/finotopia.toe` in TouchDesigner. The project expects the folders `twin/`, `code/` and `tox/` next to the `.toe` file, so keep the folder structure as it is.

The 3D view is in `/project1/VISUAL_PREVIEW/twin`, and its output is `twin/null_out`. In `VISUAL_PREVIEW`, `switch1` selects between the 2D preview (index 0) and the 3D preview (index 1).

## The digital twin

- **Room**: a low-poly model of the floor (trapezoid, ceiling sloping towards the bar), night mode only. It is generated from `twin/room.json` by `twin/tools/build_room.py`.
- **Fixtures**: all fixtures are listed in `twin/fixtures.json`:
  - 8 moving heads (Cameo MovoBeam 100, 35-channel mode)
  - 6 blinders with inner and outer LED rings
  - the hexagon panel
  - 2 pentagons under the ceiling
  - 4 bulbs
  - fog
- **Rendering**: moving-head beams are additive GLSL cones. Pixels are emissive instances. The room is lit by all moving heads, bulbs and pixel fixtures through a single GLSL material, with no Light COMPs, so there is no 8-light limit.
- **Code**: the logic lives in `twin/code/` as text files that are synced to text DATs in the project. The main module is `twin_lib.py`.

### Parameters on `/project1/VISUAL_PREVIEW/twin`

| Parameter | Effect |
| --- | --- |
| Exhibition | Exhibition mode, see below |
| Testmode | Synthetic test data, no running show needed |
| Beamgain / Hazebase / Lightgain / Pixelgain | Brightness of beams, haze, room light and pixels |
| Rebuild | Re-reads `fixtures.json` and rebuilds the static tables |

### Exhibition mode

With **Exhibition** on:

- The `node*` fixture COMPs and the DMX output stop cooking.
- The twin samples the same map textures directly on the GPU (`/project1/twin_probe_pix`, `/project1/twin_probe_ctrl`).
- Frame time drops from about 137 ms to about 38 ms (M1 Max).

The 2D preview (`preview_2D`) does not update in this mode, because it is drawn from the fixture outputs. Switch the mode off to drive a real rig.

Fixture point layouts are cached in `twin/fixture_points.json`, so the twin also works right after loading a project that was saved in exhibition mode.

### Performance options

`/project1/PERF` has three switches:

- **Groupglsl**: replaces the ColorPicker → dimmer → correction chain of each fixture group with one GLSL TOP.
- **Viscooking**: cooks only the visual content that is in use.
- **Smallfixes**: a set of minor optimisations.

All three can be switched back to the original networks.

## Moving-head positions

The position presets in `MH_Move_Controller/pos_*` were recalculated for the twin, with the old values used as the starting point.

- **Down**: all heads point straight down.
- **Center**: all 8 beams meet in one point on the floor.
- **V**: each pair of opposite heads meets on the floor on its own row.
- **Wall**: the beams land centred on the blinders, and MOVO31/32 cross above the panel.
- **Bar**: the beams are symmetric.
- **Twin_Spot** and **Sides**: MOVO31/32 are adjusted to match the other heads.

Compared with the main version, this version also differs in three places:

- The position map in `MH_Move_Controller` now runs in 32-bit float instead of 8 bit. One 8-bit step was about 2° of pan.
- `dimmer_Bulbs` follows the master fader (`Masterdimfunc` on).
- The wall-mounted MOVO32 is modelled rotated by 180° about its own axis compared to MOVO31. Its pan values follow `pan32 = 2/3 − pan31` at the same tilt.

These presets come from a model and have not been checked on the real rig.

Tools, run with plain Python 3 and numpy:

- `twin/tools/solve_presets.py` recalculates the presets from target points in the room. `--write` writes `twin/ref/presets_new.json`, which then has to be copied into the `pos_*` CHOPs.
- `twin/tools/preset_hits.py` prints where every beam lands for every preset.
- `twin/ref/presets_backup_2026-10-28.json` holds the original preset values.
- `twin/ref/mh_calibration.json` holds the DMX values that the mounting model was fitted to.
