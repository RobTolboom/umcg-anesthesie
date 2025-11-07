#!/usr/bin/env python3
"""
Exclude PMID Script

This script excludes a publication (by PMID) from the bibliography.
It adds the PMID to excluded_pmids.json and removes the entry from umcg-anes.bib.

Usage:
    python exclude_pmid.py --pmid 12345678 --member rob-tolboom --reason "Wrong author match"
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime
from typing import Optional, Dict


def load_excluded_pmids(exclude_file: str) -> Dict:
    """Load the excluded PMIDs JSON file."""
    if not os.path.exists(exclude_file):
        return {}

    try:
        with open(exclude_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {exclude_file}: {e}", file=sys.stderr)
        return {}


def save_excluded_pmids(exclude_file: str, data: Dict):
    """Save the excluded PMIDs JSON file."""
    try:
        with open(exclude_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✓ Updated {exclude_file}")
    except Exception as e:
        print(f"Error saving {exclude_file}: {e}", file=sys.stderr)
        sys.exit(1)


def validate_member(member_slug: str, members_dir: str) -> bool:
    """Validate that the member exists."""
    member_file = os.path.join(members_dir, f"{member_slug}.md")
    if not os.path.exists(member_file):
        print(f"Error: Member '{member_slug}' not found.", file=sys.stderr)
        print(f"Expected file: {member_file}", file=sys.stderr)
        print(f"\nAvailable members:", file=sys.stderr)

        # List available members
        if os.path.exists(members_dir):
            members = [f.replace('.md', '') for f in os.listdir(members_dir)
                      if f.endswith('.md') and not f.startswith('.')]
            for m in sorted(members)[:10]:
                print(f"  - {m}", file=sys.stderr)
            if len(members) > 10:
                print(f"  ... and {len(members) - 10} more", file=sys.stderr)

        return False
    return True


def find_and_remove_bib_entry(bib_file: str, pmid: str) -> Optional[str]:
    """Find and remove BibTeX entry with given PMID from the file."""
    if not os.path.exists(bib_file):
        print(f"Warning: Bibliography file not found: {bib_file}", file=sys.stderr)
        return None

    try:
        with open(bib_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find all BibTeX entries
        entry_starts = [(m.start(), m.group(0)) for m in re.finditer(r'(?:^|\n)@\w+\s*{', content, re.MULTILINE)]

        removed_key = None
        new_content_parts = []
        last_end = 0

        for i, (start_pos, start_match) in enumerate(entry_starts):
            # Adjust start_pos if match includes leading newline
            if start_pos > 0 and content[start_pos] == '\n':
                start_pos += 1

            # Determine end of this entry
            if i + 1 < len(entry_starts):
                end_pos = entry_starts[i + 1][0]
                if end_pos > 0 and content[end_pos] == '\n':
                    end_pos += 1
            else:
                end_pos = len(content)

            # Extract entry text
            entry_text = content[start_pos:end_pos].rstrip()

            # Check if this entry has the PMID we're looking for
            pmid_match = re.search(r'pmid\s*=\s*[{"]?(\d+)[}"]?', entry_text, re.IGNORECASE)
            if pmid_match and pmid_match.group(1) == pmid:
                # Extract BibTeX key for reporting
                key_match = re.search(r'@(\w+)\s*{\s*([^,\s]+)\s*,', entry_text)
                if key_match:
                    removed_key = key_match.group(2)

                # Skip this entry (don't add to new_content_parts)
                new_content_parts.append(content[last_end:start_pos])
                last_end = end_pos
                print(f"✓ Found and removed entry with PMID {pmid} (key: {removed_key})")
                continue

        # Add remaining content
        new_content_parts.append(content[last_end:])

        if removed_key:
            # Write updated content back
            new_content = ''.join(new_content_parts)
            # Clean up multiple blank lines
            new_content = re.sub(r'\n{4,}', '\n\n\n', new_content)

            with open(bib_file, 'w', encoding='utf-8') as f:
                f.write(new_content)

            print(f"✓ Updated {bib_file}")
            return removed_key
        else:
            print(f"Note: PMID {pmid} not found in {bib_file} (may have been already removed)")
            return None

    except Exception as e:
        print(f"Error processing {bib_file}: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(
        description='Exclude a publication (by PMID) from the bibliography',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('--pmid', type=str, required=True,
                        help='PubMed ID to exclude')
    parser.add_argument('--member', type=str, required=True,
                        help='Member slug (e.g., rob-tolboom)')
    parser.add_argument('--reason', type=str, required=True,
                        help='Reason for exclusion')
    parser.add_argument('--excluded-by', type=str, default='',
                        help='Person who excluded (optional)')

    args = parser.parse_args()

    # Determine paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    members_dir = os.path.join(project_root, 'content', 'pages', 'members')
    exclude_file = os.path.join(script_dir, 'excluded_pmids.json')
    bib_file = os.path.join(project_root, 'content', 'umcg-anes.bib')

    print(f"Excluding PMID: {args.pmid}")
    print(f"Member: {args.member}")
    print(f"Reason: {args.reason}")
    print()

    # Validate member exists
    if not validate_member(args.member, members_dir):
        sys.exit(1)

    # Load existing exclusions
    excluded_data = load_excluded_pmids(exclude_file)

    # Check if already excluded
    if args.pmid in excluded_data:
        print(f"Warning: PMID {args.pmid} is already excluded:", file=sys.stderr)
        print(f"  Reason: {excluded_data[args.pmid].get('reason', 'N/A')}", file=sys.stderr)
        print(f"  Member: {excluded_data[args.pmid].get('member', 'N/A')}", file=sys.stderr)
        print(f"\nOverwriting with new information...", file=sys.stderr)

    # Add to exclusion list
    excluded_data[args.pmid] = {
        'reason': args.reason,
        'member': args.member,
        'excluded_date': datetime.now().strftime('%Y-%m-%d'),
    }

    if args.excluded_by:
        excluded_data[args.pmid]['excluded_by'] = args.excluded_by

    # Save exclusion list
    save_excluded_pmids(exclude_file, excluded_data)

    # Remove from bibliography
    removed_key = find_and_remove_bib_entry(bib_file, args.pmid)

    print()
    print("=" * 80)
    print("✓ Successfully excluded publication")
    print(f"  PMID: {args.pmid}")
    if removed_key:
        print(f"  BibTeX key removed: {removed_key}")
    print(f"  Member: {args.member}")
    print(f"  Reason: {args.reason}")
    print("=" * 80)

    return 0


if __name__ == '__main__':
    sys.exit(main())
