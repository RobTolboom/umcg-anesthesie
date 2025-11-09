import json
import time
import latexcodec
import codecs
import glob
import os
import numpy as np
import sys

from mdfiles import create_author_md_files, create_publication_md, create_group_md_files
from authors import get_list_researchers, get_publications_by_author
from bibreader import parse_bibtex_file
from vancouver_formatter import format_vancouver


class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


def save_dict2json(json_path, dict_md5):
    with open(json_path, "w") as fp:
        json.dump(dict_md5, fp, cls=SetEncoder, ensure_ascii=False, sort_keys=False)


def load_json2dict(json_path):
    if os.path.exists(json_path):
        json_file = open(json_path)
        json_data = json.load(json_file)
    else:
        json_data = None
    return json_data


def timeit(method):
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        if "log_time" in kw:
            name = kw.get("log_name", method.__name__.upper())
            kw["log_time"][name] = int((te - ts) * 1000)
        else:
            print("%r ran for  %2.2f ms" % (method.__name__, (te - ts) * 1000))
        return result

    return timed


def sort_bib_keys_author(author_bib_keys, bib_items):
    _types = [
        "article",
        "preprint",
        "inproceedings",
        "conference",
        "phdthesis",
        "mastersthesis",
        "book",
        "incollection",
        "other",
    ]

    # Month name to number mapping
    month_map = {
        "january": 1, "jan": 1,
        "february": 2, "feb": 2,
        "march": 3, "mar": 3,
        "april": 4, "apr": 4,
        "may": 5,
        "june": 6, "jun": 6,
        "july": 7, "jul": 7,
        "august": 8, "aug": 8,
        "september": 9, "sep": 9,
        "october": 10, "oct": 10,
        "november": 11, "nov": 11,
        "december": 12, "dec": 12
    }

    def get_sort_key(item):
        """Generate sort key: (year DESC, month DESC, pmid DESC)"""
        year = bib_items[item].get("year", 0)
        month = bib_items[item].get("month", 0)

        # Convert month to integer if it's a string
        if isinstance(month, str):
            month = month_map.get(month.lower(), 0)
        else:
            month = int(month) if month else 0

        pmid = bib_items[item]["pmidnumber"]

        # Return tuple for sorting (negative for descending order)
        return (-int(year) if year else 0, -month, -pmid)

    bib_items_per_author_per_date = {}
    for researcher, keys in author_bib_keys.items():
        keys = set(keys)
        # Sort by year (desc), month (desc), then pmid (desc)
        keys = sorted(keys, key=get_sort_key)
        bib_items_per_data = {}
        for key in keys:
            bib_items_per_data.setdefault(bib_items[key]["year"], []).append(key)
            bib_items_per_data.setdefault("__types__", set()).add(
                bib_items[key]["type"]
            )
        bib_items_per_data["__years__"] = sorted(
            set([y for y in bib_items_per_data.keys() if isinstance(y, int)])
        )[::-1]
        bib_items_per_data["__types__"] = [
            t for t in _types if t in bib_items_per_data["__types__"]
        ]

        bib_items_per_author_per_date[researcher] = bib_items_per_data
    return bib_items_per_author_per_date


def sort_bib_keys_group(author_bib_keys, bib_items, list_researchers, bibfile, include_all_publications=True):
    _types = [
        "article",
        "preprint",
        "inproceedings",
        "conference",
        "phdthesis",
        "mastersthesis",
        "book",
        "incollection",
        "other",
    ]
    bib_items_per_group_per_date = {}
    groups = []
    publication_types = set()
    group_keys = {}

    # First, collect publications from researchers (member-authored publications)
    for researcher, keys in author_bib_keys.items():
        # set group if not set
        for group in list_researchers[researcher][1]:
            if group not in groups:
                groups.append(group)
            bib_items_per_group_per_date.setdefault(group, {})
            group_keys.setdefault(group, set()).update(keys)

    # If include_all_publications is True, add ALL publications to the appropriate groups
    if include_all_publications:
        # Determine which groups should get all publications based on bibfile
        target_groups = []
        if bibfile == 'cara':
            target_groups = [g for g in groups if g == 'cara-lab']
        else:  # diag
            target_groups = [g for g in groups if g != 'cara-lab']

        # If no target groups found, use a default based on bibfile
        if not target_groups:
            if bibfile == 'cara':
                target_groups = ['cara-lab']
            else:
                target_groups = ['anes']  # Only anes website is active

        # Add all publications to target groups
        for group in target_groups:
            if group not in groups:
                groups.append(group)
            bib_items_per_group_per_date.setdefault(group, {})
            group_keys.setdefault(group, set())
            # Add all publication keys
            for bib_key in bib_items.keys():
                group_keys[group].add(bib_key)

    # Month name to number mapping (same as in sort_bib_keys_author)
    month_map = {
        "january": 1, "jan": 1,
        "february": 2, "feb": 2,
        "march": 3, "mar": 3,
        "april": 4, "apr": 4,
        "may": 5,
        "june": 6, "jun": 6,
        "july": 7, "jul": 7,
        "august": 8, "aug": 8,
        "september": 9, "sep": 9,
        "october": 10, "oct": 10,
        "november": 11, "nov": 11,
        "december": 12, "dec": 12
    }

    def get_sort_key(item):
        """Generate sort key: (year DESC, month DESC, pmid DESC)"""
        year = bib_items[item].get("year", 0)
        month = bib_items[item].get("month", 0)

        # Convert month to integer if it's a string
        if isinstance(month, str):
            month = month_map.get(month.lower(), 0)
        else:
            month = int(month) if month else 0

        pmid = bib_items[item]["pmidnumber"]

        # Return tuple for sorting (negative for descending order)
        return (-int(year) if year else 0, -month, -pmid)

    # compute all years per group
    for group in groups:
        if (group == 'cara-lab' and bibfile == 'cara') or (group != 'cara-lab'):
            # Sort by year (desc), month (desc), then pmid (desc)
            group_keys_sorted = sorted(group_keys[group], key=get_sort_key)

            for key in group_keys_sorted:
                bib_items_per_group_per_date[group].setdefault(
                    bib_items[key]["year"], []
                ).append(key)
                bib_items_per_group_per_date[group].setdefault("__types__", []).append(
                    bib_items[key]["type"]
                )

            bib_items_per_group_per_date[group]["__years__"] = sorted(
                set(
                    [
                        y
                        for y in bib_items_per_group_per_date[group].keys()
                        if isinstance(y, int)
                    ]
                )
            )[::-1]
            bib_items_per_group_per_date[group]["__types__"] = [
                t for t in _types if t in bib_items_per_group_per_date[group]["__types__"]
            ]
    return bib_items_per_group_per_date


@timeit
def parse_bib_file():
    print("parsing bib file...")
    bib_items = parse_bibtex_file("./content/{}.bib".format(sys.argv[1]), "./content/fullstrings.bib")

    # Add Vancouver formatted citations
    print("formatting citations in Vancouver style...")
    for bib_key, bib_item in bib_items.items():
        bib_item['vancouver_citation'] = format_vancouver(bib_item)

    print("retreiving list of diag members")
    list_researchers = get_list_researchers("./content/pages/members/")
    print("mapping bib keys to authors")
    author_bib_keys = get_publications_by_author(bib_items, list_researchers)

    # sorting
    print("sorting...")
    bib_items_per_author_per_date = sort_bib_keys_author(author_bib_keys, bib_items)
    bib_items_per_group_per_date = sort_bib_keys_group(
        author_bib_keys, bib_items, list_researchers, sys.argv[1]
    )

    # saving
    print("saving bibitems.json")
    save_dict2json("./content/bibitems_{}.json".format(sys.argv[1]), bib_items)
    print("saving authorbibkeys.json")
    save_dict2json("./content/authorkeys_{}.json".format(sys.argv[1]), bib_items_per_author_per_date)
    print("saving groupbibkeys.json")
    save_dict2json("./content/groupkeys_{}.json".format(sys.argv[1]), bib_items_per_group_per_date)

    return (
        bib_items,
        list_researchers,
        bib_items_per_author_per_date,
        bib_items_per_group_per_date,
    )


if __name__ == "__main__":
    (
        bib_items,
        list_researchers,
        bib_items_per_author_per_date,
        bib_items_per_group_per_date,
    ) = parse_bib_file()

    print("creating author md files")
    create_author_md_files(sys.argv[1], bib_items_per_author_per_date, list_researchers)

    print("creating group md files")
    create_group_md_files(bib_items, bib_items_per_group_per_date)

    print("creating publication md files")
    create_publication_md(sys.argv[1], bib_items, bib_items_per_author_per_date, list_researchers)
