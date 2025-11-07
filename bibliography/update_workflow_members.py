#!/usr/bin/env python3
"""
Update Workflow Member List

This script automatically updates the member dropdown in the exclude-publication.yml
workflow file based on the members found in content/pages/members/.

Usage:
    python update_workflow_members.py
"""

import os
import sys
import re
from typing import List


def get_all_members(members_dir: str) -> List[str]:
    """Get all member slugs from the members directory."""
    if not os.path.exists(members_dir):
        print(f"Error: Members directory not found: {members_dir}", file=sys.stderr)
        return []

    members = []
    for filename in sorted(os.listdir(members_dir)):
        if filename.endswith('.md') and not filename.startswith('.'):
            member_slug = filename.replace('.md', '')
            members.append(member_slug)

    return members


def update_workflow_file(workflow_file: str, members: List[str]) -> bool:
    """Update the workflow file with the current member list."""
    if not os.path.exists(workflow_file):
        print(f"Error: Workflow file not found: {workflow_file}", file=sys.stderr)
        return False

    try:
        with open(workflow_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find the member input section and update the options
        # Pattern matches the member input with its options array (block-style YAML)
        pattern = r'(member:\s+description:.*?\n\s+required:.*?\n\s+type:\s+choice\s+options:\n)((?:\s+- [^\n]+\n)+)'

        # Build new options array (block-style YAML)
        options_array = ''
        for member in members:
            options_array += f'          - {member}\n'

        # Replace in content
        new_content = re.sub(pattern, r'\1' + options_array, content, flags=re.MULTILINE)

        # Check if anything changed
        if new_content == content:
            print("No changes needed - member list is up to date")
            return False

        # Write back
        with open(workflow_file, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"✓ Updated {workflow_file} with {len(members)} members")
        return True

    except Exception as e:
        print(f"Error updating workflow file: {e}", file=sys.stderr)
        return False


def main():
    # Determine paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    members_dir = os.path.join(project_root, 'content', 'pages', 'members')
    workflow_file = os.path.join(project_root, '.github', 'workflows', 'exclude-publication.yml')

    print("Updating workflow member list...")
    print(f"Members directory: {members_dir}")
    print(f"Workflow file: {workflow_file}")
    print()

    # Get all members
    members = get_all_members(members_dir)
    if not members:
        print("Error: No members found", file=sys.stderr)
        return 1

    print(f"Found {len(members)} members")

    # Update workflow file
    changed = update_workflow_file(workflow_file, members)

    if changed:
        print()
        print("=" * 80)
        print("✓ Workflow file updated successfully")
        print(f"  Total members: {len(members)}")
        print("=" * 80)
        return 0
    else:
        return 0


if __name__ == '__main__':
    sys.exit(main())
