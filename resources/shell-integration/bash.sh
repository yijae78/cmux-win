#!/bin/bash
# cmux-win Bash integration (WSL / Git Bash) — OSC 133 + CWD + Git
cmux_precmd() {
  local e=$'\e'
  printf '%s]133;A%s\\' "$e" "$e"
  printf '%s]7;file://localhost%s%s\\' "$e" "$PWD" "$e"
  local branch
  branch=$(git branch --show-current 2>/dev/null)
  if [ -n "$branch" ]; then
    local dirty=""
    if [ -n "$(git status --porcelain 2>/dev/null | head -1)" ]; then dirty="*"; fi
    printf '%s]133;P;k=git_branch;v=%s%s%s\\' "$e" "$branch" "$dirty" "$e"
  fi
}
if [[ ! "$PROMPT_COMMAND" == *"cmux_precmd"* ]]; then
  PROMPT_COMMAND="cmux_precmd;${PROMPT_COMMAND:-}"
fi
