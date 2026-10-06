"""Pop-up windows over the map: battle reports, captures and the end of the war."""

import pygame

from ..game import Battle, Captured, Eliminated, Victory
from . import theme

BOX = pygame.Rect(0, 0, 560, 340)
BOX.center = theme.MAP_RECT.center


def concerns_player(game, event):
    """Does the player need a pop-up for this event? (Everything else only goes to the chronicle.)"""
    if isinstance(event, Battle):
        return game.player in (event.result.attacker.faction, event.result.defender.faction)
    if isinstance(event, Captured):
        return event.previous == game.player
    return isinstance(event, (Eliminated, Victory))


def _shade(surface):
    veil = pygame.Surface(theme.MAP_RECT.size, pygame.SRCALPHA)
    veil.fill((10, 8, 6, 150))
    surface.blit(veil, theme.MAP_RECT)


def _frame(surface, rect, color):
    pygame.draw.rect(surface, theme.PANEL_BG, rect, border_radius=8)
    pygame.draw.rect(surface, color, rect, 3, border_radius=8)


def draw_report(surface, game, assets, event):
    _shade(surface)
    if isinstance(event, Battle):
        _battle(surface, game, assets, event.result)
    else:
        _notice(surface, game, event)
    theme.text(surface, "Click or press Enter to continue", (BOX.centerx, BOX.bottom - 22), 17, theme.TEXT_DIM,
               anchor="center")


def _battle(surface, game, assets, result):
    place = game.provinces[result.province].name
    player_won = result.winning_faction == game.player
    _frame(surface, BOX, theme.GOOD if player_won else theme.DANGER)
    title = f"{'Assault on' if result.kind == 'assault' else 'Battle of'} {place}"
    theme.text(surface, title, (BOX.centerx, BOX.y + 22), 34, theme.GOLD, anchor="midtop")
    theme.text(surface, "Victory!" if player_won else "Defeat", (BOX.centerx, BOX.y + 60), 30,
               theme.GOOD if player_won else theme.DANGER, anchor="midtop")

    column = BOX.width // 2
    for i, (side, label) in enumerate(((result.attacker, "Attacker"), (result.defender, "Defender"))):
        x = BOX.x + i * column + 30
        y = BOX.y + 110
        color = theme.faction_color(game, side.faction)
        banner = assets.get(f"army_{side.faction}", color)
        surface.blit(banner, (x, y))
        theme.text(surface, label, (x + 44, y), 18, theme.TEXT_DIM)
        theme.text(surface, game.faction_name(side.faction), (x + 44, y + 18), 22, color)
        y += 50
        theme.text(surface, side.leader or "Garrison", (x, y), 20)
        y += 26
        lost = side.start_regiments - side.end_regiments
        theme.text(surface, f"Regiments: {side.end_regiments} of {side.start_regiments}"
                            + (f"  ({lost} lost)" if lost else ""), (x, y), 18)
        y += 24
        bar = pygame.Rect(x, y, column - 60, 12)
        share = side.end_hp / side.start_hp if side.start_hp else 0
        pygame.draw.rect(surface, theme.DANGER, bar)
        pygame.draw.rect(surface, theme.GOOD, (bar.x, bar.y, round(bar.width * share), bar.height))
        theme.text(surface, f"{round(share * 100)}% strength left", (x, y + 18), 17, theme.TEXT_DIM)
    theme.text(surface, f"The fighting lasted {result.rounds} rounds.", (BOX.centerx, BOX.bottom - 52), 18,
               theme.TEXT_DIM, anchor="center")


def _notice(surface, game, event):
    if isinstance(event, Captured):
        title, color = f"{game.provinces[event.province].name} has fallen", theme.DANGER
        body = f"{game.faction_name(event.faction)} have taken it from us."
    elif isinstance(event, Eliminated):
        mine = event.faction == game.player
        title, color = ("Your realm is lost" if mine else f"{game.faction_name(event.faction)} are no more",
                        theme.DANGER if mine else theme.GOLD)
        body = ("The legends will forget your name." if mine
                else "Their last province has fallen; their armies scatter into the mist.")
    else:  # Victory
        mine = event.faction == game.player
        title, color = (("Victory!" if mine else "Defeat"), theme.GOOD if mine else theme.DANGER)
        how = {"conquest": f"conquered {game.victory_rules['conquest_provinces']} provinces",
               "legend": "held the Heart of the Mountains and their capital through the seasons",
               "last_standing": "outlasted every rival"}[event.kind]
        body = f"{game.faction_name(event.faction)} {how}."
    _frame(surface, BOX, color)
    theme.text(surface, title, (BOX.centerx, BOX.y + 60), 40, color, anchor="midtop")
    y = BOX.y + 130
    for line in theme.wrap(body, 24, BOX.width - 80):
        theme.text(surface, line, (BOX.centerx, y), 24, theme.PARCHMENT, anchor="midtop")
        y += 28


def draw_game_over(surface, game, button_rect, mouse):
    """A strip at the top of the map once the war is decided, with a way back to the menu."""
    strip = pygame.Rect(theme.MAP_RECT.x, 0, theme.MAP_RECT.width, 56)
    veil = pygame.Surface(strip.size, pygame.SRCALPHA)
    veil.fill((20, 14, 10, 220))
    surface.blit(veil, strip)
    won = game.winner is not None and game.winner.faction == game.player
    text = "You are master of the Carpathians!" if won else "The war is lost."
    theme.text(surface, text, (strip.x + 20, strip.centery), 30, theme.GOOD if won else theme.DANGER,
               anchor="midleft")
    theme.button(surface, button_rect, "Main menu", button_rect.collidepoint(mouse))
