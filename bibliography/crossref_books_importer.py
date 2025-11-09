#!/usr/bin/env python3
"""
Crossref Books & Book Chapters Importer

This script automatically imports books and book chapters from Crossref API
for all group members and adds them to the umcg-anes.bib file.

Features:
- Reads member information from content/pages/members/*.md files
- Queries Crossref using multiple search strategies (initials + names)
- Filters results with author name matching to reduce false positives
- Converts Crossref metadata to BibTeX format
- Detects and avoids duplicates
- Merges new entries into umcg-anes.bib

Usage:
    python crossref_books_importer.py [options]

Options:
    --dry-run       : Show what would be added without modifying umcg-anes.bib
    --member NAME   : Only import for specific member (e.g., "Rob Tolboom")
    --active-only   : Only process active members (default: True)
    --max-results N : Maximum results per query (default: 100)
    --verbose       : Show detailed progress
"""

import os
import sys
import re
import time
import argparse
import json
from datetime import datetime
from typing import List, Dict, Set, Optional, Tuple
import requests


class MemberInfo:
    """Represents a group member with their publication identifiers."""

    def __init__(self, name: str, file_path: str):
        self.name = name
        self.file_path = file_path
        self.pub_name = None
        self.family_name = None
        self.given_name = None
        self.initials = None
        self.active = False

    def __repr__(self):
        return f"MemberInfo(name='{self.name}', family='{self.family_name}', given='{self.given_name}', active={self.active})"


class CrossrefBooksImporter:
    """Handles importing books and book chapters from Crossref."""

    BASE_URL = "https://api.crossref.org/works"
    BOOK_TYPES = ['book', 'book-chapter', 'monograph', 'edited-book']

    def __init__(self, rate_limit: float = 1.0, verbose: bool = False):
        """
        Initialize Crossref importer.

        Args:
            rate_limit: Seconds to wait between API calls (default: 1.0)
            verbose: Show detailed progress
        """
        self.rate_limit = rate_limit
        self.verbose = verbose
        self.last_request = 0
        self.request_count = 0
        self.stats = {
            'total_queries': 0,
            'total_results': 0,
            'filtered_matches': 0,
            'new_entries': 0
        }

    def _rate_limit_wait(self):
        """Wait to respect rate limits."""
        elapsed = time.time() - self.last_request
        if elapsed < self.rate_limit:
            wait_time = self.rate_limit - elapsed
            time.sleep(wait_time)
        self.last_request = time.time()
        self.request_count += 1

    def search_crossref(self, query_string: str, max_results: int = 100) -> List[Dict]:
        """
        Search Crossref API for books/chapters.

        Args:
            query_string: Author query string
            max_results: Maximum number of results

        Returns:
            List of Crossref work items
        """
        self._rate_limit_wait()
        self.stats['total_queries'] += 1

        type_filters = ','.join([f'type:{t}' for t in self.BOOK_TYPES])

        params = {
            'query.author': query_string,
            'filter': type_filters,
            'rows': max_results,
            'mailto': 'r.c.tolboom@umcg.nl'
        }

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                items = data.get('message', {}).get('items', [])
                self.stats['total_results'] += len(items)
                return items
            else:
                if self.verbose:
                    print(f"  Warning: API returned status {response.status_code}", file=sys.stderr)
                return []

        except Exception as e:
            if self.verbose:
                print(f"  Warning: Error querying Crossref: {e}", file=sys.stderr)
            return []

    def check_author_match(self, item: Dict, family: str, initials: str = None, given: str = None) -> bool:
        """
        Check if the target author is in the author list of an item.

        Args:
            item: Crossref work item
            family: Target family name
            initials: Target initials (e.g., 'RC', 'MMRF')
            given: Target given name (e.g., 'Robert', 'Michel')

        Returns:
            True if author matched, False otherwise
        """
        authors = item.get('author', [])

        for author in authors:
            author_family = author.get('family', '').lower()
            author_given = author.get('given', '').lower()

            # Match on family name
            if author_family != family.lower():
                continue

            # If we have initials to check
            if initials:
                # Extract initials from given name
                initials_in_given = ''.join([c for c in author_given if c.isupper() or c == '.'])
                initials_clean = initials_in_given.replace('.', '').replace(' ', '').upper()
                target_initials_clean = initials.replace('.', '').replace(' ', '').upper()

                if target_initials_clean in initials_clean:
                    return True

            # If we have given name to check
            if given and given.lower() in author_given:
                return True

        return False

    def search_member_publications(self, member: MemberInfo, max_results: int = 100) -> List[Dict]:
        """
        Search for books/chapters for a specific member using multiple strategies.

        Args:
            member: Member information
            max_results: Maximum results per query

        Returns:
            List of matched Crossref items (deduplicated)
        """
        if self.verbose:
            print(f"\n  Searching for {member.name}:")
            print(f"    Family: {member.family_name}, Given: {member.given_name}, Initials: {member.initials}")

        all_items = []
        seen_dois = set()

        # Strategy 1: Family + Initials
        if member.initials:
            query = f"{member.family_name} {member.initials}"
            if self.verbose:
                print(f"    Query: {query}")
            items = self.search_crossref(query, max_results)

            for item in items:
                if self.check_author_match(item, member.family_name, member.initials, member.given_name):
                    doi = item.get('DOI')
                    if doi and doi not in seen_dois:
                        all_items.append(item)
                        seen_dois.add(doi)
                        self.stats['filtered_matches'] += 1
                    elif not doi:
                        all_items.append(item)
                        self.stats['filtered_matches'] += 1

        # Strategy 2: Family + Given name
        if member.given_name:
            query = f"{member.family_name} {member.given_name}"
            if self.verbose:
                print(f"    Query: {query}")
            items = self.search_crossref(query, max_results)

            for item in items:
                if self.check_author_match(item, member.family_name, member.initials, member.given_name):
                    doi = item.get('DOI')
                    if doi and doi not in seen_dois:
                        all_items.append(item)
                        seen_dois.add(doi)
                        self.stats['filtered_matches'] += 1
                    elif not doi:
                        all_items.append(item)
                        self.stats['filtered_matches'] += 1

        if self.verbose:
            print(f"    Found {len(all_items)} unique matches")

        return all_items

    def crossref_to_bibtex(self, item: Dict, existing_keys: Set[str]) -> str:
        """
        Convert Crossref item to BibTeX entry.

        Args:
            item: Crossref work item
            existing_keys: Set of existing BibTeX keys to avoid duplicates

        Returns:
            BibTeX entry as string
        """
        item_type = item.get('type', 'misc')

        # Map Crossref types to BibTeX types
        type_map = {
            'book': 'book',
            'monograph': 'book',
            'edited-book': 'book',
            'book-chapter': 'incollection',
            'book-section': 'incollection'
        }

        bib_type = type_map.get(item_type, 'misc')

        # Generate BibTeX key
        authors = item.get('author', [])
        if authors:
            first_author_family = authors[0].get('family', 'Unknown')
            first_author_family = re.sub(r'[^a-zA-Z]', '', first_author_family)
        else:
            first_author_family = 'Unknown'

        published = item.get('published-print', item.get('published-online', {}))
        year = str(published.get('date-parts', [[None]])[0][0] or '')
        year_short = year[-2:] if year else '00'

        # Ensure unique key
        base_key = f"{first_author_family}{year_short}"
        bib_key = base_key
        suffix = ord('a')
        while bib_key in existing_keys:
            bib_key = f"{base_key}{chr(suffix)}"
            suffix += 1

        existing_keys.add(bib_key)

        # Build BibTeX entry
        lines = [f"@{bib_type}{{{bib_key},"]

        # Title
        title = item.get('title', [''])[0]
        if title:
            lines.append(f"  title = {{{title}}},")

        # Authors
        if authors:
            author_strings = []
            for author in authors:
                given = author.get('given', '')
                family = author.get('family', '')
                if family:
                    if given:
                        author_strings.append(f"{family}, {given}")
                    else:
                        author_strings.append(family)

            if author_strings:
                lines.append(f"  author = {{{' and '.join(author_strings)}}},")

        # Year
        if year:
            lines.append(f"  year = {{{year}}},")

        # Publisher
        publisher = item.get('publisher', '')
        if publisher:
            lines.append(f"  publisher = {{{publisher}}},")

        # ISBN
        isbn_list = item.get('ISBN', [])
        if isbn_list:
            lines.append(f"  isbn = {{{isbn_list[0]}}},")

        # DOI
        doi = item.get('DOI', '')
        if doi:
            lines.append(f"  doi = {{{doi}}},")

        # For book chapters: booktitle
        if bib_type == 'incollection':
            container = item.get('container-title', [''])[0]
            if container:
                lines.append(f"  booktitle = {{{container}}},")

        # Citations (if available)
        citations = item.get('is-referenced-by-count', 0)
        if citations:
            lines.append(f"  citations = {{{citations}}},")

        lines.append("}")

        return '\n'.join(lines)


def parse_member_files(members_dir: str, active_only: bool = True) -> List[MemberInfo]:
    """Parse all member markdown files and extract relevant information."""
    members = []

    if not os.path.exists(members_dir):
        print(f"Error: Members directory not found: {members_dir}", file=sys.stderr)
        return members

    for filename in os.listdir(members_dir):
        if not filename.endswith('.md'):
            continue

        filepath = os.path.join(members_dir, filename)
        member = parse_member_file(filepath)

        if member and (not active_only or member.active):
            members.append(member)

    return members


def parse_member_file(filepath: str) -> Optional[MemberInfo]:
    """Parse a single member markdown file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract name
        name_match = re.search(r'^name:\s*(.+)$', content, re.MULTILINE)
        if not name_match:
            return None

        name = name_match.group(1).strip()
        member = MemberInfo(name, filepath)

        # Extract pub_name if available (preferred for searches)
        pub_name_match = re.search(r'^pub_name:\s*(.+)$', content, re.MULTILINE)
        if pub_name_match:
            member.pub_name = pub_name_match.group(1).strip()
        else:
            member.pub_name = name

        # Extract family and given names
        parts = member.pub_name.split()
        if len(parts) >= 2:
            member.family_name = parts[-1]
            member.given_name = parts[0]

            # Extract initials from all parts except last (family name)
            initials = []
            for part in parts[:-1]:
                clean_part = part.replace('.', '').strip()
                if clean_part:
                    initials.append(clean_part[0].upper())
            member.initials = ''.join(initials)

        # Check if active
        active_match = re.search(r'^active:\s*(yes|true)$', content, re.MULTILINE | re.IGNORECASE)
        member.active = bool(active_match)

        return member

    except Exception as e:
        print(f"Error parsing {filepath}: {e}", file=sys.stderr)
        return None


def read_existing_bib(bib_path: str) -> Tuple[str, Set[str], Set[str]]:
    """
    Read existing BibTeX file and extract keys and DOIs.

    Returns:
        Tuple of (file_content, existing_keys, existing_dois)
    """
    existing_keys = set()
    existing_dois = set()

    if not os.path.exists(bib_path):
        return "", existing_keys, existing_dois

    with open(bib_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    # Extract all BibTeX keys
    for match in re.finditer(r'@\w+\{([^,]+),', content):
        existing_keys.add(match.group(1))

    # Extract all DOIs
    for match in re.finditer(r'doi\s*=\s*{([^}]+)}', content, re.IGNORECASE):
        existing_dois.add(match.group(1).strip())

    return content, existing_keys, existing_dois


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Import books and book chapters from Crossref for group members'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be added without modifying umcg-anes.bib')
    parser.add_argument('--member', type=str,
                        help='Only import for specific member (e.g., "Rob Tolboom")')
    parser.add_argument('--active-only', action='store_true', default=True,
                        help='Only process active members (default: True)')
    parser.add_argument('--max-results', type=int, default=100,
                        help='Maximum results per query (default: 100)')
    parser.add_argument('--verbose', action='store_true',
                        help='Show detailed progress')

    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"Crossref Books & Chapters Importer")
    print(f"{'='*70}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if args.dry_run:
        print("MODE: DRY RUN (no changes will be made)")
    print(f"{'='*70}\n")

    # Paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    members_dir = os.path.join(project_root, 'content', 'pages', 'members')
    bib_path = os.path.join(project_root, 'content', 'umcg-anes.bib')

    # Parse members
    print(f"Reading member files from: {members_dir}")
    members = parse_member_files(members_dir, active_only=args.active_only)

    if args.member:
        members = [m for m in members if args.member.lower() in m.name.lower()]

    if not members:
        print("No members found to process")
        return

    print(f"Found {len(members)} member(s) to process")

    # Read existing BibTeX file
    print(f"\nReading existing BibTeX file: {bib_path}")
    bib_content, existing_keys, existing_dois = read_existing_bib(bib_path)
    print(f"Existing entries: {len(existing_keys)}, DOIs: {len(existing_dois)}")

    # Initialize importer
    importer = CrossrefBooksImporter(rate_limit=1.0, verbose=args.verbose)

    # Collect new entries
    new_entries = []

    # Process each member
    for i, member in enumerate(members, 1):
        print(f"\n[{i}/{len(members)}] Processing: {member.name}")

        items = importer.search_member_publications(member, max_results=args.max_results)

        # Filter out existing entries
        for item in items:
            doi = item.get('DOI', '')

            # Skip if DOI already exists
            if doi and doi in existing_dois:
                if args.verbose:
                    print(f"  Skipping (DOI exists): {item.get('title', [''])[0][:60]}...")
                continue

            # Convert to BibTeX
            bib_entry = importer.crossref_to_bibtex(item, existing_keys)
            new_entries.append(bib_entry)

            # Add DOI to set to avoid duplicates within this run
            if doi:
                existing_dois.add(doi)

            title = item.get('title', ['No title'])[0]
            item_type = item.get('type', 'unknown')
            print(f"  + NEW: [{item_type}] {title[:60]}...")

    # Summary
    print(f"\n{'='*70}")
    print("Summary")
    print(f"{'='*70}")
    print(f"Members processed:    {len(members)}")
    print(f"Total API queries:    {importer.stats['total_queries']}")
    print(f"Total results:        {importer.stats['total_results']}")
    print(f"Filtered matches:     {importer.stats['filtered_matches']}")
    print(f"New entries to add:   {len(new_entries)}")
    print(f"{'='*70}\n")

    # Write new entries
    if new_entries:
        if args.dry_run:
            print("DRY RUN - would add the following entries:\n")
            for entry in new_entries[:5]:  # Show first 5
                print(entry)
                print()
            if len(new_entries) > 5:
                print(f"... and {len(new_entries) - 5} more entries")
        else:
            # Append to BibTeX file
            print(f"Appending {len(new_entries)} new entries to {bib_path}")

            with open(bib_path, 'a', encoding='utf-8') as f:
                for entry in new_entries:
                    f.write('\n\n')
                    f.write(entry)

            print("✓ Successfully updated umcg-anes.bib")
    else:
        print("No new entries to add")

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
