"""Check public bibliographic markup without changing the manuscript."""
import json
from html.parser import HTMLParser
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.structured = []
        self.in_json = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'meta' and 'name' in values:
            self.meta[values['name']] = values.get('content')
        if tag == 'script' and values.get('type') == 'application/ld+json':
            self.in_json = True

    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_json = False

    def handle_data(self, data):
        if self.in_json:
            self.structured.append(json.loads(data))


class DiscoverabilityTest(unittest.TestCase):
    def test_metadata_and_static_abstract(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / 'docs/index.html').read_text(encoding='utf-8')
        parser = MetadataParser()
        parser.feed(html)
        meta = parser.meta
        self.assertEqual(meta['citation_author'], 'Oliver Pardo')
        self.assertEqual(meta['citation_doi'], '10.2139/ssrn.7546439')
        self.assertEqual(meta['citation_publication_date'], '2026/09/27')
        self.assertTrue(meta['citation_pdf_url'].endswith('.pdf'))
        self.assertNotIn('citation_journal_title', meta)
        article, = parser.structured
        self.assertEqual(article['creativeWorkStatus'], 'Preprint')
        self.assertEqual(article['headline'], meta['citation_title'])
        self.assertIn('<p>' + article['abstract'] + '</p>', html)
        self.assertIn('citation.bib', html)
        ET.fromstring((root / 'docs/sitemap.xml').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
