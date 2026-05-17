#!/usr/bin/env python3
import xml.etree.ElementTree as ET
from pathlib import Path
from math import radians, cos, sin, asin, sqrt
import sys
import os

# Register namespaces
namespaces = {
    'default': 'http://www.topografix.com/GPX/1/1',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    'gpxx': 'http://www.garmin.com/xmlschemas/GpxExtensions/v3',
    'trp': 'http://www.garmin.com/xmlschemas/TripExtensions/v1'
}

for prefix, uri in namespaces.items():
    ET.register_namespace(prefix if prefix != 'default' else '', uri)


def get_base_dir():
    """Return the directory where the exe (or script) lives."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return c * 6371


def ask(prompt, default, cast):
    """Ask the user for input with a default value."""
    while True:
        raw = input(f"{prompt} [default: {default}]: ").strip()
        if raw == "":
            return default
        try:
            return cast(raw)
        except ValueError:
            print(f"  Invalid input, please enter a number.")


def split_gpx_by_duration(input_file, output_dir, max_duration_hours, avg_speed_kmh):
    tree = ET.parse(input_file)
    root = tree.getroot()
    base_name = input_file.stem

    rte = root.find('.//{{{}}}rte'.format(namespaces['default']))
    if rte is not None:
        waypoints = rte.findall('{http://www.topografix.com/GPX/1/1}rtept')
        is_route = True
    else:
        waypoints = root.findall('{http://www.topografix.com/GPX/1/1}wpt')
        is_route = False

    if not waypoints:
        print(f"  [!] No waypoints found in {input_file.name}, skipping.")
        return

    max_duration_seconds = max_duration_hours * 3600

    print(f"\nProcessing: {input_file.name}  ({len(waypoints)} waypoints)")

    chunks = []
    current_chunk = [waypoints[0]]
    current_duration = 0
    total_distance = 0

    for i in range(len(waypoints) - 1):
        lat1 = float(waypoints[i].get('lat'))
        lon1 = float(waypoints[i].get('lon'))
        lat2 = float(waypoints[i + 1].get('lat'))
        lon2 = float(waypoints[i + 1].get('lon'))

        distance_km = haversine(lon1, lat1, lon2, lat2)
        time_seconds = (distance_km / avg_speed_kmh) * 3600

        if current_duration + time_seconds > max_duration_seconds and len(current_chunk) > 1:
            chunks.append((current_chunk, current_duration / 3600, total_distance))
            current_chunk = [waypoints[i]]
            current_duration = 0
            total_distance = 0

        current_chunk.append(waypoints[i + 1])
        current_duration += time_seconds
        total_distance += distance_km

    if current_chunk:
        chunks.append((current_chunk, current_duration / 3600, total_distance))

    for chunk_idx, (chunk, duration_hours, distance_km) in enumerate(chunks, 1):
        new_root = ET.Element(root.tag)
        for key, value in root.attrib.items():
            new_root.set(key, value)

        metadata = root.find('{http://www.topografix.com/GPX/1/1}metadata')
        if metadata is not None:
            new_root.append(ET.fromstring(ET.tostring(metadata)))

        if is_route:
            new_rte = ET.SubElement(new_root, '{http://www.topografix.com/GPX/1/1}rte')
            rte_name = rte.find('{http://www.topografix.com/GPX/1/1}name')
            if rte_name is not None:
                new_rte_name = ET.SubElement(new_rte, '{http://www.topografix.com/GPX/1/1}name')
                new_rte_name.text = f"{rte_name.text}_part{chunk_idx}"
            rte_extensions = rte.find('{http://www.topografix.com/GPX/1/1}extensions')
            if rte_extensions is not None:
                new_rte.append(ET.fromstring(ET.tostring(rte_extensions)))
            for waypoint in chunk:
                new_rte.append(ET.fromstring(ET.tostring(waypoint)))
        else:
            for waypoint in chunk:
                new_root.append(ET.fromstring(ET.tostring(waypoint)))

        output_file = output_dir / f"{base_name}_part{chunk_idx}.gpx"
        ET.ElementTree(new_root).write(output_file, encoding='utf-8', xml_declaration=True)

        print(f"  -> Part {chunk_idx}: {len(chunk)} waypoints, "
              f"~{duration_hours:.2f} hrs, ~{distance_km:.1f} km  =>  {output_file.name}")


def main():
    base_dir = get_base_dir()
    input_dir = base_dir / "in"
    output_dir = base_dir / "out_by_duration"

    print("=" * 55)
    print("       GPX Split by Duration")
    print("=" * 55)
    print(f"Looking for .gpx files in: {input_dir}")
    print()

    if not input_dir.exists():
        input_dir.mkdir(parents=True)
        print(f"Created '{input_dir}' folder — place your .gpx files there and re-run.")
        input("\nPress Enter to exit...")
        return

    gpx_files = sorted(input_dir.glob("*.gpx"))
    if not gpx_files:
        print(f"No .gpx files found in '{input_dir}'.")
        print("Place your .gpx files in that folder and re-run.")
        input("\nPress Enter to exit...")
        return

    print(f"Found {len(gpx_files)} file(s): {', '.join(f.name for f in gpx_files)}")
    print()

    duration = ask("Max driving duration per part (hours)", 2.0, float)
    speed    = ask("Average driving speed (km/h)         ", 20.0, float)

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput folder: {output_dir}")

    for gpx_file in gpx_files:
        split_gpx_by_duration(gpx_file, output_dir, duration, speed)

    print("\nDone! All files have been split.")
    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
