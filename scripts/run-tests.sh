#!/usr/bin/env bash
cd ..

echo "              🔍 Kirishima Test Runner 🔍"
echo

# pick a sub‑folder if given
if [[ -n "$1" ]]; then
  target_dir="tests/$1"
  if [[ ! -d "$target_dir" ]]; then
    echo "❌ No such test group: $1"
    exit 1
  fi
  echo "▶ Running tests in: $target_dir"
  echo
else
  target_dir="tests"
fi

# find & sort: basename (field 3) then dirname (field 2)
find "$target_dir" -type f -name "*.sh" | \
  sort -t/ -k3,3 -k2,2 | \
  while IFS= read -r script; do
    bash "$script"
    echo
  done
