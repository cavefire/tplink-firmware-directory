#!/usr/bin/env python3

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def check_if_archived(url):
    try:
        check_url = f"https://archive.org/wayback/available?url={urllib.parse.quote(url)}"
        req = urllib.request.Request(check_url, headers={'User-Agent': 'TP-Link Archive Bot'})
        
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            if data.get('archived_snapshots', {}).get('closest', {}).get('available'):
                return data['archived_snapshots']['closest'].get('url', '')
    except Exception as e:
        print(f"  Check failed: {e}", flush=True)
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--check-only', action='store_true', help='Only check for existing archives, do not create new ones')
    args = parser.parse_args()
    
    mode = "check-only mode" if args.check_only else "archive mode"
    print(f"Starting archive script in {mode}...", flush=True)
    
    csv_path = Path(__file__).parent / "all_keys.csv"
    stats_path = Path(__file__).parent / "archive_stats.txt"
    
    archived = 0
    skipped = 0
    found_existing = 0
    
    with open(stats_path, 'w') as f:
        f.write(f"new_archives=0\n")
        f.write(f"already_archived=0\n")
        f.write(f"failed=0\n")
    
    if not csv_path.exists():
        print(f"Error: {csv_path} not found", flush=True)
        return 1
    
    print(f"Loading CSV from {csv_path}...", flush=True)
    records = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    
    print(f"Loaded {len(records)} records", flush=True)
    start_time = time.time()
    
    for i, row in enumerate(records):
        if time.time() - start_time > args.timeout:
            print(f"\nTimeout reached after {i} records", flush=True)
            break
        
        if row.get('wayback_url'):
            skipped += 1
            continue
        
        if row.get('removed'):
            continue
        
        url = f"http://download.tplinkcloud.com/{row['fullpath']}"
        print(f"[{i+1}/{len(records)}] Processing: {row['fullpath']}", flush=True)
        
        print(f"  Checking if already archived...", flush=True)
        existing = check_if_archived(url)
        if existing:
            print(f"  ✓ Found existing: {existing}", flush=True)
            row['wayback_url'] = existing
            found_existing += 1
            
            with open(csv_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['creation', 'size', 'fullpath', 'added', 'removed', 'wayback_url'])
                writer.writeheader()
                writer.writerows(records)
            
            with open(stats_path, 'w') as f:
                f.write(f"new_archives={archived}\n")
                f.write(f"already_archived={skipped + found_existing}\n")
                f.write(f"failed=0\n")
            
            time.sleep(1)
            continue
        
        if args.check_only:
            print(f"  - Not archived (check-only mode, skipping)", flush=True)
            time.sleep(1)
            continue
        
        print(f"  Archiving to Wayback Machine...", flush=True)
        success = False
        for attempt in range(5):
            try:
                save_url = f"https://web.archive.org/save/{url}"
                req = urllib.request.Request(save_url, headers={'User-Agent': 'TP-Link Archive Bot'})
                
                with urllib.request.urlopen(req, timeout=120) as response:
                    content_location = response.headers.get('Content-Location')
                    if content_location:
                        row['wayback_url'] = f"https://web.archive.org{content_location}"
                    else:
                        row['wayback_url'] = response.geturl()
                    
                    print(f"  ✓ Archived: {row['wayback_url']}", flush=True)
                    archived += 1
                    success = True
                    
                    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=['creation', 'size', 'fullpath', 'added', 'removed', 'wayback_url'])
                        writer.writeheader()
                        writer.writerows(records)
                    
                    with open(stats_path, 'w') as f:
                        f.write(f"new_archives={archived}\n")
                        f.write(f"already_archived={skipped + found_existing}\n")
                        f.write(f"failed=0\n")
                    break
            
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait_time = 180
                    print(f"  Rate limited (429), waiting {wait_time}s...", flush=True)
                    time.sleep(wait_time)
                    continue
                elif e.code == 520:
                    if attempt < 4:
                        wait_time = 30 * (attempt + 1)
                        print(f"  Server error (520), retry {attempt+1}/5 after {wait_time}s...", flush=True)
                        time.sleep(wait_time)
                        continue
                print(f"  ✗ HTTP {e.code}", flush=True)
                break
            
            except Exception as e:
                if attempt < 4:
                    wait_time = 15 * (attempt + 1)
                    print(f"  Retry {attempt+1}/5 after {wait_time}s: {e}", flush=True)
                    time.sleep(wait_time)
                else:
                    print(f"  ✗ Failed after 5 attempts: {e}", flush=True)
        
        if success:
            time.sleep(8)
        else:
            time.sleep(3)
    
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['creation', 'size', 'fullpath', 'added', 'removed', 'wayback_url'])
        writer.writeheader()
        writer.writerows(records)
    
    with open(stats_path, 'w') as f:
        f.write(f"new_archives={archived}\n")
        f.write(f"already_archived={skipped + found_existing}\n")
        f.write(f"failed=0\n")
    
    print(f"\nDone: {archived} newly archived, {found_existing} found existing, {skipped} already in CSV", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
