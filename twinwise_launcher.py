"""Entry point for the packaged Windows app (Twinwise.exe).

Double-clicking the exe opens the review screen in your browser.
"""
import sys

from twinwise.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["ui"]))
