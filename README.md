# GPX Splitter by Duration

Splits a GPX file into multiple parts based on estimated driving duration. Useful when a navigation app has a time limit per route segment.

---

## Option A — Run the Python script directly

**Requirements:** Python 3.8+

1. Clone or download this repository.
2. Place your `.gpx` file(s) inside an `in/` folder next to the script:
   ```
   gpx_split/
   ├── split_by_duration_portable.py
   ├── in/
   │   └── my_route.gpx
   ```
3. Run the script:
   ```bash
   python split_by_duration_portable.py
   ```
4. Answer the two prompts:
   - **Max driving duration per part (hours)** — default `2.0`
   - **Average driving speed (km/h)** — default `20.0`
5. Split files are saved to `out_by_duration/` next to the script.

---

## Option B — Build a standalone executable (Windows)

No Python needed on the target machine after this step.

**Requirements:** Python 3.8+, PyInstaller

```bash
pip install pyinstaller
pyinstaller split_by_duration.spec
```

The executable is created at `dist/split_by_duration.exe`.

To use it:
1. Copy `split_by_duration.exe` to any folder.
2. Create an `in/` subfolder in the same location and put your `.gpx` files there.
3. Double-click the `.exe` — it will prompt for duration and speed, then write the split files to `out_by_duration/`.

---

## How it works

The script reads all `.gpx` files from the `in/` folder. For each file it:

1. Calculates the distance between consecutive waypoints using the Haversine formula.
2. Estimates travel time for each segment using your average speed.
3. Cuts a new part whenever the accumulated time would exceed the limit.
4. Writes each part as a separate `.gpx` file (`my_route_part1.gpx`, `my_route_part2.gpx`, …).

Supports both **route** (`<rte>`) and **waypoint** (`<wpt>`) GPX formats.

---

## Example output

```
Processing: my_route.gpx  (87 waypoints)
  -> Part 1: 34 waypoints, ~1.97 hrs, ~39.4 km  =>  my_route_part1.gpx
  -> Part 2: 31 waypoints, ~1.98 hrs, ~39.6 km  =>  my_route_part2.gpx
  -> Part 3: 22 waypoints, ~1.12 hrs, ~22.4 km  =>  my_route_part3.gpx
```
