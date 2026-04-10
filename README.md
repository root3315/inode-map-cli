# inode-map-cli

CLI tool to scan directories and map file inodes to paths. Handy when you need to find hardlinks, deduplicate files, or just understand what's sharing inodes in a tree.

## Quick start

```bash
python3 inode_map.py /some/path
python3 inode_map.py /some/path --hardlinks-only
python3 inode_map.py /some/path --json --stats
python3 inode_map.py /some/path --max-depth 3
python3 inode_map.py /some/path --follow-links
```

## What it does

Walks a directory, grabs `lstat()` for every file, and builds a mapping of inode → [paths]. From there you can spot hardlinks, get stats, or dump the whole thing as JSON for downstream processing.

## Flags

| Flag | Description |
|---|---|
| `path` | Target directory, defaults to `.` |
| `-f, --follow-links` | Follow symlinks during walk |
| `-d, --max-depth N` | Don't recurse deeper than N levels |
| `--hardlinks-only` | Only show inodes with more than one path |
| `--json` | Output as JSON instead of the tree view |
| `--stats` | Print summary stats after the scan |

## Output

Default output is a simple tree view:

```
Inode 12345
    └── /some/path/file.txt
Inode 67890 [2 paths] (hardlink)
    ├── /some/path/link1.dat
    └── /some/other/link2.dat
```

With `--json` you get a dict keyed by inode number, plus a `_stats` block if you also pass `--stats`.

## Stats block

```
=== Scan Statistics ===
  Total files scanned : 1432
  Unique inodes       : 1400
  Hardlinked inodes   : 12
  Hardlinked paths    : 44
  Effective unique    : 1400
```

- **Total files scanned** — every file we could stat.
- **Unique inodes** — distinct inode numbers found.
- **Hardlinked inodes** — inodes that point to multiple paths.
- **Hardlinked paths** — total path entries belonging to hardlinked inodes.
- **Effective unique** — total files minus redundant hardlink copies plus the unique inodes that represent them.

## Notes

- Permission errors on individual files are silently skipped — you'll just miss those entries if you don't have read access.
- Symlinks are recorded but stat'd with `lstat`, so the inode is the link's own inode, not the target's. Use `--follow-links` if you want the target's inode instead.
- No external dependencies. Python 3.6+ is fine since we only use `pathlib`, `os`, `stat`, `argparse`, `json`, and `collections`.
