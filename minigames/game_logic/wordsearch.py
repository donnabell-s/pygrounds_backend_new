# wordsearch.py
import random
import string
from dataclasses import dataclass

@dataclass
class WordPlacement:
    word: str
    row: int
    col: int
    direction: str  

class WordSearchGenerator:
    def __init__(self, size=13):
        self.size = size
        self.matrix = [['' for _ in range(size)] for _ in range(size)]
        self.placements = []
        self.directions = [
            ('across', 0, 1),
            ('down', 1, 0),
            ('diagonal', 1, 1),
        ]

    def fits(self, word, row, col, dr, dc):
        for i in range(len(word)):
            r = row + dr * i
            c = col + dc * i
            if not (0 <= r < self.size and 0 <= c < self.size):
                return False
            cell = self.matrix[r][c]
            if cell != '' and cell != word[i]:
                return False
        return True

    def place_word(self, word):
        word = word.upper()
        random.shuffle(self.directions)
        for direction, dr, dc in self.directions:
            for _ in range(100):
                row = random.randint(0, self.size - 1)
                col = random.randint(0, self.size - 1)
                if self.fits(word, row, col, dr, dc):
                    for i in range(len(word)):
                        r = row + dr * i
                        c = col + dc * i
                        self.matrix[r][c] = word[i]
                    self.placements.append(WordPlacement(word, row, col, direction))
                    return True
        return False

    def fill_random_letters(self):
        for r in range(self.size):
            for c in range(self.size):
                if self.matrix[r][c] == '':
                    self.matrix[r][c] = random.choice(string.ascii_uppercase)

    def generate(self, words):
        words.sort(key=lambda w: -len(w))  
        for word in words:
            self.place_word(word)
        self.fill_random_letters()
        return self.matrix, self.placements
