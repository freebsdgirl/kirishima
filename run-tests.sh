#!/bin/bash

target_dir="tests"

if [[ -n "$1" ]]; then
  target_dir="tests/$1"
  if [[ ! -d "$target_dir" ]]; then
    echo "❌ No such test group: $1"
    exit 1
  fi
fi

echo "🔍 Running tests from: $target_dir"
echo

for file in "$target_dir"/*.sh; do
  echo "⏱ $file"
  bash "$file"
done
