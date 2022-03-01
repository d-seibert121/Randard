import unittest
from Randard.verify_decklist import verify_decklist, decklist_parser
from collections import Counter


class MyTestCase(unittest.TestCase):
    def test_1(self):
        test_decklist_1 = decklist_parser('test_decklist_1')
        decklist_1 = Counter({'Giant Growth': 1, 'Llanowar Elves': 1, 'Forest': 1})
        self.assertEqual(test_decklist_1, decklist_1)  # add assertion here
        self.assertTrue(verify_decklist(decklist_1, ['10e']))


if __name__ == '__main__':
    unittest.main()
