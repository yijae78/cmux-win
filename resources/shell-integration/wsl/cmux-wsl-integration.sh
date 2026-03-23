#!/usr/bin/env bash
# cmux-win WSL shell integration
# Sources the standard bash integration with WSL-specific path conversion

# Convert Windows path to WSL path for CWD reporting
cmux_wsl_cwd() {
  local win_path
  win_path=$(wslpath -w "$(pwd)" 2>/dev/null || pwd)
  printf '\033]7;file://localhost/%s\033\\' "$win_path"
}

# OSC 133 prompt markers
cmux_wsl_precmd() {
  local exit_code=$?
  # Report previous command exit code
  printf '\033]133;D;%d\033\\' "$exit_code"
  # Report CWD
  cmux_wsl_cwd
  # Git branch detection
  local branch
  branch=$(git symbolic-ref --short HEAD 2>/dev/null)
  if [ -n "$branch" ]; then
    local dirty=""
    if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
      dirty="*"
    fi
    printf '\033]133;P;k=git_branch;v=%s%s\033\\' "$branch" "$dirty"
  fi
  # Prompt start
  printf '\033]133;A\033\\'
}

# Inject into PROMPT_COMMAND
if [[ -n "$CMUX_SHELL_INTEGRATION" ]]; then
  PROMPT_COMMAND="cmux_wsl_precmd${PROMPT_COMMAND:+;$PROMPT_COMMAND}"
fi
