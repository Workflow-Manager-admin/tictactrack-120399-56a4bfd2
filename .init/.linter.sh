#!/bin/bash
cd /home/kavia/workspace/code-generation/tictactrack-120399-56a4bfd2/tic_tac_toe_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

