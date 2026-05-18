#!/usr/bin/env python3
"""
Folder monitor: watches INPUT_DIR every 60 seconds for .gpx files,
splits them (max 1 hour / 20 km/h), writes parts to OUTPUT_DIR,
then moves the original to IMPORTED_DIR.
Errors are logged and the loop continues.
"""

import xml.etree.ElementTree as ET
import shutil
import time
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from math import radians, cos, sin, asin, sqrt

# ── Configuration ─────────────────────────────────────────────────────────────
INPUT_DIR    = Path(r"Z:\P3FTPFilesNL\routes\\p3_NL_2026_q2_ALL")
OUTPUT_DIR   = Path(r"Z:\P3FTPFilesNL\routes_splitted")
IMPORTED_DIR = Path(r"Z:\P3FTPFilesNL\routes_Imported")

MAX_DURATION_HOURS = 2.0
AVG_SPEED_KMH      = 20.0
POLL_INTERVAL_SEC  = 60
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("monitor_split.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

NAMESPACES = {
    "default": "http://www.topografix.com/GPX/1/1",
    "xsi":     "http://www.w3.org/2001/XMLSchema-instance",
    "gpxx":    "http://www.garmin.com/xmlschemas/GpxExtensions/v3",
    "trp":     "http://www.garmin.com/xmlschemas/TripExtensions/v1",
}
for prefix, uri in NAMESPACES.items():
    ET.register_namespace("" if prefix == "default" else prefix, uri)

GPX_NS = "http://www.topografix.com/GPX/1/1"


def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * asin(sqrt(a)) * 6371


def parse_time(pt):
    """Return UTC timestamp in seconds from a trkpt/rtept/wpt element, or None."""
    t = pt.find(f"{{{GPX_NS}}}time")
    if t is None or not t.text:
        return None
    text = t.text.strip().rstrip("Z")
    try:
        return datetime.fromisoformat(text).replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


def split_gpx(input_file: Path, output_dir: Path,
              max_hours: float, speed_kmh: float) -> int:
    """Split one GPX file. Returns the number of parts written."""
    tree = ET.parse(input_file)
    root = tree.getroot()
    base = input_file.stem

    # Detect format: track, route, or bare waypoints
    trk = root.find(f".//{{{GPX_NS}}}trk")
    rte = root.find(f".//{{{GPX_NS}}}rte")

    if trk is not None:
        waypoints = trk.findall(f".//{{{GPX_NS}}}trkpt")
        mode = "trk"
        container = trk
    elif rte is not None:
        waypoints = rte.findall(f"{{{GPX_NS}}}rtept")
        mode = "rte"
        container = rte
    else:
        waypoints = root.findall(f"{{{GPX_NS}}}wpt")
        mode = "wpt"
        container = None

    if not waypoints:
        log.warning("  No waypoints in %s — skipping.", input_file.name)
        return 0

    max_seconds = max_hours * 3600
    chunks, current, cur_dur, cur_dist = [], [waypoints[0]], 0.0, 0.0

    for i in range(len(waypoints) - 1):
        lat1 = float(waypoints[i].get("lat"))
        lon1 = float(waypoints[i].get("lon"))
        lat2 = float(waypoints[i + 1].get("lat"))
        lon2 = float(waypoints[i + 1].get("lon"))

        dist_km = haversine(lon1, lat1, lon2, lat2)

        # Use real timestamps when available, fall back to speed estimate
        t1 = parse_time(waypoints[i])
        t2 = parse_time(waypoints[i + 1])
        if t1 is not None and t2 is not None and t2 > t1:
            seg_sec = t2 - t1
        else:
            seg_sec = (dist_km / speed_kmh) * 3600

        if cur_dur + seg_sec > max_seconds and len(current) > 1:
            chunks.append((current, cur_dur / 3600, cur_dist))
            current, cur_dur, cur_dist = [waypoints[i]], 0.0, 0.0

        current.append(waypoints[i + 1])
        cur_dur  += seg_sec
        cur_dist += dist_km

    if current:
        chunks.append((current, cur_dur / 3600, cur_dist))

    metadata = root.find(f"{{{GPX_NS}}}metadata")
    total = len(chunks)

    for idx, (chunk, dur_h, dist_km) in enumerate(chunks, 1):
        new_root = ET.Element(root.tag, root.attrib)

        if metadata is not None:
            new_root.append(ET.fromstring(ET.tostring(metadata)))

        part_label = f"part{idx}_of_{total}"

        if mode == "trk":
            new_trk = ET.SubElement(new_root, f"{{{GPX_NS}}}trk")
            trk_name = container.find(f"{{{GPX_NS}}}name")
            if trk_name is not None:
                el = ET.SubElement(new_trk, f"{{{GPX_NS}}}name")
                el.text = f"{trk_name.text}_{part_label}"
            trk_ext = container.find(f"{{{GPX_NS}}}extensions")
            if trk_ext is not None:
                new_trk.append(ET.fromstring(ET.tostring(trk_ext)))
            new_seg = ET.SubElement(new_trk, f"{{{GPX_NS}}}trkseg")
            for wp in chunk:
                new_seg.append(ET.fromstring(ET.tostring(wp)))
        elif mode == "rte":
            new_rte = ET.SubElement(new_root, f"{{{GPX_NS}}}rte")
            rte_name = container.find(f"{{{GPX_NS}}}name")
            if rte_name is not None:
                el = ET.SubElement(new_rte, f"{{{GPX_NS}}}name")
                el.text = f"{rte_name.text}_{part_label}"
            rte_ext = container.find(f"{{{GPX_NS}}}extensions")
            if rte_ext is not None:
                new_rte.append(ET.fromstring(ET.tostring(rte_ext)))
            for wp in chunk:
                new_rte.append(ET.fromstring(ET.tostring(wp)))
        else:
            for wp in chunk:
                new_root.append(ET.fromstring(ET.tostring(wp)))

        out = output_dir / f"{base}_{part_label}.gpx"
        ET.ElementTree(new_root).write(out, encoding="utf-8", xml_declaration=True)
        log.info("    part %d/%d: %d pts, ~%.2f hrs, ~%.1f km  ->  %s",
                 idx, total, len(chunk), dur_h, dist_km, out.name)

    return len(chunks)


def ensure_dirs():
    for d in (INPUT_DIR, OUTPUT_DIR, IMPORTED_DIR):
        d.mkdir(parents=True, exist_ok=True)


def process_file(gpx_file: Path):
    log.info("Processing: %s", gpx_file.name)
    parts = split_gpx(gpx_file, OUTPUT_DIR, MAX_DURATION_HOURS, AVG_SPEED_KMH)
    if parts == 0:
        log.warning("  Nothing written for %s; file NOT moved.", gpx_file.name)
        return
    dest = IMPORTED_DIR / gpx_file.name
    # avoid collision in imported folder
    if dest.exists():
        stem, suffix = gpx_file.stem, gpx_file.suffix
        i = 1
        while dest.exists():
            dest = IMPORTED_DIR / f"{stem}_{i}{suffix}"
            i += 1
    shutil.move(str(gpx_file), str(dest))
    log.info("  Moved original -> %s", dest)


def run_once():
    """Scan INPUT_DIR and process every .gpx found."""
    gpx_files = sorted(INPUT_DIR.glob("*.gpx"))
    if not gpx_files:
        log.info("No .gpx files found in %s", INPUT_DIR)
        return
    log.info("Found %d file(s) to process.", len(gpx_files))
    for gpx_file in gpx_files:
        try:
            process_file(gpx_file)
        except Exception:
            log.error("  Failed to process %s:\n%s", gpx_file.name, traceback.format_exc())


def main():
    log.info("=" * 60)
    log.info("  GPX Folder Monitor started")
    log.info("  Input   : %s", INPUT_DIR)
    log.info("  Output  : %s", OUTPUT_DIR)
    log.info("  Imported: %s", IMPORTED_DIR)
    log.info("  Settings: max %.1f h / %.0f km/h / poll every %ds",
             MAX_DURATION_HOURS, AVG_SPEED_KMH, POLL_INTERVAL_SEC)
    log.info("=" * 60)

    ensure_dirs()

    while True:
        try:
            run_once()
        except Exception:
            log.error("Unexpected error in run_once:\n%s", traceback.format_exc())

        log.info("Sleeping %d s until next check…", POLL_INTERVAL_SEC)
        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
