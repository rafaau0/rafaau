import unittest

from content_planner.clip_finder import find_suggestions
from content_planner.video_subtitles import Subtitle


class ClipFinderTests(unittest.TestCase):
    def test_returns_timestamped_non_overlapping_suggestions(self):
        subtitles = [
            Subtitle(0, 12, "Hoje eu quero explicar o erro que mais impede uma empresa de crescer."),
            Subtitle(12, 26, "Ninguém percebe esse problema porque parece uma tarefa pequena todos os dias."),
            Subtitle(26, 42, "A solução é medir o resultado antes de investir mais dinheiro em anúncios."),
            Subtitle(48, 62, "Agora vou falar de outro assunto sem relação com o anterior."),
            Subtitle(62, 80, "Esta é uma dica importante para vender melhor e melhorar o seu resultado."),
        ]
        suggestions = find_suggestions(subtitles)
        self.assertTrue(suggestions)
        self.assertTrue(all(item.end > item.start for item in suggestions))
        self.assertTrue(all(0 <= item.score <= 99 for item in suggestions))


if __name__ == "__main__":
    unittest.main()
