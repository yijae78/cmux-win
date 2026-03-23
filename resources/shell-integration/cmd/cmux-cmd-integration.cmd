@echo off
REM cmux-win CMD.exe shell integration
REM Sets PROMPT to emit OSC 7 (CWD) after each command

REM Save original prompt
IF NOT DEFINED CMUX_ORIGINAL_PROMPT SET "CMUX_ORIGINAL_PROMPT=%PROMPT%"

REM Set prompt to emit OSC 7 CWD sequence
REM CMD can emit escape sequences if VIRTUAL_TERMINAL_PROCESSING is enabled
REM ESC ]7;file://localhost/CWD ESC\
SET "PROMPT=$E]7;file://localhost/$P$E\%CMUX_ORIGINAL_PROMPT%"
