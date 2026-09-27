from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_compilation_cover as cover


class CompilationCoverTests(unittest.TestCase):
    def test_balanced_title_and_opaque_card(self):
        self.assertEqual(
            ["Roads Between", "Distant Kingdoms"],
            cover.wrap_title("Roads Between Distant Kingdoms"),
        )
        svg = cover.overlay_svg("Roads Between Distant Kingdoms")
        self.assertIn("Roads Between", svg)
        self.assertIn("Distant Kingdoms", svg)
        self.assertIn("30 MINUTE JOURNEY", svg)
        self.assertIn('fill="#1B2C3C" opacity="1"', svg)
        self.assertIn("Aether Inn", svg)


if __name__ == "__main__":
    unittest.main()
