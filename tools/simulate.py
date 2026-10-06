"""Let the AI play every faction for many games and print how the wars went (for balancing).

    python tools/simulate.py [games] [max_turns]
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from legendele.game import Game, GameData  # noqa: E402
from legendele.game.ai import SimpleAI  # noqa: E402


FACTIONS = ("voievodat", "zmei", "iele", "strigoi")


def play(data, seed, max_turns):
    # The "player" is AI-controlled too; rotate who it is, since the game ends if the player falls.
    game = Game.new(data, FACTIONS[seed % len(FACTIONS)], seed=seed)
    game.ai[game.player] = SimpleAI(game.player)
    game.spectate = True
    battles = 0
    while not game.over and game.round < max_turns:
        before = len(game.events)
        game.ai_turn(game.player)
        game.end_turn()
        battles += sum(type(e).__name__ == "Battle" for e in game.events[before:])
    return game, battles


def main():
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    max_turns = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    data = GameData.load()
    winners, lengths, battle_counts = Counter(), [], []
    for seed in range(games):
        game, battles = play(data, seed, max_turns)
        w = game.winner
        if w:
            winners[f"{w.faction} ({w.kind})"] += 1
        else:
            winners["no winner yet"] += 1
        lengths.append(game.round)
        battle_counts.append(battles)
    print(f"{games} games, up to {max_turns} turns each")
    for k, v in winners.most_common():
        print(f"  {k:28} {v}")
    print(f"  turns: min {min(lengths)}, avg {sum(lengths) / len(lengths):.1f}, max {max(lengths)}")
    print(f"  battles per game: avg {sum(battle_counts) / len(battle_counts):.1f}")


if __name__ == "__main__":
    main()
