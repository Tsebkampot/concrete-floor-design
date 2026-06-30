#!/bin/bash

echo "========================================"
echo "Concrete Floor Design"
echo "macOS run script"
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

if [ ! -f "app.py" ]; then
    echo "ERROR: app.py was not found."
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
echo "Starting Streamlit..."
echo "An available local port will be selected automatically."
echo "If the browser does not open, use the Local URL shown below."
echo

"$PYTHON_CMD" -m streamlit run app.py --server.port 0
RUN_STATUS=$?

echo
if [ $RUN_STATUS -eq 0 ]; then
    echo "Program closed."
else
    echo "ERROR: Program exited with code $RUN_STATUS."
    echo "Check the messages above."
fi
echo

read -r -p "Press Enter to close..."
exit $RUN_STATUS
