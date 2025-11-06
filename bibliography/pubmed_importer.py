#!/usr/bin/env python3
"""
PubMed Bibliography Importer

This script automatically imports publications from PubMed for all group members
and adds them to the diag.bib file.

Features:
- Reads member information from content/pages/members/*.md files
- Queries PubMed using ORCID IDs and/or author names
- Converts PubMed XML to BibTeX format
- Detects and avoids duplicates
- Merges new entries into diag.bib

Usage:
    python pubmed_importer.py [options]

Options:
    --dry-run       : Show what would be added without modifying diag.bib
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

    def __init__(self, email: str = None, api_key: str = None, rate_limit: float = 0.34):
        """
        Initialize PubMed importer.

        Args:
            email: Email for PubMed API (required by NCBI)
            api_key: PubMed API key for faster queries
            rate_limit: Seconds to wait between requests (0.34 = ~3 req/sec)
        """
        self.email = email or "pubmed@example.com"  # Default email if none provided
        self.api_key = api_key
        self.rate_limit = rate_limit if not api_key else 0.1  # 10 req/sec with API key
        self.last_request = 0

    def _rate_limit_wait(self):
        """Wait to respect rate limits."""
        elapsed = time.time() - self.last_request
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request = time.time()

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

        try:
            with urllib.request.urlopen(url, timeout=30) as response:
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

        try:
            with urllib.request.urlopen(url, timeout=60) as response:
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

    def search_by_author_name(self, name: str, since_year: int = None, max_results: int = 100) -> List[str]:
        """Search PubMed by author name."""
        # Simple name formatting: "Lastname Firstname[au]"
        query = f'"{name}"[Author]'

        mindate = f"{since_year}/01/01" if since_year else None

        print(f"  Searching PubMed with name: {name}")
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


def load_existing_pmids(bib_file: str) -> Set[str]:
    """Load all PMIDs that already exist in the BibTeX file."""
    pmids = set()

    if not os.path.exists(bib_file):
        return pmids

    try:
        with open(bib_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find all pmid entries
        pmid_pattern = r'pmid\s*=\s*[{\"]?(\d+)[}\"]?'
        for match in re.finditer(pmid_pattern, content, re.IGNORECASE):
            pmids.add(match.group(1))

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


def append_to_bibfile(bib_file: str, new_entries: List[str], dry_run: bool = False):
    """Append new BibTeX entries to the bibliography file."""
    if not new_entries:
        print("No new entries to add.")
        return

    if dry_run:
        print(f"\n{'='*80}")
        print("DRY RUN: Would add the following entries:")
        print(f"{'='*80}\n")
        for entry in new_entries:
            print(entry)
            print()
        return

    try:
        with open(bib_file, 'a', encoding='utf-8') as f:
            f.write('\n\n')
            for i, entry in enumerate(new_entries):
                if i > 0:
                    f.write('\n\n')
                f.write(entry)

        print(f"\n✓ Successfully added {len(new_entries)} new entries to {bib_file}")

    except Exception as e:
        print(f"Error writing to {bib_file}: {e}", file=sys.stderr)


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

    args = parser.parse_args()

    # Determine paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    members_dir = os.path.join(project_root, 'content', 'pages', 'members')
    bib_file = os.path.join(project_root, 'content', 'diag.bib')

    print(f"PubMed Bibliography Importer")
    print(f"{'='*80}\n")

    # Load existing data
    print("Loading existing bibliography...")
    existing_pmids = load_existing_pmids(bib_file)
    existing_keys = load_existing_bibkeys(bib_file)
    print(f"  Found {len(existing_pmids)} existing publications")
    print(f"  Found {len(existing_keys)} existing BibTeX keys\n")

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
    importer = PubMedImporter(email=args.email, api_key=args.api_key)

    # Process each member
    new_entries = []
    total_found = 0
    total_new = 0

    for member in members:
        print(f"Processing: {member.name}")

        pmids = []

        # Try ORCID first (more reliable)
        if member.orcid:
            pmids = importer.search_by_orcid(member.orcid, since_year=args.since,
                                            max_results=args.max_results)

        # Fall back to name search if no ORCID or no results
        if not pmids:
            search_name = member.pub_name or member.name
            pmids = importer.search_by_author_name(search_name, since_year=args.since,
                                                  max_results=args.max_results)

        if not pmids:
            print(f"  No publications found\n")
            continue

        print(f"  Found {len(pmids)} publications")

        # Filter out existing
        new_pmids = [pmid for pmid in pmids if pmid not in existing_pmids]

        if not new_pmids:
            print(f"  All publications already in database\n")
            continue

        print(f"  {len(new_pmids)} new publications to add")
        total_found += len(pmids)
        total_new += len(new_pmids)

        # Fetch details
        publications = importer.fetch_pubmed_details(new_pmids)

        # Convert to BibTeX
        for pub in publications:
            entry = publication_to_bibtex(pub, existing_keys)
            new_entries.append(entry)
            # Mark as added to avoid duplicates
            existing_pmids.add(pub['pmid'])

        print()

    # Summary
    print(f"{'='*80}")
    print(f"Summary:")
    print(f"  Total publications found: {total_found}")
    print(f"  New publications to add: {total_new}")
    print(f"{'='*80}\n")

    # Append to file
    if new_entries:
        append_to_bibfile(bib_file, new_entries, dry_run=args.dry_run)

        if not args.dry_run:
            print(f"\nNext steps:")
            print(f"  1. Review the new entries in {bib_file}")
            print(f"  2. Run: ./parse_publications.sh")
            print(f"  3. Commit and push the changes")
    else:
        print("No new publications to add.")

    return 0


if __name__ == '__main__':
    sys.exit(main())
