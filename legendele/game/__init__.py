"""Game rules and campaign state. Must not import pygame."""

from . import diplomacy, economy, events, foreign, generals, legends
from .battle import BattleResult, Regiment
from .data import DataError, GameData
from .diplomacy import DiplomacyChange, Proposal
from .events import Tale
from .foreign import Plundered, Raid
from .legends import Abduction, Rebellion
from .state import (Army, Battle, Captured, Eliminated, Game, GeneralFell, MoveError, Province, Retreated,
                    SiegeStarted, Victory)

__all__ = ["diplomacy", "economy", "legends", "DiplomacyChange", "Proposal", "Abduction", "Rebellion", "Army", "Battle", "BattleResult", "Captured", "DataError", "Eliminated", "Game", "GameData", "GeneralFell",
           "MoveError", "Province", "Regiment", "Retreated", "SiegeStarted", "Tale", "Victory", "Raid", "Plundered"]
