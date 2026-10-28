# -*- coding: utf-8 -*-
"""Episode recognition regressions; uses persisted pre-fix rules and no real writes."""
import sys, unittest, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/rename-unify/code'))
import core_rules as c

class EpisodeRecognition(unittest.TestCase):
    def test_explicit_episode_short_tracks(self):
        for info,target in [('Master','MIX'),('DX BUS','BUS'),('FX BUS','BUS'),('MX BUS','BUS'),('DX 1','STEM'),('DX VO','STEM'),('FX 2.dup3','STEM'),('MX Verb ST','STEM'),('Ai FX 1','AIFX')]:
            with self.subTest(info=info):
                h=c.identify('心剑 02集_'+info,c.DEFAULT_RULES)
                self.assertEqual((h.ep,h.target,h.captured['片名']),('02',target,'心剑'))
                self.assertEqual(h.info,info)

    def test_missing_user_is_not_version_episode(self):
        for info,target in [('Master','MIX'),('DX BUS','BUS'),('FX 1','STEM')]:
            with self.subTest(info=info):
                h=c.identify('心剑 03集 1016 V01_'+info,c.DEFAULT_RULES)
                self.assertEqual((h.ep,h.target,h.captured),('03',target,{'片名':'心剑','日期':'1016','版本':'V01'}))

    def test_incomplete_metadata_never_becomes_episode(self):
        for name in ['心剑 03集 1016_Master','心剑 03集 V01_Master']:
            with self.subTest(name=name):
                h=c.identify(name,c.DEFAULT_RULES)
                self.assertEqual((h.ep,h.target),("03","MIX"))  # v4.3.5 permits missing metadata, never a wrong episode.

    def test_old_formats_and_user_rules(self):
        for name,ep,tgt in [('心剑20_DX BUS','20','BUS'),('心剑 20集 1016 V01 7F_Master','20','MIX'),('示例Demo 20260923 V02 7F_Master','','MIX')]:
            with self.subTest(name=name):
                h=c.identify(name,c.DEFAULT_RULES);self.assertEqual((h.ep,h.target),(ep,tgt))
        custom=[['对白',r'^{片名}\s*{裸集数}_(?P<info>DX BUS)$',r'\g<info>']]+c.DEFAULT_RULES
        self.assertEqual(c.identify('心剑 02集_DX BUS',custom).target,'对白')

if __name__=='__main__': unittest.main()
