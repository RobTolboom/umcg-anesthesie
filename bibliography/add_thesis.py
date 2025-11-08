#!/usr/bin/env python3
"""
Add PhD Thesis to Bibliography

This script adds a new PhD thesis entry to the umcg-anes.bib file.
It generates a BibTeX key, saves the cover image, and creates a properly formatted entry.

Usage:
    python add_thesis.py --author "Thiago Ramos Grigio" --title "..." --year 2024 \
        --school "..." --promotor "..." --url "..." --abstract "..." --cover-image cover.png
"""

import os
import sys
import re
import argparse
import subprocess
from typing import Set, Optional


def get_author_full_name(member_slug: str, members_dir: str) -> str:
    """Extract full name from member markdown file.

    Prefers pub_name over name for consistent publication matching.
    """
    member_file = os.path.join(members_dir, f"{member_slug}.md")

    if not os.path.exists(member_file):
        raise ValueError(f"Member file not found: {member_file}")

    try:
        with open(member_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract pub_name field (preferred for publications)
        pub_name_match = re.search(r'^pub_name:\s*(.+)$', content, re.MULTILINE)
        if pub_name_match:
            return pub_name_match.group(1).strip()

        # Fallback to name field
        name_match = re.search(r'^name:\s*(.+)$', content, re.MULTILINE)
        if not name_match:
            raise ValueError(f"No 'name' or 'pub_name' field found in {member_file}")

        return name_match.group(1).strip()

    except Exception as e:
        raise ValueError(f"Error reading member file: {e}")


def load_existing_bibkeys(bib_file: str) -> Set[str]:
    """Load all existing BibTeX keys from the .bib file."""
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


def generate_bibkey(author_name: str, year: str, existing_keys: Set[str]) -> str:
    """
    Generate a unique BibTeX key from author name and year.

    Format: LastnameYYYY (e.g., "Grigio2024")
    Adds suffix (a, b, c, ...) if key already exists.
    """
    # Extract lastname
    parts = author_name.strip().split()
    if not parts:
        raise ValueError("Author name is empty")

    lastname = parts[-1]

    # Remove non-alphanumeric characters
    lastname = re.sub(r'[^a-zA-Z]', '', lastname)

    if not lastname:
        raise ValueError(f"Could not extract valid lastname from '{author_name}'")

    # Base key: LastnameYear
    base_key = lastname + str(year)

    # Check if key exists
    if base_key not in existing_keys:
        return base_key

    # Add suffix
    for suffix in 'abcdefghijklmnopqrstuvwxyz':
        candidate = base_key + suffix
        if candidate not in existing_keys:
            print(f"Note: {base_key} already exists, using {candidate}", file=sys.stderr)
            return candidate

    raise ValueError(f"Too many theses for {author_name} in {year}")


def create_bibtex_entry(bibkey: str, author: str, title: str, school: str, year: str,
                       promotor: str, url: str, abstract: str,
                       copromotor: Optional[str] = None, month: Optional[int] = None) -> str:
    """Create a properly formatted BibTeX entry for a PhD thesis."""

    # Build entry
    lines = [f"@phdthesis{{{bibkey},"]

    # Author
    lines.append(f"  author = {{{author}}},")

    # Title (remove trailing period if present)
    title_clean = title.rstrip('.')
    lines.append(f"  title = {{{title_clean}}},")

    # School
    lines.append(f"  school = {{{school}}},")

    # Year
    lines.append(f"  year = {{{year}}},")

    # Promotor
    lines.append(f"  promotor = {{{promotor}}},")

    # Co-promotor (optional)
    if copromotor:
        lines.append(f"  copromotor = {{{copromotor}}},")

    # Month (optional)
    if month:
        lines.append(f"  optmonth = {{{month}}},")

    # URL
    lines.append(f"  url = {{{url}}},")

    # Abstract - escape special characters
    abstract_clean = abstract.replace('{', '\\{').replace('}', '\\}')
    lines.append(f"  abstract = {{{abstract_clean}}},")

    # Fixed fields
    lines.append(f"  journal = {{PhD thesis}},")

    lines.append("}")

    return '\n'.join(lines)


def add_entry_to_bibfile(bib_file: str, new_entry: str, bibkey: str):
    """Add a new entry to the .bib file in alphabetical order by key."""

    if not os.path.exists(bib_file):
        # File doesn't exist, create it
        with open(bib_file, 'w', encoding='utf-8') as f:
            f.write(new_entry + '\n')
        print(f"✓ Created {bib_file} with new entry")
        return

    try:
        with open(bib_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find all entries with their positions
        entry_pattern = r'(?:^|\n)(@\w+\s*{)'
        entry_starts = [(m.start(), m.group(0)) for m in re.finditer(entry_pattern, content, re.MULTILINE)]

        # Extract entries with their keys
        entries = []
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

            # Skip @string and @preamble entries
            if entry_text.lower().startswith('@string') or entry_text.lower().startswith('@preamble'):
                continue

            # Extract key
            key_match = re.search(r'@(\w+)\s*{\s*([^,\s]+)\s*,', entry_text)
            if key_match:
                key = key_match.group(2)
                entries.append((key, entry_text))

        # Add new entry
        entries.append((bibkey, new_entry))

        # Sort by key (case-insensitive)
        entries.sort(key=lambda x: x[0].lower())

        # Find preamble/string section (everything before first @article/@phdthesis/@etc)
        first_entry_pos = entry_starts[0][0] if entry_starts else 0
        if first_entry_pos > 0 and content[first_entry_pos] == '\n':
            first_entry_pos += 1

        preamble = content[:first_entry_pos].rstrip()

        # Rebuild file
        new_content = preamble
        if preamble:
            new_content += '\n\n'

        for i, (key, entry_text) in enumerate(entries):
            if i > 0:
                new_content += '\n\n'
            new_content += entry_text

        new_content += '\n'

        # Write back
        with open(bib_file, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"✓ Added entry to {bib_file} (sorted alphabetically)")

    except Exception as e:
        print(f"Error updating {bib_file}: {e}", file=sys.stderr)
        sys.exit(1)


def save_cover_image(source_path: str, bibkey: str, images_dir: str) -> str:
    """Save cover image to content/images/theses/ with proper naming."""

    if not os.path.exists(images_dir):
        os.makedirs(images_dir, exist_ok=True)
        print(f"✓ Created directory: {images_dir}")

    # Determine target filename
    target_filename = bibkey[0].upper() + bibkey[1:] + '.png'
    target_path = os.path.join(images_dir, target_filename)

    # Copy file
    try:
        import shutil
        shutil.copy2(source_path, target_path)
        print(f"✓ Saved cover image: {target_path}")
        return target_path
    except Exception as e:
        print(f"Error saving cover image: {e}", file=sys.stderr)
        sys.exit(1)


def crop_thesis_cover(project_root: str):
    """Run crop_thesis_covers.py to normalize aspect ratio."""
    crop_script = os.path.join(project_root, 'crop_thesis_covers.py')

    if not os.path.exists(crop_script):
        print(f"Warning: {crop_script} not found, skipping crop step", file=sys.stderr)
        return

    try:
        subprocess.run(['python3', crop_script], cwd=project_root, check=True)
        print(f"✓ Cropped thesis covers to standard aspect ratio")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Error running crop script: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Could not run crop script: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description='Add a PhD thesis to the bibliography',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('--member', type=str,
                       help='Member slug (e.g., rob-tolboom)')
    parser.add_argument('--author', type=str,
                       help='Full author name (overrides --member)')
    parser.add_argument('--title', type=str, required=True,
                       help='Thesis title')
    parser.add_argument('--year', type=int, required=True,
                       help='Year of thesis')
    parser.add_argument('--month', type=int,
                       help='Month (1-12, optional)')
    parser.add_argument('--school', type=str, required=True,
                       help='University/School')
    parser.add_argument('--promotor', type=str, required=True,
                       help='Promotor name(s)')
    parser.add_argument('--copromotor', type=str,
                       help='Co-promotor name(s) (optional)')
    parser.add_argument('--url', type=str, required=True,
                       help='URL to thesis (e.g., institutional repository)')
    parser.add_argument('--abstract', type=str, required=True,
                       help='Thesis abstract')
    parser.add_argument('--cover-image', type=str, required=True,
                       help='Path to cover image (PNG/JPG)')

    args = parser.parse_args()

    # Determine paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    members_dir = os.path.join(project_root, 'content', 'pages', 'members')
    bib_file = os.path.join(project_root, 'content', 'umcg-anes.bib')
    images_dir = os.path.join(project_root, 'content', 'images', 'theses')

    print(f"Adding PhD Thesis")
    print(f"{'='*80}\n")

    # Get author name
    if args.member:
        author_name = get_author_full_name(args.member, members_dir)
        print(f"Author (from member '{args.member}'): {author_name}")
    elif args.author:
        author_name = args.author
        print(f"Author: {author_name}")
    else:
        print("Error: Either --member or --author must be specified", file=sys.stderr)
        return 1

    # Validate inputs
    if args.year < 1900 or args.year > 2100:
        print(f"Error: Year {args.year} seems invalid", file=sys.stderr)
        return 1

    if args.month and (args.month < 1 or args.month > 12):
        print(f"Error: Month must be between 1 and 12", file=sys.stderr)
        return 1

    if not os.path.exists(args.cover_image):
        print(f"Error: Cover image not found: {args.cover_image}", file=sys.stderr)
        return 1

    if len(args.abstract) < 50:
        print(f"Warning: Abstract is very short ({len(args.abstract)} chars)", file=sys.stderr)

    # Load existing keys
    existing_keys = load_existing_bibkeys(bib_file)
    print(f"Found {len(existing_keys)} existing entries")

    # Generate bibkey
    bibkey = generate_bibkey(author_name, str(args.year), existing_keys)
    print(f"Generated BibTeX key: {bibkey}")
    print()

    # Create BibTeX entry
    entry = create_bibtex_entry(
        bibkey=bibkey,
        author=author_name,
        title=args.title,
        school=args.school,
        year=str(args.year),
        promotor=args.promotor,
        url=args.url,
        abstract=args.abstract,
        copromotor=args.copromotor,
        month=args.month
    )

    # Save cover image
    save_cover_image(args.cover_image, bibkey, images_dir)

    # Add entry to .bib file
    add_entry_to_bibfile(bib_file, entry, bibkey)

    # Crop covers
    crop_thesis_cover(project_root)

    print()
    print("=" * 80)
    print("✓ Successfully added PhD thesis")
    print(f"  BibTeX key: {bibkey}")
    print(f"  Author: {author_name}")
    print(f"  Title: {args.title[:60]}...")
    print(f"  Year: {args.year}")
    print("=" * 80)

    return 0


if __name__ == '__main__':
    sys.exit(main())
