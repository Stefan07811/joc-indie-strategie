"""Entry point for the packaged Crowns of the Balkans (PyInstaller needs a script, not `python -m crowns`).

In the packaged program Panda3D's plugins (the OpenGL display, the OpenAL sound) lie in the bundle's
panda3d folder: tell Panda where. If the game crashes, the error is written to ~/.crowns/crash.log and
shown in a message box, since a windowed program has no console."""

import os
import sys
import traceback
from pathlib import Path


def _point_panda_at_its_plugins():
    if not getattr(sys, "frozen", False):
        return
    from panda3d.core import Filename, loadPrcFileData
    plugins = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "panda3d"
    loadPrcFileData("frozen", f"plugin-path {Filename.fromOsSpecific(str(plugins)).getFullpath()}\n"
                              "load-display pandagl\n")


def _report(error_text):
    home = Path(os.environ.get("CROWNS_HOME", Path.home() / ".crowns"))
    try:
        home.mkdir(parents=True, exist_ok=True)
        (home / "crash.log").write_text(error_text, encoding="utf-8")
    except OSError:
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, "Crowns of the Balkans stopped because of an error.\n\n"
                                             f"{error_text[-1500:]}\n\nThe full report is in {home / 'crash.log'}",
                                             "Crowns of the Balkans", 0x10)
        except Exception:   # noqa: BLE001 - nothing more can be done
            pass


def main():
    try:
        _point_panda_at_its_plugins()
        from crowns.app import main as run
        sys.exit(run())
    except SystemExit:
        raise
    except BaseException:   # noqa: BLE001 - anything that kills the game is reported
        _report(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
