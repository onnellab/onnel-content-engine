"""Korean category localization must use the existing bounded card layout."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import publishing
from article_localization import CATEGORY_LABELS

def card(language='ko', category='productivity', title='반복 문장 정리하기', description='붙여 넣기 전에 문장과 목적지를 확인하세요.'):
    return publishing.Article({'primary_language':language,'category':category},Path('unused.md'),Path('unused.html'),'blog/test/',title,'',description,'','')

class KoreanSocialCardLabels(unittest.TestCase):
    def test_all_seven_korean_categories_are_localized(self):
        expected={'reading':'독서','music':'음악','productivity':'생산성','media':'미디어','craft':'창작','games':'게임','research':'연구'}
        self.assertEqual(CATEGORY_LABELS['ko'],expected)
        for category,label in expected.items():
            with self.subTest(category=category):
                svg=publishing.social_card_svg(card(category=category))
                self.assertIn('>'+label+'</text>',svg)
                self.assertIn(label+' · KO',svg)
                self.assertNotIn(category.upper(),svg)

    def test_short_and_long_korean_text_are_complete_and_bounded(self):
        title='반복해서 쓰는 문장을 재사용 가능한 텍스트 조각으로 정리하기'
        description='사용 맥락과 바꿀 항목을 분명히 표시하고 보내기 전에 확인하는 방법입니다. 자주 쓰는 문장을 작게 모아 최신 상태로 유지하세요.'
        for article in [card(),card(title=title,description=description)]:
            svg=publishing.social_card_svg(article)
            self.assertNotIn('…',svg);self.assertNotIn('...',svg)
            dom=ET.fromstring(svg)
            spans=dom.findall('.//{http://www.w3.org/2000/svg}tspan')
            visible=''.join(x.text or '' for x in spans).replace(' ','')
            self.assertIn(article.title.replace(' ',''),visible)
            self.assertIn(article.description.replace(' ',''),visible)
            self.assertTrue(all(float(x.attrib['y'])<=490 for x in spans))

    def test_other_eight_locales_are_byte_unchanged(self):
        old={k:v for k,v in CATEGORY_LABELS.items() if k!='ko'}
        for language in ('en','ja','zh-Hans','zh-Hant','pt-BR','de','fr','es'):
            with self.subTest(language=language):
                article=card(language=language,title='A clear article title',description='A complete description.')
                current=publishing.social_card_svg(article)
                with patch.object(publishing,'CATEGORY_LABELS',old):
                    previous=publishing.social_card_svg(article)
                self.assertEqual(current,previous)

if __name__=='__main__':unittest.main()
