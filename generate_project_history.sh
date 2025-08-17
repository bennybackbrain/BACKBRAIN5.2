#!/usr/bin/env bash
set -euo pipefail

OUT_MD="PROJECT_HISTORY.md"
MODE="markdown"

if [[ ${1:-} == "--json" ]]; then
  MODE="json"
fi

now_ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

is_git=0
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  is_git=1
fi

gather_git_history() {
  git log --date=iso --pretty=format:'%H|%ad|%an|%s' | head -n 500
}

list_files() {
  find . -maxdepth 8 -type f \
    ! -path './.git/*' \
    ! -path './.venv/*' \
    ! -path './__pycache__/*' \
    ! -path './.pytest_cache/*' \
    -print0 | sort -z | xargs -0 stat -f '%m|%z|%N'
}

extract_migrations() {
  if [[ -d migrations/versions ]]; then
    awk 'FNR==1{file=FILENAME} /"""/{block=$0; getline; while($0!="""" && !/^$/){block=block"\\n"$0; getline}; print file":::"block}' migrations/versions/*.py 2>/dev/null || true
  fi
}

if [[ $MODE == "json" ]]; then
  echo '{' > "$OUT_MD"
  echo '  "generated_at": '"\"$now_ts\"", >> "$OUT_MD"
  echo '  "git": {' >> "$OUT_MD"
  if [[ $is_git -eq 1 ]]; then
    echo '    "present": true,' >> "$OUT_MD"
    echo '    "log": [' >> "$OUT_MD"
    first=1
    while IFS='|' read -r hash date author subject; do
      [[ -z $hash ]] && continue
      if [[ $first -eq 0 ]]; then echo ',' >> "$OUT_MD"; fi
      first=0
      jq -nc --arg h "$hash" --arg d "$date" --arg a "$author" --arg s "$subject" '{hash:$h,date:$d,author:$a,subject:$s}' >> "$OUT_MD"
    done < <(gather_git_history)
    echo '    ]' >> "$OUT_MD"
  else
    echo '    "present": false' >> "$OUT_MD"
  fi
  echo '  },' >> "$OUT_MD"
  echo '  "files": [' >> "$OUT_MD"
  first=1
  while IFS='|' read -r mtime size path; do
    [[ -z $path ]] && continue
    iso=$(date -u -r "$mtime" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u +"%Y-%m-%dT%H:%M:%SZ")
    if [[ $first -eq 0 ]]; then echo ',' >> "$OUT_MD"; fi
    first=0
    jq -nc --arg p "$path" --arg t "$iso" --argjson s "$size" '{path:$p,modified:$t,size_bytes:$s}' >> "$OUT_MD"
  done < <(list_files)
  echo '  ],' >> "$OUT_MD"
  echo '  "migrations": [' >> "$OUT_MD"
  first=1
  while IFS=':::' read -r file block; do
    [[ -z $file ]] && continue
    cleaned=$(echo "$block" | sed 's/"/\\"/g')
    if [[ $first -eq 0 ]]; then echo ',' >> "$OUT_MD"; fi
    first=0
    echo "    {\"file\": \"$file\", \"docstring\": \"$cleaned\"}" >> "$OUT_MD"
  done < <(extract_migrations)
  echo '  ]' >> "$OUT_MD"
  echo '}' >> "$OUT_MD"
else
  {
    echo "# Project History"
    echo "Generated at: $now_ts"
    echo
    if [[ $is_git -eq 1 ]]; then
      echo "## Recent Git Commits"
      echo
      echo "| Hash | Date | Author | Subject |"
      echo "|------|------|--------|---------|"
      gather_git_history | while IFS='|' read -r hash date author subject; do
        [[ -z $hash ]] && continue
        short=${hash:0:8}
        echo "| $short | $date | $author | ${subject//|/ } |"
      done
      echo
    else
      echo "(No git repository detected – showing file snapshot.)"
      echo
    fi
    echo "## Files Snapshot"
    echo
    echo "| Path | Last Modified (UTC) | Size (bytes) |"
    echo "|------|---------------------|--------------|"
    list_files | while IFS='|' read -r mtime size path; do
      iso=$(date -u -r "$mtime" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u +"%Y-%m-%dT%H:%M:%SZ")
      echo "| ${path#./} | $iso | $size |"
    done
    echo
    if [[ -d migrations/versions ]]; then
      echo "## Migrations"
      echo
      for f in migrations/versions/*.py; do
        [[ -e $f ]] || continue
        head -n 5 "$f" | sed 's/^/    /'
        echo
      done
    fi
  } > "$OUT_MD"
fi

echo "Generated $OUT_MD in $MODE mode." >&2
