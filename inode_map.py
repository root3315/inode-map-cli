#!/usr/bin/env python3
"""CLI tool to scan directories and map file inodes to paths."""

import argparse
import json
import os
import stat
import sys
from collections import defaultdict
from pathlib import Path


def scan_directory(root_path, follow_links=False, max_depth=None):
    """Walk the directory tree and collect inode information for each file.

    Returns a dict mapping inode number to a list of absolute paths.
    """
    root = Path(root_path).resolve()
    if not root.is_dir():
        print(f"Error: '{root_path}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    inode_map = defaultdict(list)
    root_depth = root.parts.__len__()

    walker = os.walk if not follow_links else os.walk
    if follow_links:
        walker = os.walk

    for dirpath, dirnames, filenames in walker(str(root), followlinks=follow_links):
        current_depth = Path(dirpath).resolve().parts.__len__() - root_depth
        if max_depth is not None and current_depth >= max_depth:
            dirnames.clear()
            continue

        for entry_name in filenames:
            full_path = os.path.join(dirpath, entry_name)
            try:
                st = os.lstat(full_path)
            except (PermissionError, OSError):
                continue

            if stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode):
                inode_map[st.st_ino].append(os.path.abspath(full_path))

        for entry_name in dirnames:
            full_path = os.path.join(dirpath, entry_name)
            try:
                st = os.lstat(full_path)
            except (PermissionError, OSError):
                continue

            if stat.S_ISDIR(st.st_mode):
                pass

    return dict(inode_map)


def find_hardlinks(inode_map):
    """Return only entries where multiple paths share the same inode."""
    return {ino: paths for ino, paths in inode_map.items() if len(paths) > 1}


def format_tree(inode_map, show_all=True):
    """Format the inode map as a human-readable tree string."""
    lines = []
    sorted_inodes = sorted(inode_map.keys())

    for ino in sorted_inodes:
        paths = inode_map[ino]
        if not show_all and len(paths) < 2:
            continue

        if len(paths) > 1:
            lines.append(f"Inode {ino} [{len(paths)} paths] (hardlink)")
        else:
            lines.append(f"Inode {ino}")

        for i, path in enumerate(sorted(paths)):
            prefix = "    " + ("├── " if i < len(paths) - 1 else "└── ")
            lines.append(f"{prefix}{path}")

    return "\n".join(lines)


def compute_stats(inode_map):
    """Compute summary statistics about the scan results."""
    total_files = sum(len(paths) for paths in inode_map.values())
    total_inodes = len(inode_map)
    hardlinked_inodes = sum(1 for paths in inode_map.values() if len(paths) > 1)
    hardlinked_files = sum(len(paths) for paths in inode_map.values() if len(paths) > 1)

    return {
        "total_files": total_files,
        "total_inodes": total_inodes,
        "hardlinked_inodes": hardlinked_inodes,
        "hardlinked_files": hardlinked_files,
        "unique_files": total_files - hardlinked_files + hardlinked_inodes,
    }


def format_json(inode_map, include_stats=True):
    """Serialize the inode map to a JSON string."""
    output = {}
    for ino, paths in sorted(inode_map.items()):
        output[str(ino)] = sorted(paths)

    if include_stats:
        output["_stats"] = compute_stats(inode_map)

    return json.dumps(output, indent=2)


def main():
    parser = argparse.ArgumentParser(
        prog="inode-map",
        description="Scan directories and map file inodes to paths.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory to scan (default: current directory)",
    )
    parser.add_argument(
        "-f", "--follow-links",
        action="store_true",
        help="Follow symbolic links",
    )
    parser.add_argument(
        "-d", "--max-depth",
        type=int,
        default=None,
        help="Maximum directory depth to scan",
    )
    parser.add_argument(
        "--hardlinks-only",
        action="store_true",
        help="Show only files with multiple paths (hardlinks)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print summary statistics after scanning",
    )

    args = parser.parse_args()

    inode_map = scan_directory(
        args.path,
        follow_links=args.follow_links,
        max_depth=args.max_depth,
    )

    if args.hardlinks_only:
        inode_map = find_hardlinks(inode_map)

    if args.as_json:
        print(format_json(inode_map, include_stats=False))
    else:
        output = format_tree(inode_map, show_all=not args.hardlinks_only)
        if output:
            print(output)
        else:
            print("No files found.")

    if args.stats:
        stats = compute_stats(inode_map)
        print()
        print("=== Scan Statistics ===")
        print(f"  Total files scanned : {stats['total_files']}")
        print(f"  Unique inodes       : {stats['total_inodes']}")
        print(f"  Hardlinked inodes   : {stats['hardlinked_inodes']}")
        print(f"  Hardlinked paths    : {stats['hardlinked_files']}")
        print(f"  Effective unique    : {stats['unique_files']}")


if __name__ == "__main__":
    main()
