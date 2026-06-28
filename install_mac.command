#!/bin/bash

echo "========================================"
echo "Concrete Floor Design"
echo "macOS install script"
echo "========================================"
echo

cd "$(dirname "$0")" || {
    echo "ERROR: Could not enter the script folder."
    echo
    read -r -p "Press Enter to close..."
    exit 1
}

echo "Project folder: $(pwd)"
echo

if [ ! -f "requirements.txt" ]; then
    echo "ERROR: requirements.txt was not found."
    echo "Please put this script in the project root folder."
    echo
    read -r -p "Press Enter to close..."
    exit 1
fi

if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "ERROR: Python was not found."
    echo "Please install Python 3."
    echo
    read -r -p "Press Enter to close..."
    exit 1
fi

echo "Python:"
"$PYTHON_CMD" --version
echo
echo "Installing dependencies..."
echo

"$PYTHON_CMD" -m pip install -r requirements.txt
INSTALL_STATUS=$?

echo
if [ $INSTALL_STATUS -eq 0 ]; then
    echo "Install finished."
    echo "You can now run run_mac.command."
else
    echo "ERROR: Install failed with code $INSTALL_STATUS."
    echo "Check the messages above."
fi
echo

read -r -p "Press Enter to close..."
exit $INSTALL_STATUS
