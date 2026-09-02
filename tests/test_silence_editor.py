import unittest
from content_planner.silence_editor import Cut, SilenceSettings, map_time, plan_cuts, remap_subtitles
from content_planner.video_subtitles import Subtitle

class SilenceEditorTests(unittest.TestCase):
    def test_short_silence_is_kept(self):
        self.assertEqual(plan_cuts([(1,1.3)],SilenceSettings(mode="Remover silêncios")),[])
    def test_long_silence_preserves_margins(self):
        cuts=plan_cuts([(1,3)],SilenceSettings(mode="Remover silêncios",before_margin=.15,after_margin=.15))
        self.assertEqual(cuts,[Cut(1.15,2.85)])
    def test_timestamps_are_remapped(self):
        subs=remap_subtitles([Subtitle(.2,.8,"A"),Subtitle(3,4,"B")],[Cut(1,2)])
        self.assertEqual((subs[1].start,subs[1].end),(2,3))
        self.assertEqual(map_time(1.5,[Cut(1,2)]),1)
