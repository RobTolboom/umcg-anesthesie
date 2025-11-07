#!/usr/bin/env python3
"""
BibTeX Duplicate Cleanup Script

This script removes duplicate entries from a BibTeX file based on PMID.
When duplicates are found, it keeps only the first occurrence.

Usage:
    python cleanup_duplicates.py [bib_file] [--dry-run]

Options:
    --dry-run : Show what would be removed without modifying the file
"""

import os
import sys
import re
import argparse
from typing import Set, List, Dict


def parse_bibtex_entries(content: str) -> List[Dict]:
    """
    Parse BibTeX file content into a list of entries.

    Returns:
        List of dictionaries with 'text', 'pmid', 'key', 'start', 'end'
    """
    entries = []

    # Split by entry start pattern and process each chunk
    # This handles nested braces in abstracts better
    # Require @ at start of line or after whitespace to avoid matching @ in abstracts
    entry_starts = [(m.start(), m.group(0)) for m in re.finditer(r'(?:^|\n)@\w+\s*{', content, re.MULTILINE)]

    for i, (start_pos, start_match) in enumerate(entry_starts):
        # Adjust start_pos if match includes leading newline
        if content[start_pos] == '\n':
            start_pos += 1

        # Determine end of this entry (start of next entry or end of file)
        if i + 1 < len(entry_starts):
            end_pos = entry_starts[i + 1][0]
            # Adjust if next match includes leading newline
            if end_pos > 0 and content[end_pos] == '\n':
                end_pos += 1
        else:
            end_pos = len(content)

        # Extract entry text
        entry_text = content[start_pos:end_pos].rstrip()

        # Extract PMID
        pmid = None
        pmid_match = re.search(r'pmid\s*=\s*[{\"]?(\d+)[}\"]?', entry_text, re.IGNORECASE)
        if pmid_match:
            pmid = pmid_match.group(1)

        # Extract BibTeX key
        bib_key = None
        key_match = re.search(r'@(\w+)\s*{\s*([^,\s]+)\s*,', entry_text)
        if key_match:
            bib_key = key_match.group(2)

        entries.append({
            'text': entry_text,
            'pmid': pmid,
            'key': bib_key,
            'start': start_pos,
            'end': end_pos
        })

    return entries


def find_duplicates(entries: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Find duplicate entries based on PMID.

    Returns:
        Dictionary mapping PMID to list of duplicate entries
    """
    pmid_to_entries = {}

    for entry in entries:
        if entry['pmid']:
            pmid = entry['pmid']
            if pmid not in pmid_to_entries:
                pmid_to_entries[pmid] = []
            pmid_to_entries[pmid].append(entry)

    # Keep only PMIDs with duplicates
    duplicates = {pmid: entries for pmid, entries in pmid_to_entries.items() if len(entries) > 1}

    return duplicates


def remove_duplicates(bib_file: str, dry_run: bool = False) -> None:
    """
    Remove duplicate entries from BibTeX file.

    Args:
        bib_file: Path to BibTeX file
        dry_run: If True, only show what would be removed
    """
    if not os.path.exists(bib_file):
        print(f"Error: File not found: {bib_file}", file=sys.stderr)
        sys.exit(1)

    # Read file
    print(f"Reading {bib_file}...")
    with open(bib_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parse entries
    print("Parsing BibTeX entries...")
    entries = parse_bibtex_entries(content)
    print(f"  Found {len(entries)} total entries")

    # Find duplicates
    print("\nAnalyzing for duplicates...")
    duplicates = find_duplicates(entries)

    if not duplicates:
        print("✓ No duplicates found!")
        return

    # Report duplicates
    total_duplicates = sum(len(dup_entries) - 1 for dup_entries in duplicates.values())
    print(f"  Found {len(duplicates)} PMIDs with duplicates")
    print(f"  Total duplicate entries to remove: {total_duplicates}")
    print()

    # Show details
    print("Duplicate details:")
    print("-" * 80)
    for pmid, dup_entries in sorted(duplicates.items()):
        print(f"\nPMID {pmid}: {len(dup_entries)} entries")
        for i, entry in enumerate(dup_entries):
            status = "KEEP" if i == 0 else "REMOVE"
            print(f"  [{status}] {entry['key']}")
    print("-" * 80)
    print()

    if dry_run:
        print("DRY RUN: No changes made to file")
        return

    # Remove duplicates - keep only first occurrence of each PMID
    seen_pmids = set()
    kept_entries = []
    removed_count = 0

    for entry in entries:
        pmid = entry['pmid']

        if pmid is None:
            # Keep entries without PMID
            kept_entries.append(entry['text'])
        elif pmid not in seen_pmids:
            # First occurrence - keep it
            seen_pmids.add(pmid)
            kept_entries.append(entry['text'])
        else:
            # Duplicate - remove it
            removed_count += 1

    # Write cleaned file
    print(f"Writing cleaned file...")
    with open(bib_file, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(kept_entries))
        f.write('\n')

    print(f"✓ Successfully removed {removed_count} duplicate entries")
    print(f"✓ Kept {len(kept_entries)} unique entries")


def main():
    parser = argparse.ArgumentParser(
        description='Remove duplicate entries from BibTeX file based on PMID',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('bib_file', nargs='?',
                        default='../content/umcg-anes.bib',
                        help='Path to BibTeX file (default: ../content/umcg-anes.bib)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be removed without modifying the file')

    args = parser.parse_args()

    # Resolve path relative to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bib_file = os.path.join(script_dir, args.bib_file)
    bib_file = os.path.normpath(bib_file)

    print("BibTeX Duplicate Cleanup Script")
    print("=" * 80)
    print()

    remove_duplicates(bib_file, args.dry_run)

    return 0


if __name__ == '__main__':
    sys.exit(main())
