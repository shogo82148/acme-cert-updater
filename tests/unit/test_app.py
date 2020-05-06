"""tests of acme-cert-updater"""

import unittest

from updater import app

class TestConfig(unittest.TestCase):
    def test_domains(self):
        config = app.Config({'domains': ''})
        self.assertEqual(config.domains, [])

        config = app.Config({'domains': 'example.com'})
        self.assertEqual(config.domains, ['example.com'])

        config = app.Config({'domains': 'example.com, *.EXAMPLE.com ,'})
        self.assertEqual(config.domains, ['example.com', '*.example.com'])

        config = app.Config({'domains': []})
        self.assertEqual(config.domains, [])

        config = app.Config({'domains': ['example.com']})
        self.assertEqual(config.domains, ['example.com'])

        config = app.Config({'domains': ['example.com', ' *.EXAMPLE.com ', ' ', 123]})
        self.assertEqual(config.domains, ['example.com', '*.example.com'])

    def test_cert_name(self):
        config = app.Config({'domains': ''})
        self.assertEqual(config.cert_name, '')

        config = app.Config({'domains': 'EXAMPLE.com'})
        self.assertEqual(config.cert_name, 'example.com')

        config = app.Config({'domains': '*.example.com'})
        self.assertEqual(config.cert_name, 'example.com')

        config = app.Config({'cert_name': 'EXAMPLE.com'})
        self.assertEqual(config.cert_name, 'example.com')

if __name__ == '__main__':
    unittest.main()
