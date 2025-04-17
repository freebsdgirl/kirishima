#!/bin/bash

cd ..
echo "              🔍 Kirishima Test Runner 🔍"
echo

if [[ -n "$1" ]]; then
  target_dir="tests/$1"
  if [[ ! -d "$target_dir" ]]; then
    echo "❌ No such test group: $1"
    exit 1
  fi
  echo "▶ Running tests in: $target_dir"
  echo
  find "$target_dir" -type f -name "*.sh" -exec bash {} \;
else
  find tests -type f -name "*.sh" -exec bash {} \;
fi

