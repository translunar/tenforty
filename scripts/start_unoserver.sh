#!/bin/sh
# Start the unoserver daemon using LibreOffice's Python.
LO_PYTHON="/Applications/LibreOffice.app/Contents/Resources/python"
if [ ! -f "$LO_PYTHON" ]; then
    echo "Error: LibreOffice Python not found at $LO_PYTHON"
    exit 1
fi
echo "Starting unoserver daemon..."
exec "$LO_PYTHON" -m unoserver.server "$@"
