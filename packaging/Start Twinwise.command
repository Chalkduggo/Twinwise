#!/bin/bash
# Double-click to start Twinwise on macOS.
cd "$(dirname "$0")"
xattr -dr com.apple.quarantine . 2>/dev/null
./Twinwise ui
