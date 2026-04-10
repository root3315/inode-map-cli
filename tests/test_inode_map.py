"""Unit tests for inode_map core functions."""

import json
import os
import stat
import tempfile
from pathlib import Path
from unittest import TestCase, main

from inode_map import (
    compute_stats,
    find_hardlinks,
    format_json,
    format_tree,
    scan_directory,
)


class TestScanDirectory(TestCase):
    """Tests for the scan_directory function."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _create_file(self, relative_path, content="data"):
        """Create a file with the given content."""
        full_path = self.root / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        return full_path

    def test_single_file(self):
        self._create_file("a.txt", "hello")
        result = scan_directory(self.root)
        self.assertEqual(len(result), 1)
        ino = list(result.keys())[0]
        self.assertEqual(len(result[ino]), 1)
        self.assertTrue(result[ino][0].endswith("a.txt"))

    def test_multiple_files(self):
        self._create_file("a.txt", "aaa")
        self._create_file("b.txt", "bbb")
        result = scan_directory(self.root)
        self.assertEqual(len(result), 2)

    def test_nested_directories(self):
        self._create_file("sub/deep/c.txt", "deep content")
        result = scan_directory(self.root)
        self.assertEqual(len(result), 1)
        paths = list(result.values())[0]
        self.assertEqual(len(paths), 1)
        self.assertIn("c.txt", paths[0])

    def test_hardlinks_detected(self):
        file_a = self._create_file("original.txt", "shared")
        link_path = self.root / "hardlink.txt"
        os.link(str(file_a), str(link_path))

        result = scan_directory(self.root)
        self.assertEqual(len(result), 1)
        ino = list(result.keys())[0]
        self.assertEqual(len(result[ino]), 2)

    def test_max_depth_limits_traversal(self):
        self._create_file("l1/l2/l3/deep.txt", "very deep")
        result = scan_directory(self.root, max_depth=2)
        paths = []
        for p in result.values():
            paths.extend(p)
        for p in paths:
            depth = Path(p).relative_to(self.root).parts.__len__()
            self.assertLessEqual(depth, 2)

    def test_empty_directory(self):
        result = scan_directory(self.root)
        self.assertEqual(result, {})

    def test_nonexistent_directory_exits(self):
        with self.assertRaises(SystemExit):
            scan_directory("/nonexistent/path/xyz")

    def test_file_as_root_exits(self):
        file_path = self._create_file("single.txt", "x")
        with self.assertRaises(SystemExit):
            scan_directory(str(file_path))

    def test_paths_are_absolute(self):
        self._create_file("rel.txt", "abs check")
        result = scan_directory(self.root)
        for paths in result.values():
            for p in paths:
                self.assertTrue(os.path.isabs(p))


class TestFindHardlinks(TestCase):
    """Tests for the find_hardlinks function."""

    def test_returns_only_multi_path_entries(self):
        inode_map = {
            100: ["/a.txt"],
            200: ["/b.txt", "/b_link.txt"],
            300: ["/c.txt", "/c_l1.txt", "/c_l2.txt"],
        }
        result = find_hardlinks(inode_map)
        self.assertEqual(len(result), 2)
        self.assertIn(200, result)
        self.assertIn(300, result)
        self.assertNotIn(100, result)

    def test_no_hardlinks_returns_empty(self):
        inode_map = {1: ["/a.txt"], 2: ["/b.txt"]}
        result = find_hardlinks(inode_map)
        self.assertEqual(result, {})

    def test_empty_map_returns_empty(self):
        self.assertEqual(find_hardlinks({}), {})


class TestFormatTree(TestCase):
    """Tests for the format_tree function."""

    def test_single_file_format(self):
        inode_map = {12345: ["/tmp/a.txt"]}
        output = format_tree(inode_map, show_all=True)
        self.assertIn("Inode 12345", output)
        self.assertIn("/tmp/a.txt", output)
        self.assertIn("└── ", output)

    def test_hardlink_format(self):
        inode_map = {
            999: ["/tmp/original.txt", "/tmp/hardlink.txt"]
        }
        output = format_tree(inode_map)
        self.assertIn("Inode 999 [2 paths] (hardlink)", output)
        self.assertIn("/tmp/hardlink.txt", output)
        self.assertIn("/tmp/original.txt", output)

    def test_show_all_false_skips_singles(self):
        inode_map = {
            1: ["/a.txt"],
            2: ["/b.txt", "/b_link.txt"],
        }
        output = format_tree(inode_map, show_all=False)
        self.assertIn("Inode 2", output)
        self.assertNotIn("Inode 1", output)

    def test_empty_map_returns_empty_string(self):
        self.assertEqual(format_tree({}), "")

    def test_paths_are_sorted(self):
        inode_map = {1: ["/z.txt", "/a.txt", "/m.txt"]}
        output = format_tree(inode_map)
        lines = output.split("\n")
        path_lines = [l for l in lines if "/" in l and "Inode" not in l]
        self.assertIn("/a.txt", path_lines[0])
        self.assertIn("/m.txt", path_lines[1])
        self.assertIn("/z.txt", path_lines[2])

    def test_inodes_are_sorted(self):
        inode_map = {300: ["/c.txt"], 100: ["/a.txt"], 200: ["/b.txt"]}
        output = format_tree(inode_map)
        lines = output.split("\n")
        inode_lines = [l for l in lines if l.startswith("Inode ")]
        self.assertIn("100", inode_lines[0])
        self.assertIn("200", inode_lines[1])
        self.assertIn("300", inode_lines[2])


class TestComputeStats(TestCase):
    """Tests for the compute_stats function."""

    def test_basic_stats(self):
        inode_map = {
            1: ["/a.txt"],
            2: ["/b.txt", "/b_link.txt"],
        }
        stats = compute_stats(inode_map)
        self.assertEqual(stats["total_files"], 3)
        self.assertEqual(stats["total_inodes"], 2)
        self.assertEqual(stats["hardlinked_inodes"], 1)
        self.assertEqual(stats["hardlinked_files"], 2)

    def test_empty_map_stats(self):
        stats = compute_stats({})
        self.assertEqual(stats["total_files"], 0)
        self.assertEqual(stats["total_inodes"], 0)
        self.assertEqual(stats["hardlinked_inodes"], 0)
        self.assertEqual(stats["hardlinked_files"], 0)
        self.assertEqual(stats["unique_files"], 0)

    def test_all_unique_files(self):
        inode_map = {
            1: ["/a.txt"],
            2: ["/b.txt"],
            3: ["/c.txt"],
        }
        stats = compute_stats(inode_map)
        self.assertEqual(stats["total_files"], 3)
        self.assertEqual(stats["hardlinked_inodes"], 0)
        self.assertEqual(stats["unique_files"], 3)

    def test_effective_unique_count(self):
        inode_map = {
            1: ["/a.txt"],
            2: ["/b.txt", "/b_link.txt"],
        }
        stats = compute_stats(inode_map)
        self.assertEqual(stats["unique_files"], 2)


class TestFormatJson(TestCase):
    """Tests for the format_json function."""

    def test_valid_json_output(self):
        inode_map = {123: ["/b.txt", "/a.txt"]}
        result = format_json(inode_map, include_stats=False)
        parsed = json.loads(result)
        self.assertIn("123", parsed)
        self.assertEqual(parsed["123"], ["/a.txt", "/b.txt"])

    def test_stats_included_when_requested(self):
        inode_map = {1: ["/a.txt"]}
        result = format_json(inode_map, include_stats=True)
        parsed = json.loads(result)
        self.assertIn("_stats", parsed)
        self.assertIn("total_files", parsed["_stats"])

    def test_stats_excluded_when_not_requested(self):
        inode_map = {1: ["/a.txt"]}
        result = format_json(inode_map, include_stats=False)
        parsed = json.loads(result)
        self.assertNotIn("_stats", parsed)

    def test_inodes_sorted_in_json(self):
        inode_map = {300: ["/c.txt"], 100: ["/a.txt"]}
        result = format_json(inode_map, include_stats=False)
        keys = list(json.loads(result).keys())
        self.assertEqual(keys, ["100", "300"])


if __name__ == "__main__":
    main()
