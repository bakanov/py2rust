#!/usr/bin/env python3
"""One command to rebuild and launch the web application."""

import os

from build import ROOT, build

if __name__ == "__main__":
    binary = build()
    os.chdir(ROOT)
    os.execv(binary, [str(binary)])
