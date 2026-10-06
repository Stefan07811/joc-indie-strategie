"""Start the game:  python -m legendele

Extra options for development:
  --faction ID        skip the faction screen (voievodat, zmei, iele, strigoi, outlaws, solomonari)
  --screenshot FILE   draw one frame to FILE and exit (works without a display)
"""

import argparse
import os


def main():
    parser = argparse.ArgumentParser(prog="legendele", description="Legends of the Carpathians")
    parser.add_argument("--faction")
    parser.add_argument("--screenshot")
    parser.add_argument("--select-army", action="store_true", help="with --screenshot: select the first army")
    parser.add_argument("--turns", type=int, default=0, help="with --faction: end this many turns first")
    args = parser.parse_args()

    if args.screenshot:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    from .ui.app import App

    app = App()
    if args.faction:
        app.start_campaign(args.faction)
        for _ in range(args.turns):
            app.scene.end_turn()
        if args.select_army:
            app.scene.select_next_army()
            reach = app.scene.reach()
            if reach:
                app.scene.hovered = max(reach, key=lambda pid: (reach[pid].cost, pid))
    if args.screenshot:
        app.screenshot(args.screenshot)
    else:
        app.run()


if __name__ == "__main__":
    main()
