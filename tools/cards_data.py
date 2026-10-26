"""Standard 52-card deck: codes, display names, rank and suit numbering.

A card code is two ASCII characters, rank then suit:

    rank : A 2 3 4 5 6 7 8 9 T J Q K      (T is the ten)
    suit : S H D C                        (spades hearts diamonds clubs)

so "AS" is the ace of spades and "TD" the ten of diamonds. Two characters
means card lookup can reuse the same binary search as the country and state
tables. Jokers use rank 'Z' with suit 'R' (red) or 'B' (black).
"""

# (suit_char, suit_name, is_red)
SUITS = [
    ("S", "Spades", False),
    ("H", "Hearts", True),
    ("D", "Diamonds", True),
    ("C", "Clubs", False),
]

# (rank_char, rank_name, rank_value)  -- ace low at 1, king at 13.
RANKS = [
    ("A", "Ace", 1),
    ("2", "Two", 2),
    ("3", "Three", 3),
    ("4", "Four", 4),
    ("5", "Five", 5),
    ("6", "Six", 6),
    ("7", "Seven", 7),
    ("8", "Eight", 8),
    ("9", "Nine", 9),
    ("T", "Ten", 10),
    ("J", "Jack", 11),
    ("Q", "Queen", 12),
    ("K", "King", 13),
]

# Suit numbering handed to C as MNF_SUIT_*; keep in step with templates.py.
SUIT_INDEX = {"S": 0, "H": 1, "D": 2, "C": 3}
SUIT_NONE = 4

JOKERS = [
    ("ZR", "Red Joker", True),
    ("ZB", "Black Joker", False),
]


def deck(jokers: bool = False) -> list[dict]:
    """The deck as table rows, sorted by code so lookup can binary-search."""
    rows = []
    for suit_char, suit_name, is_red in SUITS:
        for rank_char, rank_name, value in RANKS:
            rows.append({
                "code": rank_char + suit_char,
                "name": f"{rank_name} of {suit_name}",
                "rank": value,
                "suit": SUIT_INDEX[suit_char],
                "red": is_red,
            })
    if jokers:
        for code, name, is_red in JOKERS:
            rows.append({
                "code": code, "name": name,
                "rank": 0, "suit": SUIT_NONE, "red": is_red,
            })
    return sorted(rows, key=lambda r: r["code"])
