#!/usr/bin/env python3
"""
Script to add or update citation counts from Crossref API to BibTeX entries.

Usage:
    python add_citations.py [--test N] [--verbose]

    --test N: Only process first N entries (for testing)
    --verbose: Show detailed progress
"""

import requests
import time
import re
import sys
import argparse
from datetime import datetime


class CrossrefCitationUpdater:
    def __init__(self, bib_path, rate_limit=1.0, verbose=False):
        """
        Initialize the citation updater.

        Args:
            bib_path: Path to the .bib file
            rate_limit: Seconds to wait between API calls (default: 1.0)
            verbose: Print detailed progress
        """
        self.bib_path = bib_path
        self.rate_limit = rate_limit
        self.verbose = verbose
        self.stats = {
            'total_entries': 0,
            'with_doi': 0,
            'api_success': 0,
            'api_failure': 0,
            'added': 0,
            'updated': 0,
            'unchanged': 0
        }

    def get_citation_count(self, doi):
        """
        Query Crossref API for citation count.

        Args:
            doi: DOI string

        Returns:
            int: Citation count, or None if failed
        """
        # Clean DOI
        doi = doi.strip()
        if doi.startswith('https://doi.org/'):
            doi = doi.replace('https://doi.org/', '')

        url = f"https://api.crossref.org/works/{doi}"

        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                count = data.get('message', {}).get('is-referenced-by-count', 0)
                self.stats['api_success'] += 1
                return count
            else:
                if self.verbose:
                    print(f"  Warning: API returned status {response.status_code} for DOI: {doi}")
                self.stats['api_failure'] += 1
                return None
        except Exception as e:
            if self.verbose:
                print(f"  Error querying DOI {doi}: {e}")
            self.stats['api_failure'] += 1
            return None

    def extract_entry_info(self, entry_text):
        """
        Extract DOI and existing citations from a bib entry.

        Returns:
            tuple: (doi, current_citations, has_citations_field)
        """
        doi_match = re.search(r'doi\s*=\s*{([^}]+)}', entry_text, re.IGNORECASE)
        doi = doi_match.group(1).strip() if doi_match else None

        # Check for existing citations field
        citations_match = re.search(r'citations\s*=\s*{(\d+)}', entry_text, re.IGNORECASE)
        current_citations = int(citations_match.group(1)) if citations_match else None
        has_citations = citations_match is not None

        return doi, current_citations, has_citations

    def add_or_update_citations(self, entry_text, new_count):
        """
        Add or update the citations field in a bib entry.

        Args:
            entry_text: The original bib entry text
            new_count: The new citation count

        Returns:
            str: Modified entry text
        """
        # Check if citations field already exists
        citations_pattern = r'(\s+citations\s*=\s*{)\d+(},?\s*\n)'

        if re.search(citations_pattern, entry_text, re.IGNORECASE):
            # Update existing field
            modified = re.sub(citations_pattern,
                            rf'\g<1>{new_count}\g<2>',
                            entry_text,
                            flags=re.IGNORECASE)
            self.stats['updated'] += 1
        else:
            # Add new field before the closing brace
            # Find the last field (before the final closing brace)
            lines = entry_text.rstrip().split('\n')

            # Insert citations field before the last line (which is just "}")
            if lines[-1].strip() == '}':
                # Find the last field line
                insert_pos = len(lines) - 1
                # Add comma to previous line if it doesn't have one
                if not lines[insert_pos - 1].rstrip().endswith(','):
                    lines[insert_pos - 1] = lines[insert_pos - 1].rstrip() + ','
                # Insert citations field
                lines.insert(insert_pos, f'  citations = {{{new_count}}},')
                modified = '\n'.join(lines)
                self.stats['added'] += 1
            else:
                # Fallback: just append before closing brace
                modified = entry_text.rstrip() + f'\n  citations = {{{new_count}}},\n}}\n'
                self.stats['added'] += 1

        return modified

    def process_bib_file(self, test_limit=None):
        """
        Process the entire .bib file.

        Args:
            test_limit: If set, only process first N entries with DOI
        """
        print(f"Reading {self.bib_path}...")

        with open(self.bib_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()

        # Split into entries (everything from @ to the matching closing })
        entries = []
        current_pos = 0
        bracket_count = 0
        entry_start = None

        for i, char in enumerate(content):
            if content[i:i+1] == '@' and bracket_count == 0:
                if entry_start is not None:
                    entries.append((entry_start, current_pos))
                entry_start = i

            if char == '{':
                bracket_count += 1
            elif char == '}':
                bracket_count -= 1
                if bracket_count == 0 and entry_start is not None:
                    current_pos = i + 1

        # Add last entry
        if entry_start is not None:
            entries.append((entry_start, len(content)))

        self.stats['total_entries'] = len(entries)
        print(f"Found {len(entries)} entries")

        # Process entries
        modified_content = content
        processed_with_doi = 0
        offset = 0  # Track position changes due to modifications

        for idx, (start, end) in enumerate(entries):
            # Adjust for offset
            adj_start = start + offset
            adj_end = end + offset

            entry_text = modified_content[adj_start:adj_end]

            # Skip comments
            if entry_text.strip().lower().startswith('@comment'):
                continue

            # Extract info
            doi, current_citations, has_citations = self.extract_entry_info(entry_text)

            if doi:
                self.stats['with_doi'] += 1
                processed_with_doi += 1

                # Check test limit
                if test_limit and processed_with_doi > test_limit:
                    print(f"\nReached test limit of {test_limit} entries with DOI")
                    break

                # Progress indicator
                if self.verbose or (self.stats['with_doi'] % 50 == 0):
                    print(f"Processing {self.stats['with_doi']}/{self.stats['total_entries']}: DOI {doi}")

                # Get citation count from Crossref
                citation_count = self.get_citation_count(doi)

                # Rate limiting
                time.sleep(self.rate_limit)

                if citation_count is not None:
                    # Check if update needed
                    if current_citations == citation_count:
                        self.stats['unchanged'] += 1
                        if self.verbose:
                            print(f"  Citations unchanged: {citation_count}")
                    else:
                        # Modify entry
                        new_entry_text = self.add_or_update_citations(entry_text, citation_count)

                        # Update content
                        modified_content = (modified_content[:adj_start] +
                                          new_entry_text +
                                          modified_content[adj_end:])

                        # Update offset
                        offset += len(new_entry_text) - len(entry_text)

                        if self.verbose:
                            action = "Updated" if has_citations else "Added"
                            print(f"  {action} citations: {current_citations} -> {citation_count}")

        return modified_content

    def run(self, test_limit=None, dry_run=False):
        """
        Main execution method.

        Args:
            test_limit: If set, only process first N entries
            dry_run: If True, don't write changes to file
        """
        print(f"\n{'='*60}")
        print(f"Crossref Citation Updater")
        print(f"{'='*60}")
        print(f"BibTeX file: {self.bib_path}")
        print(f"Rate limit: {self.rate_limit} req/sec")
        if test_limit:
            print(f"TEST MODE: Processing first {test_limit} entries only")
        print(f"{'='*60}\n")

        start_time = time.time()

        # Process file
        modified_content = self.process_bib_file(test_limit)

        # Write results
        if not dry_run:
            # Backup original
            backup_path = self.bib_path + '.backup'
            print(f"\nCreating backup: {backup_path}")
            with open(self.bib_path, 'r', encoding='utf-8-sig') as f:
                with open(backup_path, 'w', encoding='utf-8') as backup:
                    backup.write(f.read())

            # Write modified content
            print(f"Writing updated file: {self.bib_path}")
            with open(self.bib_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)
        else:
            print("\nDRY RUN - No changes written")

        # Print statistics
        elapsed = time.time() - start_time
        print(f"\n{'='*60}")
        print("Statistics:")
        print(f"{'='*60}")
        print(f"Total entries:        {self.stats['total_entries']}")
        print(f"Entries with DOI:     {self.stats['with_doi']}")
        print(f"API successful:       {self.stats['api_success']}")
        print(f"API failed:           {self.stats['api_failure']}")
        print(f"Citations added:      {self.stats['added']}")
        print(f"Citations updated:    {self.stats['updated']}")
        print(f"Citations unchanged:  {self.stats['unchanged']}")
        print(f"Time elapsed:         {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
        print(f"{'='*60}\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Add/update Crossref citation counts to BibTeX file')
    parser.add_argument('--test', type=int, help='Only process first N entries (for testing)')
    parser.add_argument('--verbose', action='store_true', help='Show detailed progress')
    parser.add_argument('--dry-run', action='store_true', help='Do not write changes to file')
    parser.add_argument('--bib', default='../content/umcg-anes.bib', help='Path to .bib file')

    args = parser.parse_args()

    updater = CrossrefCitationUpdater(
        bib_path=args.bib,
        rate_limit=1.0,  # 1 request per second
        verbose=args.verbose
    )

    updater.run(test_limit=args.test, dry_run=args.dry_run)
