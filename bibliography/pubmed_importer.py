#!/usr/bin/env python3
"""
PubMed Bibliography Importer

This script automatically imports publications from PubMed for all group members
and adds them to the umcg-anes.bib file.

Features:
- Reads member information from content/pages/members/*.md files
- Queries PubMed using ORCID IDs and/or author names
- Converts PubMed XML to BibTeX format
- Detects and avoids duplicates
- Merges new entries into umcg-anes.bib

Usage:
    python pubmed_importer.py [options]

Options:
    --dry-run       : Show what would be added without modifying umcg-anes.bib
    --member NAME   : Only import for specific member (e.g., "Bram van Ginneken")
    --since YEAR    : Only import publications from YEAR onwards (e.g., 2020)
    --email EMAIL   : Email for PubMed API (required for >3 requests/sec)
    --api-key KEY   : PubMed API key for faster queries (10 req/sec)
    --max-results N : Maximum results per author (default: 100)
"""

import os
import sys
import re
import time
import argparse
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Set, Optional, Tuple
import json


class MemberInfo:
    """Represents a group member with their publication identifiers."""

    def __init__(self, name: str, file_path: str):
        self.name = name
        self.file_path = file_path
        self.orcid = None
        self.pub_name = None
        self.active = False

    def __repr__(self):
        return f"MemberInfo(name='{self.name}', orcid='{self.orcid}', active={self.active})"


class PubMedImporter:
    """Handles importing publications from PubMed."""

    ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    def __init__(self, email: str = None, api_key: str = None, rate_limit: float = None):
        """
        Initialize PubMed importer.

        Args:
            email: Email for PubMed API (required by NCBI)
            api_key: PubMed API key for faster queries
            rate_limit: Seconds to wait between requests (default: 1.0 sec = 1 req/sec)
                       NCBI allows max 10 req/sec with API key, 3 req/sec without
                       Being conservative prevents hitting limits with many members
        """
        self.email = email or "pubmed@example.com"  # Default email if none provided
        self.api_key = api_key

        # Conservative default: 1 request per second
        # This is safe for large batch imports with many members
        if rate_limit is not None:
            self.rate_limit = rate_limit
        elif api_key:
            self.rate_limit = 1.0  # Conservative even with API key
        else:
            self.rate_limit = 1.5  # Extra conservative without API key

        self.last_request = 0
        self.request_count = 0

    def _rate_limit_wait(self):
        """Wait to respect rate limits."""
        elapsed = time.time() - self.last_request
        if elapsed < self.rate_limit:
            wait_time = self.rate_limit - elapsed
            time.sleep(wait_time)
        self.last_request = time.time()
        self.request_count += 1

    def _build_url_params(self, **kwargs) -> Dict[str, str]:
        """Build URL parameters with email and API key if available."""
        params = kwargs.copy()
        if self.email:
            params['email'] = self.email
        if self.api_key:
            params['api_key'] = self.api_key
        return params

    def search_pubmed(self, query: str, retmax: int = 100, mindate: str = None) -> List[str]:
        """
        Search PubMed and return list of PMIDs.

        Args:
            query: PubMed search query
            retmax: Maximum number of results
            mindate: Minimum date in format YYYY/MM/DD

        Returns:
            List of PMIDs
        """
        self._rate_limit_wait()

        params = self._build_url_params(
            db='pubmed',
            term=query,
            retmode='json',
            retmax=retmax
        )

        if mindate:
            params['mindate'] = mindate
            params['datetype'] = 'pdat'

        url = f"{self.ESEARCH_URL}?{urllib.parse.urlencode(params)}"

        # Debug: print URL for first few requests
        if os.environ.get('DEBUG_PUBMED'):
            print(f"  DEBUG: {url}", file=sys.stderr)

        # Add User-Agent header to avoid being blocked
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (compatible; PubMedImporter/1.0; +mailto:' + self.email + ')')

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode())
                pmids = data.get('esearchresult', {}).get('idlist', [])
                return pmids
        except urllib.error.HTTPError as e:
            print(f"  Warning: HTTP Error {e.code} - {e.reason}", file=sys.stderr)
            if e.code == 403:
                print(f"  Note: Consider providing --email parameter for better API access", file=sys.stderr)
            return []
        except Exception as e:
            print(f"  Warning: Error searching PubMed: {e}", file=sys.stderr)
            return []

    def fetch_pubmed_details(self, pmids: List[str]) -> List[Dict]:
        """
        Fetch detailed information for PMIDs.

        Args:
            pmids: List of PubMed IDs

        Returns:
            List of publication dictionaries
        """
        if not pmids:
            return []

        self._rate_limit_wait()

        params = self._build_url_params(
            db='pubmed',
            id=','.join(pmids),
            retmode='xml'
        )

        url = f"{self.EFETCH_URL}?{urllib.parse.urlencode(params)}"

        # Add User-Agent header to avoid being blocked
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (compatible; PubMedImporter/1.0; +mailto:' + self.email + ')')

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                xml_data = response.read().decode('utf-8')
                return self._parse_pubmed_xml(xml_data)
        except urllib.error.HTTPError as e:
            print(f"  Warning: HTTP Error {e.code} - {e.reason}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"  Warning: Error fetching PubMed details: {e}", file=sys.stderr)
            return []

    def _parse_pubmed_xml(self, xml_data: str) -> List[Dict]:
        """Parse PubMed XML response into publication dictionaries."""
        publications = []

        try:
            root = ET.fromstring(xml_data)

            for article in root.findall('.//PubmedArticle'):
                pub = self._extract_article_data(article)
                if pub:
                    publications.append(pub)

        except Exception as e:
            print(f"Error parsing XML: {e}", file=sys.stderr)

        return publications

    def _extract_article_data(self, article: ET.Element) -> Optional[Dict]:
        """Extract publication data from PubMed XML article element."""
        try:
            medline = article.find('.//MedlineCitation')
            pubmed_data = article.find('.//PubmedData')

            if medline is None:
                return None

            pmid = medline.findtext('.//PMID', '')

            # Article details
            art = medline.find('.//Article')
            if art is None:
                return None

            title = art.findtext('.//ArticleTitle', '')
            # Remove trailing period if present
            title = title.rstrip('.')

            # Authors
            authors = []
            author_list = art.find('.//AuthorList')
            if author_list is not None:
                for author in author_list.findall('.//Author'):
                    lastname = author.findtext('LastName', '')
                    forename = author.findtext('ForeName', '')
                    initials = author.findtext('Initials', '')

                    if lastname:
                        if forename:
                            authors.append(f"{forename} {lastname}")
                        elif initials:
                            authors.append(f"{initials} {lastname}")
                        else:
                            authors.append(lastname)

            # Journal
            journal = art.findtext('.//Journal/Title', '')
            journal_iso = art.findtext('.//Journal/ISOAbbreviation', journal)

            # Date
            pub_date = art.find('.//Journal/JournalIssue/PubDate')
            year = ''
            month = ''
            if pub_date is not None:
                year = pub_date.findtext('Year', '')
                month_text = pub_date.findtext('Month', '')
                # Convert month name to number
                month = self._month_to_number(month_text)

                # Handle MedlineDate (e.g., "2020 Spring")
                if not year:
                    medline_date = pub_date.findtext('MedlineDate', '')
                    year_match = re.search(r'(\d{4})', medline_date)
                    if year_match:
                        year = year_match.group(1)

            # Volume, Issue, Pages
            volume = art.findtext('.//Journal/JournalIssue/Volume', '')
            issue = art.findtext('.//Journal/JournalIssue/Issue', '')
            pages = art.findtext('.//Pagination/MedlinePgn', '')

            # Abstract
            abstract_texts = art.findall('.//Abstract/AbstractText')
            abstract = ' '.join([abs_text.text or '' for abs_text in abstract_texts])

            # DOI
            doi = ''
            article_ids = pubmed_data.findall('.//ArticleId') if pubmed_data else []
            for aid in article_ids:
                if aid.get('IdType') == 'doi':
                    doi = aid.text or ''
                    break

            # Publication Type
            pub_type = 'article'
            pub_type_list = art.find('.//PublicationTypeList')
            if pub_type_list is not None:
                for pt in pub_type_list.findall('.//PublicationType'):
                    pt_text = (pt.text or '').lower()
                    if 'review' in pt_text:
                        pub_type = 'article'  # Keep as article in BibTeX
                        break

            return {
                'pmid': pmid,
                'title': title,
                'authors': authors,
                'journal': journal_iso or journal,
                'year': year,
                'month': month,
                'volume': volume,
                'issue': issue,
                'pages': pages,
                'abstract': abstract,
                'doi': doi,
                'type': pub_type
            }

        except Exception as e:
            print(f"Error extracting article data: {e}", file=sys.stderr)
            return None

    def _month_to_number(self, month_text: str) -> str:
        """Convert month name to number string."""
        if not month_text:
            return ''

        months = {
            'jan': '1', 'january': '1',
            'feb': '2', 'february': '2',
            'mar': '3', 'march': '3',
            'apr': '4', 'april': '4',
            'may': '5',
            'jun': '6', 'june': '6',
            'jul': '7', 'july': '7',
            'aug': '8', 'august': '8',
            'sep': '9', 'september': '9',
            'oct': '10', 'october': '10',
            'nov': '11', 'november': '11',
            'dec': '12', 'december': '12'
        }

        month_lower = month_text.lower()
        return months.get(month_lower, '')

    def search_by_orcid(self, orcid: str, since_year: int = None, max_results: int = 100) -> List[str]:
        """Search PubMed by ORCID."""
        # Extract just the ORCID number
        orcid_match = re.search(r'(\d{4}-\d{4}-\d{4}-\d{3}[0-9X])', orcid)
        if not orcid_match:
            return []

        orcid_id = orcid_match.group(1)
        query = f"{orcid_id}[auid]"

        mindate = f"{since_year}/01/01" if since_year else None

        print(f"  Searching PubMed with ORCID: {orcid_id}")
        return self.search_pubmed(query, retmax=max_results, mindate=mindate)

    def _format_name_for_pubmed(self, name: str) -> str:
        """
        Convert name from 'Firstname Lastname' to PubMed format 'Lastname, Firstname'.

        PubMed expects author names in the format:
        - "Lastname, Firstname" or "Lastname Firstname"
        - "Lastname Initials" (without periods)

        Examples:
            "Riccardo Samperna" -> "Samperna, Riccardo"
            "Joeran S. Bosma" -> "Bosma, Joeran S"
            "Clara I Sánchez" -> "Sánchez, Clara I"

        Args:
            name: Name in format "Firstname [Middle] Lastname"

        Returns:
            Name formatted for PubMed search: "Lastname, Firstname [Middle]"
        """
        if not name:
            return name

        # Split name into parts
        parts = name.strip().split()

        if len(parts) == 0:
            return name
        elif len(parts) == 1:
            # Single name, return as-is
            return name
        else:
            # Multiple parts: assume last part is lastname
            lastname = parts[-1]
            firstname_parts = parts[:-1]
            firstname = ' '.join(firstname_parts)

            # Remove periods from initials for PubMed format
            firstname = firstname.replace('.', '')

            return f"{lastname}, {firstname}"

    def search_by_author_name(self, name: str, since_year: int = None, max_results: int = 100) -> List[str]:
        """
        Search PubMed by author name.

        Converts name from 'Firstname Lastname' to PubMed format 'Lastname, Firstname'.
        """
        # Convert to PubMed format
        pubmed_name = self._format_name_for_pubmed(name)
        query = f'"{pubmed_name}"[Author]'

        mindate = f"{since_year}/01/01" if since_year else None

        print(f"  Searching PubMed with name: {name} (formatted as: {pubmed_name})")
        return self.search_pubmed(query, retmax=max_results, mindate=mindate)

    def _extract_initials(self, name: str) -> str:
        """
        Extract initials from a name.

        Examples:
            "Robert Tolboom" -> "R"
            "Rob C. Tolboom" -> "RC"
            "Rob Tolboom" -> "R"
            "Clara I Sánchez" -> "CI"

        Args:
            name: Full name in format "Firstname [Middle] Lastname"

        Returns:
            Initials (e.g., "R", "RC", "CI")
        """
        if not name:
            return ""

        # Split name into parts
        parts = name.strip().split()

        if len(parts) <= 1:
            return ""

        # Get initials from all parts except the last (lastname)
        initials = []
        for part in parts[:-1]:
            # Remove periods and get first character
            clean_part = part.replace('.', '').strip()
            if clean_part:
                initials.append(clean_part[0].upper())

        return ''.join(initials)

    def search_by_author_initials(self, name: str, since_year: int = None, max_results: int = 100) -> List[str]:
        """
        Search PubMed by author name with initials.

        Converts name to format "Lastname, Initials".
        Examples:
            "Robert Tolboom" -> "Tolboom, R"
            "Rob C. Tolboom" -> "Tolboom, RC"

        Many publications use initials instead of full first names,
        so this search helps find those publications.
        """
        if not name:
            return []

        # Split name into parts
        parts = name.strip().split()

        if len(parts) <= 1:
            return []

        # Extract lastname and initials
        lastname = parts[-1]
        initials = self._extract_initials(name)

        if not initials:
            return []

        # Format as "Lastname, Initials"
        pubmed_name = f"{lastname}, {initials}"
        query = f'"{pubmed_name}"[Author]'

        mindate = f"{since_year}/01/01" if since_year else None

        print(f"  Searching PubMed with initials: {name} (formatted as: {pubmed_name})")
        return self.search_pubmed(query, retmax=max_results, mindate=mindate)


def parse_member_files(members_dir: str) -> List[MemberInfo]:
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
        if member:
            members.append(member)

    return members


def parse_member_file(filepath: str) -> Optional[MemberInfo]:
    """Parse a single member markdown file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract metadata fields
        name_match = re.search(r'^name:\s*(.+)$', content, re.MULTILINE)
        if not name_match:
            return None

        name = name_match.group(1).strip()
        member = MemberInfo(name, filepath)

        # Extract ORCID
        orcid_match = re.search(r'^orcid:\s*(.+)$', content, re.MULTILINE)
        if orcid_match:
            member.orcid = orcid_match.group(1).strip()

        # Extract pub_name if available
        pub_name_match = re.search(r'^pub_name:\s*(.+)$', content, re.MULTILINE)
        if pub_name_match:
            member.pub_name = pub_name_match.group(1).strip()

        # Check if active
        active_match = re.search(r'^active:\s*(yes|true)$', content, re.MULTILINE | re.IGNORECASE)
        member.active = bool(active_match)

        return member

    except Exception as e:
        print(f"Error parsing {filepath}: {e}", file=sys.stderr)
        return None


def publication_to_bibtex(pub: Dict, existing_keys: Set[str]) -> str:
    """
    Convert publication dictionary to BibTeX entry.

    Args:
        pub: Publication dictionary from PubMed
        existing_keys: Set of existing BibTeX keys to avoid duplicates

    Returns:
        BibTeX entry as string
    """
    # Generate BibTeX key
    if pub['authors']:
        first_author = pub['authors'][0]
        last_name = first_author.split()[-1]
        # Remove non-alphanumeric characters
        last_name = re.sub(r'[^a-zA-Z]', '', last_name)
    else:
        last_name = 'Unknown'

    year_short = pub['year'][-2:] if pub['year'] else '00'
    base_key = f"{last_name}{year_short}"

    # Ensure unique key
    bib_key = base_key
    suffix = ord('a')
    while bib_key in existing_keys:
        bib_key = f"{base_key}{chr(suffix)}"
        suffix += 1

    existing_keys.add(bib_key)

    # Build BibTeX entry
    lines = [f"@{pub['type']}{{{bib_key},"]

    # Authors - format as "Lastname, Firstname and Lastname, Firstname"
    if pub['authors']:
        author_str = ' and '.join(pub['authors'])
        lines.append(f"  author = {{{author_str}}},")

    # Title
    if pub['title']:
        lines.append(f"  title = {{{pub['title']}}},")

    # Journal
    if pub['journal']:
        lines.append(f"  journal = {{{pub['journal']}}},")

    # Year
    if pub['year']:
        lines.append(f"  year = {{{pub['year']}}},")

    # Volume
    if pub['volume']:
        lines.append(f"  volume = {{{pub['volume']}}},")

    # Issue/Number
    if pub['issue']:
        lines.append(f"  number = {{{pub['issue']}}},")

    # Pages
    if pub['pages']:
        lines.append(f"  pages = {{{pub['pages']}}},")

    # Month
    if pub['month']:
        lines.append(f"  month = {{{pub['month']}}},")

    # DOI
    if pub['doi']:
        lines.append(f"  doi = {{{pub['doi']}}},")

    # PMID
    if pub['pmid']:
        lines.append(f"  pmid = {{{pub['pmid']}}},")

    # Abstract
    if pub['abstract']:
        # Escape special characters and wrap long abstracts
        abstract = pub['abstract'].replace('{', '\\{').replace('}', '\\}')
        lines.append(f"  abstract = {{{abstract}}},")

    # Add DIAG note
    lines.append(f"  optnote = {{DIAG, RADIOLOGY}},")

    lines.append("}")

    return '\n'.join(lines)


def load_existing_entries(bib_file: str) -> Dict[str, List[Dict]]:
    """
    Load all existing BibTeX entries with their PMIDs.

    Returns:
        Dictionary mapping PMID to list of entry infos:
        {pmid: [{'key': bibkey, 'entry': full_entry_text}, ...]}

    Note: Returns a list per PMID to handle duplicates that may exist in the file.
    """
    entries = {}

    if not os.path.exists(bib_file):
        return entries

    try:
        with open(bib_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find all BibTeX entries with their PMIDs
        # Use improved parsing that handles nested braces in abstracts
        # Split by entry start pattern - entries begin with @ at start of line
        entry_starts = [(m.start(), m.group(0)) for m in re.finditer(r'(?:^|\n)@\w+\s*{', content, re.MULTILINE)]

        for i, (start_pos, start_match) in enumerate(entry_starts):
            # Adjust start_pos if match includes leading newline
            if start_pos > 0 and content[start_pos] == '\n':
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

            # Only process @article entries (skip @string, etc.)
            if not entry_text.startswith('@article'):
                continue

            # Extract PMID from this entry
            pmid_match = re.search(r'pmid\s*=\s*[{\"]?(\d+)[}\"]?', entry_text, re.IGNORECASE)
            if pmid_match:
                pmid = pmid_match.group(1)

                # Extract BibTeX key
                key_match = re.search(r'@(\w+)\s*{\s*([^,\s]+)\s*,', entry_text)
                if key_match:
                    bib_key = key_match.group(2)

                    # Store as list to handle duplicates
                    if pmid not in entries:
                        entries[pmid] = []

                    entries[pmid].append({
                        'key': bib_key,
                        'entry': entry_text
                    })

    except Exception as e:
        print(f"Error reading {bib_file}: {e}", file=sys.stderr)

    return entries


def load_existing_pmids(bib_file: str) -> Set[str]:
    """Load all PMIDs that already exist in the BibTeX file."""
    pmids = set()

    if not os.path.exists(bib_file):
        return pmids

    try:
        with open(bib_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find ALL PMIDs directly in the file, not through dict
        # This prevents missing duplicates due to dict overwriting
        pmid_matches = re.findall(r'pmid\s*=\s*[{\"]?(\d+)[}\"]?', content, re.IGNORECASE)
        pmids = set(pmid_matches)

    except Exception as e:
        print(f"Error reading {bib_file}: {e}", file=sys.stderr)

    return pmids


def load_existing_bibkeys(bib_file: str) -> Set[str]:
    """Load all BibTeX keys that already exist."""
    keys = set()

    if not os.path.exists(bib_file):
        return keys

    try:
        with open(bib_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find all BibTeX entry keys
        key_pattern = r'@\w+\s*{\s*([^,\s]+)\s*,'
        for match in re.finditer(key_pattern, content):
            keys.add(match.group(1))

    except Exception as e:
        print(f"Error reading {bib_file}: {e}", file=sys.stderr)

    return keys


def has_significant_changes(old_entry: str, new_entry: str) -> bool:
    """
    Check if new entry has significant changes compared to old entry.

    Compares key fields like title, authors, journal, doi, abstract.
    Ignores whitespace and formatting differences.
    """
    def extract_field(entry: str, field: str) -> str:
        """Extract field value from BibTeX entry."""
        pattern = rf'{field}\s*=\s*{{([^}}]*)}}'
        match = re.search(pattern, entry, re.IGNORECASE | re.DOTALL)
        if match:
            # Normalize whitespace for comparison
            return ' '.join(match.group(1).split())
        return ''

    # Fields to compare
    fields = ['title', 'author', 'journal', 'year', 'volume', 'pages', 'doi', 'abstract']

    for field in fields:
        old_val = extract_field(old_entry, field)
        new_val = extract_field(new_entry, field)

        if old_val != new_val:
            return True

    return False


def update_bibfile_entries(bib_file: str, new_entries: List[str], updated_entries: List[Tuple[str, str]], dry_run: bool = False):
    """
    Update bibliography file with new and updated entries.

    Args:
        bib_file: Path to bibliography file
        new_entries: List of new BibTeX entries to append
        updated_entries: List of (old_entry, new_entry) tuples to replace
        dry_run: If True, only show what would be changed
    """
    if not new_entries and not updated_entries:
        print("No changes to make.")
        return

    if dry_run:
        print(f"\n{'='*80}")
        print("DRY RUN: Would make the following changes:")
        print(f"{'='*80}\n")

        if new_entries:
            print(f"--- NEW ENTRIES ({len(new_entries)}) ---\n")
            for entry in new_entries:
                print(entry)
                print()

        if updated_entries:
            print(f"--- UPDATED ENTRIES ({len(updated_entries)}) ---\n")
            for old_entry, new_entry in updated_entries:
                # Extract keys for display
                old_key = re.search(r'@\w+\s*{\s*([^,\s]+)', old_entry)
                new_key = re.search(r'@\w+\s*{\s*([^,\s]+)', new_entry)
                old_key = old_key.group(1) if old_key else 'unknown'
                new_key = new_key.group(1) if new_key else 'unknown'
                print(f"Update entry: {old_key} -> {new_key}")
                print(f"OLD:\n{old_entry}\n")
                print(f"NEW:\n{new_entry}\n")
                print("-" * 40)
        return

    try:
        # Read current content
        with open(bib_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Replace updated entries
        for old_entry, new_entry in updated_entries:
            # Escape special regex characters in old_entry
            old_entry_escaped = re.escape(old_entry)
            content = re.sub(old_entry_escaped, new_entry, content, count=1)

        # Write updated content
        with open(bib_file, 'w', encoding='utf-8') as f:
            f.write(content)

        # Append new entries
        if new_entries:
            with open(bib_file, 'a', encoding='utf-8') as f:
                f.write('\n\n')
                for i, entry in enumerate(new_entries):
                    if i > 0:
                        f.write('\n\n')
                    f.write(entry)

        if new_entries and updated_entries:
            print(f"\n✓ Successfully added {len(new_entries)} new entries and updated {len(updated_entries)} entries in {bib_file}")
        elif new_entries:
            print(f"\n✓ Successfully added {len(new_entries)} new entries to {bib_file}")
        elif updated_entries:
            print(f"\n✓ Successfully updated {len(updated_entries)} entries in {bib_file}")

    except Exception as e:
        print(f"Error updating {bib_file}: {e}", file=sys.stderr)


def append_to_bibfile(bib_file: str, new_entries: List[str], dry_run: bool = False):
    """Append new BibTeX entries to the bibliography file."""
    update_bibfile_entries(bib_file, new_entries, [], dry_run)


def test_api_connection(email: str, api_key: str = None):
    """Test if PubMed API is accessible."""
    print("Testing PubMed API connection...")

    importer = PubMedImporter(email=email, api_key=api_key)
    pmids = importer.search_pubmed("cancer", retmax=1)

    if pmids:
        print(f"✓ PubMed API is accessible! Found test PMID: {pmids[0]}")
        return True
    else:
        print("✗ PubMed API is not accessible from this environment.")
        print("  This may be due to network restrictions.")
        print("  The script should work on a machine with normal internet access.")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Import publications from PubMed for all group members',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be added without modifying files')
    parser.add_argument('--member', type=str,
                        help='Only import for specific member name')
    parser.add_argument('--since', type=int,
                        help='Only import publications from this year onwards')
    parser.add_argument('--email', type=str, default='bibliography@radboudumc.nl',
                        help='Email for PubMed API (required by NCBI, default: bibliography@radboudumc.nl)')
    parser.add_argument('--api-key', type=str,
                        help='PubMed API key for faster queries')
    parser.add_argument('--max-results', type=int, default=100,
                        help='Maximum results per author (default: 100)')
    parser.add_argument('--active-only', action='store_true',
                        help='Only process active members')
    parser.add_argument('--test', action='store_true',
                        help='Test PubMed API connection and exit')
    parser.add_argument('--rate-limit', type=float,
                        help='Seconds to wait between API requests (default: 1.0 for safe batch processing)')

    args = parser.parse_args()

    # Test mode
    if args.test:
        success = test_api_connection(args.email, args.api_key)
        return 0 if success else 1

    # Determine paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    members_dir = os.path.join(project_root, 'content', 'pages', 'members')
    bib_file = os.path.join(project_root, 'content', 'umcg-anes.bib')

    print(f"PubMed Bibliography Importer")
    print(f"{'='*80}\n")

    # Load existing data
    print("Loading existing bibliography...")
    existing_entries = load_existing_entries(bib_file)
    existing_pmids = load_existing_pmids(bib_file)  # Use correct function to find ALL PMIDs
    existing_keys = load_existing_bibkeys(bib_file)
    print(f"  Found {len(existing_pmids)} existing publications")
    print(f"  Found {len(existing_keys)} existing BibTeX keys")

    # Check for duplicates in existing file
    duplicates_found = sum(1 for entries in existing_entries.values() if len(entries) > 1)
    if duplicates_found > 0:
        total_duplicate_entries = sum(len(entries) - 1 for entries in existing_entries.values() if len(entries) > 1)
        print(f"  WARNING: Found {duplicates_found} PMIDs with duplicates ({total_duplicate_entries} duplicate entries)")
        print(f"  Consider running: python bibliography/cleanup_duplicates.py --dry-run")
    print()

    # Parse members
    print("Parsing member files...")
    all_members = parse_member_files(members_dir)

    # Filter members
    members = all_members
    if args.active_only:
        members = [m for m in members if m.active]
        print(f"  Found {len(all_members)} total members, {len(members)} active")
    else:
        print(f"  Found {len(members)} members")

    if args.member:
        members = [m for m in members if args.member.lower() in m.name.lower()]
        if not members:
            print(f"Error: No member found matching '{args.member}'")
            return 1
        print(f"  Filtering to member: {members[0].name}")

    print()

    # Initialize importer
    importer = PubMedImporter(email=args.email, api_key=args.api_key, rate_limit=args.rate_limit)

    # Show rate limiting info
    print(f"Rate limiting: {importer.rate_limit} seconds between requests")
    print(f"  (This ensures safe operation with {len(members)} members)")
    print()

    # Process each member
    new_entries = []
    updated_entries = []
    total_found = 0
    total_new = 0
    total_updated = 0

    start_time = time.time()

    for idx, member in enumerate(members, 1):
        print(f"[{idx}/{len(members)}] Processing: {member.name}")

        # Collect PMIDs from all search methods for comprehensive coverage
        all_pmids = []

        # Search by ORCID (most reliable)
        if member.orcid:
            orcid_pmids = importer.search_by_orcid(member.orcid, since_year=args.since,
                                                   max_results=args.max_results)
            all_pmids.extend(orcid_pmids)
            if orcid_pmids:
                print(f"  Found {len(orcid_pmids)} via ORCID")

        # Search by pub_name (if different from regular name)
        if member.pub_name and member.pub_name != member.name:
            pub_name_pmids = importer.search_by_author_name(member.pub_name, since_year=args.since,
                                                            max_results=args.max_results)
            all_pmids.extend(pub_name_pmids)
            if pub_name_pmids:
                print(f"  Found {len(pub_name_pmids)} via pub_name '{member.pub_name}'")

            # Also search with initials from pub_name
            pub_name_initial_pmids = importer.search_by_author_initials(member.pub_name, since_year=args.since,
                                                                        max_results=args.max_results)
            all_pmids.extend(pub_name_initial_pmids)
            if pub_name_initial_pmids:
                print(f"  Found {len(pub_name_initial_pmids)} via pub_name initials")

        # Search by regular name
        name_pmids = importer.search_by_author_name(member.name, since_year=args.since,
                                                    max_results=args.max_results)
        all_pmids.extend(name_pmids)
        if name_pmids:
            print(f"  Found {len(name_pmids)} via name '{member.name}'")

        # Also search with initials from regular name (if not already searched via pub_name)
        if not member.pub_name or member.pub_name == member.name:
            name_initial_pmids = importer.search_by_author_initials(member.name, since_year=args.since,
                                                                    max_results=args.max_results)
            all_pmids.extend(name_initial_pmids)
            if name_initial_pmids:
                print(f"  Found {len(name_initial_pmids)} via name initials")

        # Deduplicate PMIDs
        pmids = list(set(all_pmids))
        if len(all_pmids) > len(pmids):
            print(f"  Removed {len(all_pmids) - len(pmids)} duplicates")

        if not pmids:
            print(f"  No publications found\n")
            continue

        print(f"  Found {len(pmids)} publications")

        # Separate new and existing PMIDs
        new_pmids = [pmid for pmid in pmids if pmid not in existing_pmids]
        existing_pmids_to_check = [pmid for pmid in pmids if pmid in existing_pmids]

        if not new_pmids and not existing_pmids_to_check:
            print(f"  No publications to process\n")
            continue

        total_found += len(pmids)

        # Process new publications
        if new_pmids:
            print(f"  {len(new_pmids)} new publications to add")
            publications = importer.fetch_pubmed_details(new_pmids)

            for pub in publications:
                entry = publication_to_bibtex(pub, existing_keys)
                new_entries.append(entry)
                total_new += 1
                # Mark as added to avoid duplicates
                existing_pmids.add(pub['pmid'])

        # Check existing publications for updates
        if existing_pmids_to_check:
            print(f"  Checking {len(existing_pmids_to_check)} existing publications for updates...")
            publications = importer.fetch_pubmed_details(existing_pmids_to_check)

            for pub in publications:
                pmid = pub['pmid']

                # Check if this PMID exists in our existing entries
                if pmid not in existing_entries:
                    print(f"    - Warning: PMID {pmid} not found in existing entries, skipping update check")
                    continue

                # Handle duplicates - use first entry and warn if duplicates exist
                entry_list = existing_entries[pmid]
                if len(entry_list) > 1:
                    print(f"    - Warning: PMID {pmid} has {len(entry_list)} duplicate entries, using first one")
                    print(f"      Keys: {', '.join(e['key'] for e in entry_list)}")

                # Use first entry (in clean files there will be only one)
                old_bib_key = entry_list[0]['key']
                old_entry = entry_list[0]['entry']

                # Create new entry with same key
                # Temporarily add old key to set to use it
                temp_keys = existing_keys.copy()
                temp_keys.discard(old_bib_key)
                # Force the generation to use the old key
                new_entry = publication_to_bibtex(pub, temp_keys)
                # Replace the auto-generated key with the old key
                new_entry = re.sub(r'@(\w+)\s*{\s*([^,\s]+)\s*,',
                                 f'@\\1{{{old_bib_key},',
                                 new_entry, count=1)

                # Check if there are significant changes
                if has_significant_changes(old_entry, new_entry):
                    updated_entries.append((old_entry, new_entry))
                    total_updated += 1
                    print(f"    - Update detected for PMID {pmid} ({old_bib_key})")

        print()

    # Summary
    elapsed_time = time.time() - start_time
    print(f"{'='*80}")
    print(f"Summary:")
    print(f"  Members processed: {len(members)}")
    print(f"  Total publications found: {total_found}")
    print(f"  New publications to add: {total_new}")
    print(f"  Publications to update: {total_updated}")
    print(f"  API requests made: {importer.request_count}")
    print(f"  Time elapsed: {elapsed_time:.1f} seconds")
    if importer.request_count > 0:
        print(f"  Average time per request: {elapsed_time/importer.request_count:.2f} seconds")
    print(f"{'='*80}\n")

    # Update file with new and updated entries
    if new_entries or updated_entries:
        update_bibfile_entries(bib_file, new_entries, updated_entries, dry_run=args.dry_run)

        if not args.dry_run:
            print(f"\nNext steps:")
            print(f"  1. Review the changes in {bib_file}")
            print(f"  2. Run: ./parse_publications.sh")
            print(f"  3. Commit and push the changes")
    else:
        print("No changes to make.")

    return 0


if __name__ == '__main__':
    sys.exit(main())
