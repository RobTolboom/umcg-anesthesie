#!/usr/bin/env python3
"""
Vancouver Citation Style Formatter

This module provides functions to format bibliographic entries according to the Vancouver citation style,
commonly used in medical and biomedical publications.

Vancouver style guidelines:
- Authors: Surname Initials (no periods, no spaces between initials)
- Multiple authors: separated by commas
- Title: Sentence case, no quotes
- Journal: Abbreviated journal name
- Book: City: Publisher; Year
- Book chapter: In: Editor(s), editor(s). Book Title. City: Publisher; Year. p. page-range
"""

from typing import List, Tuple, Dict, Optional


def format_authors_vancouver(authors: List[Tuple[str, str, str, str]], max_authors: int = 6) -> str:
    """
    Format author names in Vancouver style.

    Args:
        authors: List of (first, von, last, jr) tuples
        max_authors: Maximum number of authors to list before using 'et al.' (default: 6)

    Returns:
        Formatted author string: "Surname Initials, Surname Initials, et al."

    Example:
        >>> authors = [("Robert C.", "", "Tolboom", ""), ("John", "", "Smith", "")]
        >>> format_authors_vancouver(authors)
        'Tolboom RC, Smith J'
    """
    if not authors:
        return ""

    formatted_authors = []

    for idx, (first, von, last, jr) in enumerate(authors):
        if idx >= max_authors:
            formatted_authors.append("et al")
            break

        # Extract initials from first name (remove dots and spaces)
        initials = ""
        if first:
            # Remove dots and split by spaces
            parts = first.replace(".", "").split()
            # Take first letter of each part
            initials = "".join([part[0].upper() for part in parts if part])

        # Combine von and last name
        full_last = " ".join(part for part in [von, last] if part).strip()

        # Format: "Surname Initials"
        author_str = full_last
        if initials:
            author_str += " " + initials
        if jr:
            author_str += " " + jr

        formatted_authors.append(author_str)

    return ", ".join(formatted_authors)


def format_editors_vancouver(editors: str) -> str:
    """
    Format editor names for book chapters.

    Args:
        editors: Editor string from BibTeX (e.g., "John Smith and Jane Doe")

    Returns:
        Formatted string: "Smith J, Doe J, editors" or "Smith J, editor" for single editor

    Example:
        >>> format_editors_vancouver("John Smith and Jane Doe")
        'Smith J, Doe J, editors'
    """
    if not editors:
        return ""

    # Split by 'and'
    editor_list = [e.strip() for e in editors.split(" and ")]
    formatted = []

    for editor in editor_list:
        # Simple parsing: assume "FirstName LastName" format
        parts = editor.split()
        if len(parts) >= 2:
            last_name = parts[-1]
            first_initial = parts[0][0].upper() if parts[0] else ""
            formatted.append(f"{last_name} {first_initial}")
        elif len(parts) == 1:
            formatted.append(parts[0])

    editor_string = ", ".join(formatted)
    suffix = "editor" if len(formatted) == 1 else "editors"

    return f"{editor_string}, {suffix}"


def format_article_vancouver(bib_item: Dict) -> str:
    """
    Format journal article in Vancouver style.

    Format: Authors. Title. Journal. Year;Volume(Issue):Pages.

    Example:
        Tolboom RC, Smith J. Title of the article. Journal Name. 2024;15(3):123-45.
    """
    parts = []

    # Authors
    if "author" in bib_item:
        authors = format_authors_vancouver(bib_item["author"])
        if authors:
            parts.append(authors + ".")

    # Title (remove trailing period if present)
    if "title" in bib_item:
        title = bib_item["title"].rstrip(".")
        parts.append(title + ".")

    # Journal name
    if "journal" in bib_item:
        parts.append(bib_item["journal"] + ".")

    # Publication info: Year;Volume(Issue):Pages
    pub_info = []
    if "year" in bib_item:
        pub_info.append(bib_item["year"])

    volume_info = ""
    if "volume" in bib_item:
        volume_info = bib_item["volume"]
        if "number" in bib_item:
            volume_info += f"({bib_item['number']})"

    if volume_info:
        pub_info.append(volume_info)

    if "pages" in bib_item:
        # Vancouver uses abbreviated page ranges: 123-45 instead of 123-145
        pages = bib_item["pages"].replace("--", "-")
        if pub_info:
            pub_info[-1] += f":{pages}"
        else:
            pub_info.append(pages)

    if pub_info:
        parts.append(";".join(pub_info) + ".")

    return " ".join(parts)


def format_book_vancouver(bib_item: Dict) -> str:
    """
    Format book in Vancouver style.

    Format: Authors. Title. City: Publisher; Year.

    Example:
        Tolboom RC, Smith J. Title of Book. Amsterdam: Elsevier; 2024.
    """
    parts = []

    # Authors
    if "author" in bib_item:
        authors = format_authors_vancouver(bib_item["author"])
        if authors:
            parts.append(authors + ".")

    # Title
    if "title" in bib_item:
        title = bib_item["title"].rstrip(".")
        parts.append(title + ".")

    # City: Publisher; Year
    location_pub_year = []
    if "address" in bib_item:
        location_pub_year.append(bib_item["address"])

    if "publisher" in bib_item:
        if location_pub_year:
            location_pub_year[-1] += ": " + bib_item["publisher"]
        else:
            location_pub_year.append(bib_item["publisher"])

    if "year" in bib_item:
        if location_pub_year:
            location_pub_year[-1] += "; " + bib_item["year"]
        else:
            location_pub_year.append(bib_item["year"])

    if location_pub_year:
        parts.append(location_pub_year[0] + ".")

    return " ".join(parts)


def format_incollection_vancouver(bib_item: Dict) -> str:
    """
    Format book chapter in Vancouver style.

    Format: Authors. Chapter title. In: Editors, editor(s). Book Title. City: Publisher; Year. p. pages.

    Example:
        Tolboom RC. Chapter title. In: Smith J, Doe J, editors. Book Title. Amsterdam: Elsevier; 2024. p. 123-45.
    """
    parts = []

    # Authors
    if "author" in bib_item:
        authors = format_authors_vancouver(bib_item["author"])
        if authors:
            parts.append(authors + ".")

    # Chapter title
    if "title" in bib_item:
        title = bib_item["title"].rstrip(".")
        parts.append(title + ".")

    # In: Editors, editor(s). Book Title.
    in_part = "In:"

    # Editors
    if "editor" in bib_item:
        editors = format_editors_vancouver(bib_item["editor"])
        if editors:
            in_part += " " + editors + "."

    # Book title
    if "booktitle" in bib_item:
        booktitle = bib_item["booktitle"].rstrip(".")
        in_part += " " + booktitle + "."

    parts.append(in_part)

    # City: Publisher; Year
    location_pub_year = []
    if "address" in bib_item:
        location_pub_year.append(bib_item["address"])

    if "publisher" in bib_item:
        if location_pub_year:
            location_pub_year[-1] += ": " + bib_item["publisher"]
        else:
            location_pub_year.append(bib_item["publisher"])

    if "year" in bib_item:
        if location_pub_year:
            location_pub_year[-1] += "; " + bib_item["year"]
        else:
            location_pub_year.append(bib_item["year"])

    if location_pub_year:
        parts.append(location_pub_year[0] + ".")

    # Pages
    if "pages" in bib_item:
        pages = bib_item["pages"].replace("--", "-")
        parts.append(f"p. {pages}.")

    return " ".join(parts)


def format_thesis_vancouver(bib_item: Dict) -> str:
    """
    Format thesis/dissertation in Vancouver style.

    Format: Author. Title [dissertation/thesis]. City: University; Year.

    Example:
        Tolboom RC. Title of thesis [dissertation]. Groningen: University of Groningen; 2024.
    """
    parts = []

    # Author (singular)
    if "author" in bib_item:
        authors = format_authors_vancouver(bib_item["author"], max_authors=1)
        if authors:
            parts.append(authors + ".")

    # Title [type]
    if "title" in bib_item:
        title = bib_item["title"].rstrip(".")

        # Determine thesis type
        thesis_type = "dissertation"
        if "type" in bib_item:
            bib_type = bib_item["type"].lower()
            if "master" in bib_type:
                thesis_type = "thesis"

        parts.append(f"{title} [{thesis_type}].")

    # City: University; Year
    location_inst_year = []
    if "address" in bib_item:
        location_inst_year.append(bib_item["address"])

    if "school" in bib_item:
        if location_inst_year:
            location_inst_year[-1] += ": " + bib_item["school"]
        else:
            location_inst_year.append(bib_item["school"])

    if "year" in bib_item:
        if location_inst_year:
            location_inst_year[-1] += "; " + bib_item["year"]
        else:
            location_inst_year.append(bib_item["year"])

    if location_inst_year:
        parts.append(location_inst_year[0] + ".")

    return " ".join(parts)


def format_vancouver(bib_item: Dict) -> str:
    """
    Main function to format a bibliographic entry in Vancouver style.

    Dispatches to the appropriate formatter based on entry type.

    Args:
        bib_item: Dictionary containing bibliographic data

    Returns:
        Formatted citation string in Vancouver style
    """
    if not isinstance(bib_item, dict):
        return ""

    entry_type = bib_item.get("type", "").lower()

    if entry_type == "article":
        return format_article_vancouver(bib_item)
    elif entry_type == "book":
        return format_book_vancouver(bib_item)
    elif entry_type == "incollection":
        return format_incollection_vancouver(bib_item)
    elif entry_type in ["phdthesis", "mastersthesis"]:
        return format_thesis_vancouver(bib_item)
    else:
        # Fallback: use article formatting for unknown types
        return format_article_vancouver(bib_item)


# For testing
if __name__ == "__main__":
    # Test article
    article = {
        "type": "article",
        "author": [("Robert C.", "", "Tolboom", ""), ("John", "", "Smith", "")],
        "title": "Title of the article",
        "journal": "Journal Name",
        "year": "2024",
        "volume": "15",
        "number": "3",
        "pages": "123--145"
    }
    print("Article:", format_vancouver(article))

    # Test book
    book = {
        "type": "book",
        "author": [("Robert C.", "", "Tolboom", "")],
        "title": "Title of Book",
        "address": "Amsterdam",
        "publisher": "Elsevier",
        "year": "2024"
    }
    print("Book:", format_vancouver(book))

    # Test book chapter
    chapter = {
        "type": "incollection",
        "author": [("Robert C.", "", "Tolboom", "")],
        "title": "Chapter title",
        "editor": "John Smith and Jane Doe",
        "booktitle": "Book Title",
        "address": "Amsterdam",
        "publisher": "Elsevier",
        "year": "2024",
        "pages": "123--145"
    }
    print("Chapter:", format_vancouver(chapter))
