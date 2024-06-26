from __future__ import absolute_import
import unittest
import doctest
from structurebot import pos
from structurebot.config import CONFIG
from structurebot.util import name_to_id, ncr


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(pos))
    return tests


class TestPOS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        CONFIG['CORP_ID'] = cls.corp_id = name_to_id(CONFIG['CORPORATION_NAME'], 'corporation')
        corporation_id_request, corporation_id_data = ncr.get_corporations_corporation_id(corporation_id=cls.corp_id)
        cls.alliance_id = corporation_id_data.get('alliance_id', None)

    def test_sov(self):
        sov_ids = pos.sov_systems(self.alliance_id)
        for system in sov_ids:
            self.assertIsInstance(system, int)

    def test_pos_from_corp(self):
        [self.assertIsInstance(s, pos.Pos) for s in pos.Pos.from_corp_name(CONFIG['CORPORATION_NAME'])]

    def test_check_pos(self):
        [self.assertIsInstance(s, str) for s in pos.check_pos(CONFIG['CORPORATION_NAME'])]