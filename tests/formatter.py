import unittest
import json

import dynts


class TestFlot(unittest.TestCase):

    def testFlot1(self):
        ts = dynts.evaluate('YHOO, GOOG').dump('flot')
        dts = ts.todict()
        self.assertEqual(dts['type'], 'multiplot')
        self.assertEqual(len(dts['plots']), 1)
        plot = dts['plots'][0]
        self.assertEqual(plot['type'], 'timeseries')
        self.assertEqual(len(plot['series']), 2)
        data = json.dumps(dts)

    def testScatter(self):
        ts = dynts.evaluate('scatter(YHOO, GOOG)').dump('flot')
        dts = ts.todict()
        self.assertEqual(dts['type'], 'multiplot')
        self.assertEqual(len(dts['plots']), 1)
        plot = dts['plots'][0]
        self.assertEqual(plot['type'], 'xy')
        self.assertEqual(len(plot['series']), 1)
        serie = plot['series'][0]
        #self.assertEqual(serie['extratype'], 'date')

    def testVbaJson(self):
        ts = dynts.evaluate('AMZN, AAPL').dump('jsonvba')
        self.assertTrue(isinstance(ts, list))
        head = ts[0]
        self.assertEqual(['Date', 'AMZN', 'AAPL'], head)
        for row in ts[1:]:
            self.assertTrue(isinstance(row[0], int))
            self.assertEqual(len(row), 3)
