import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_store_reviews import review_id_from_link

class ReviewLinkTest(unittest.TestCase):
    def test_modern_link(self):
        self.assertEqual(review_id_from_link('https://play.google.com/console/reviews?reviewId=abc%2D123'), 'abc-123')
    def test_legacy_link(self):
        self.assertEqual(review_id_from_link('https://play.google.com/#ReviewPlace:id=old-456&other=x'), 'old-456')
    def test_never_guess_from_app_id(self):
        self.assertEqual(review_id_from_link('https://play.google.com/store/apps/details?id=com.example.app'), '')
    def test_no_link(self):
        self.assertEqual(review_id_from_link(''), '')
