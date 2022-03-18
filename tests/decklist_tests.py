import unittest
from RandardDiscordBot.decklist_verification import verify_decklist, decklist_parser
from collections import Counter
import vcr


class MyTestCase(unittest.TestCase):
    @vcr.use_cassette
    def test_1(self):
        test_decklist_1, test_sideboard_2 = decklist_parser('test_decklist_1')
        decklist_1 = Counter({'Giant Growth': 1, 'Llanowar Elves': 4, 'Forest': 55})
        self.assertEqual(test_decklist_1, decklist_1)
        self.assertTrue(verify_decklist(decklist_1, legal_sets={'10e'}))

    @vcr.use_cassette
    def test_2(self):
        test_decklist_2, test_sideboard_2 = decklist_parser('test_decklist_2')
        decklist_2 = Counter({'Mountain': 60})
        sideboard_2 = Counter({"Forest": 2})
        self.assertEqual(test_decklist_2, decklist_2)
        self.assertEqual(sideboard_2, test_sideboard_2)
        self.assertTrue(verify_decklist(decklist_2))


if __name__ == '__main__':
    unittest.main()
