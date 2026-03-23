# cmux-win PowerShell integration — OSC 133 prompt markers + CWD + Git
function cmux_prompt_start {
  $e = [char]0x1b
  Write-Host -NoNewline "${e}]133;A${e}\"
  $cwdUri = "file://localhost/" + ($PWD.Path -replace '\\','/' -replace ' ','%20')
  Write-Host -NoNewline "${e}]7;${cwdUri}${e}\"
  $branch = git branch --show-current 2>$null
  if ($branch) {
    $dirty = ''
    if (git status --porcelain 2>$null) { $dirty = '*' }
    Write-Host -NoNewline "${e}]133;P;k=git_branch;v=${branch}${dirty}${e}\"
  }
}
function cmux_prompt_end {
  $e = [char]0x1b
  Write-Host -NoNewline "${e}]133;B${e}\"
}
$_cmux_original_prompt = $function:prompt
function prompt {
  cmux_prompt_start
  $result = & $_cmux_original_prompt
  cmux_prompt_end
  return $result
}
