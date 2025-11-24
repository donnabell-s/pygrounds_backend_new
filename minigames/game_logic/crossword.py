import random

class WordPlacement:
    def __init__(self, word, row, col, direction):
        self.word = word
        self.row = row
        self.col = col
        self.direction = direction  # 'across' or 'down'

class CrosswordGenerator:
    def __init__(self, size=15):
        self.size = size
        self.grid = [[' ' for _ in range(size)] for _ in range(size)]
        self.placements = []

    def fits(self, word, row, col, direction):
        word = word.upper()
        if direction == 'across':
            if col < 0 or col + len(word) > self.size or row < 0 or row >= self.size:
                return False
            for i, letter in enumerate(word):
                r, c = row, col + i
                cell = self.grid[r][c]
                if cell != ' ' and cell != letter:
                    return False
                # Optional: block side touching
                if cell == ' ':
                    if r > 0 and self.grid[r - 1][c] != ' ':
                        return False
                    if r < self.size - 1 and self.grid[r + 1][c] != ' ':
                        return False
            return True
        else:  # down
            if row < 0 or row + len(word) > self.size or col < 0 or col >= self.size:
                return False
            for i, letter in enumerate(word):
                r, c = row + i, col
                cell = self.grid[r][c]
                if cell != ' ' and cell != letter:
                    return False
                if cell == ' ':
                    if c > 0 and self.grid[r][c - 1] != ' ':
                        return False
                    if c < self.size - 1 and self.grid[r][c + 1] != ' ':
                        return False
            return True

    def place_at(self, word, row, col, direction):
        word = word.upper()
        for i, letter in enumerate(word):
            if direction == 'across':
                self.grid[row][col + i] = letter
            else:
                self.grid[row + i][col] = letter
        self.placements.append(WordPlacement(word, row, col, direction))

    def find_best_intersections(self, word):
        word = word.upper()
        options = []

        for existing in self.placements:
            for i, existing_letter in enumerate(existing.word):
                for j, new_letter in enumerate(word):
                    if existing_letter != new_letter:
                        continue

                    if existing.direction == 'across':
                        direction = 'down'
                        row = existing.row - j
                        col = existing.col + i
                    else:
                        direction = 'across'
                        row = existing.row + i
                        col = existing.col - j

                    if self.fits(word, row, col, direction):
                        # Score: count how many letters overlap
                        score = self.count_intersections(word, row, col, direction)
                        options.append((score, row, col, direction))

        options.sort(reverse=True)  # higher score = more intersecting letters
        return options

    def count_intersections(self, word, row, col, direction):
        count = 0
        word = word.upper()
        for i, letter in enumerate(word):
            r = row + i if direction == 'down' else row
            c = col + i if direction == 'across' else col
            if 0 <= r < self.size and 0 <= c < self.size:
                if self.grid[r][c] == letter:
                    count += 1
        return count

    def place_word(self, word):
        word = word.upper()

        if not self.placements:
            # Place first word at center
            row = self.size // 2
            col = (self.size - len(word)) // 2
            if self.fits(word, row, col, 'across'):
                self.place_at(word, row, col, 'across')
                return True

        # Try intersecting
        options = self.find_best_intersections(word)
        # Only keep intersecting placements (score >= 1)
        options = [opt for opt in options if opt[0] >= 1]

        # Sort options by score and proximity to center
        def distance_to_center(row, col):
            center = self.size // 2
            return abs(row - center) + abs(col - center)

        options.sort(key=lambda x: (-(x[0]), distance_to_center(x[1], x[2])))

        for score, row, col, direction in options:
            self.place_at(word, row, col, direction)
            return True

        # Fallback: try random but bias toward center
        for _ in range(100):
            direction = random.choice(['across', 'down'])
            mid = self.size // 2
            row = random.randint(mid - 4, mid + 4)
            col = random.randint(mid - 4, mid + 4)
            if self.fits(word, row, col, direction):
                self.place_at(word, row, col, direction)
                return True

        print(f"Could not place: {word}")
        return False


    def generate(self, words):
        words.sort(key=lambda w: -len(w))  # longest first
        for word in words:
            self.place_word(word)
        return self.grid, self.placements
