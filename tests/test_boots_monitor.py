import json
import os
import tempfile
import unittest
from unittest.mock import patch
import boots_monitor as boots


class BootsTests(unittest.TestCase):
    def test_detection_and_notifications(self):
        product = {'@type': 'Product', 'url': boots.URL, 'name': boots.NAME,
                   'offers': {'availability': 'https://schema.org/InStock'}}
        def html():
            return '<script type="application/ld+json">'+json.dumps(product)+'</script>'
        self.assertEqual(boots.detect(html()), 'IN_STOCK')
        product['offers']['availability'] = 'http://schema.org/OutOfStock'
        self.assertEqual(boots.detect(html()), 'OUT_OF_STOCK')
        product['offers']['availability'] = 'https://schema.org/PreOrder'
        self.assertEqual(boots.detect(html()), 'UNKNOWN')
        product['offers'] = [{'availability': 'https://schema.org/InStock'}]*2
        self.assertEqual(boots.detect(html()), 'UNKNOWN')
        product['url'] = 'https://www.boots.com/other-product'
        self.assertEqual(boots.detect(html()), 'UNKNOWN')
        self.assertEqual(boots.detect('Access denied. Add to basket'), 'UNKNOWN')
        with patch.object(boots, 'urlopen', side_effect=OSError('blocked')):
            self.assertEqual(boots.check(), 'UNKNOWN')
        for previous in ('', 'UNKNOWN', 'IN_STOCK', 'OUT_OF_STOCK'):
            for current in ('UNKNOWN', 'IN_STOCK', 'OUT_OF_STOCK'):
                with tempfile.NamedTemporaryFile() as output, patch.dict(os.environ, {
                    'PREVIOUS_STOCK_STATE': previous, 'GITHUB_OUTPUT': output.name
                }), patch.object(boots, 'check', return_value=current), patch.object(boots.monitor, 'send_email') as send:
                    boots.run()
                    self.assertEqual(send.call_count, int(previous == 'OUT_OF_STOCK' and current == 'IN_STOCK'))
                    if send.called:
                        body = send.call_args.args[1]
                        for value in (boots.URL, boots.NAME, 'Detected (UK):', 'IN_STOCK'):
                            self.assertIn(value, body)
        with tempfile.NamedTemporaryFile() as output, patch.dict(os.environ, {
            'PREVIOUS_STOCK_STATE': 'OUT_OF_STOCK', 'GITHUB_OUTPUT': output.name
        }), patch.object(boots, 'check', return_value='IN_STOCK'), patch.object(boots.monitor, 'send_email', side_effect=RuntimeError('SMTP failure')):
            with self.assertRaises(RuntimeError):
                boots.run()
            self.assertEqual(os.path.getsize(output.name), 0)
