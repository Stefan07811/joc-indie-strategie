"""The campaign's calendar: a turn is a month."""

from dataclasses import dataclass

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
SEASONS = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring", 6: "summer",
           7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "autumn"}


@dataclass(frozen=True, order=True)
class Date:
    year: int
    month: int   # 1 .. 12

    def next(self):
        return Date(self.year + self.month // 12, self.month % 12 + 1)

    @property
    def season(self):
        return SEASONS[self.month]

    def months_since(self, other):
        return (self.year - other.year) * 12 + self.month - other.month

    def __str__(self):
        return f"{MONTHS[self.month - 1]} {self.year}"


START = Date(1402, 9)   # two months after Ankara: Timur has broken the Ottomans, Bayezid is his prisoner
