@echo off
REM cmux-win open wrapper — opens URL in browser panel instead of system browser
REM Usage: open https://example.com

IF NOT DEFINED CMUX_SOCKET_PORT (
  REM Not inside cmux-win, use system default
  start "" %*
  exit /b %ERRORLEVEL%
)

REM Inside cmux-win: send RPC to open browser panel
node -e "const net=require('net');const s=net.connect(%CMUX_SOCKET_PORT%,'127.0.0.1',()=>{s.write(JSON.stringify({jsonrpc:'2.0',id:1,method:'browser.open',params:{url:process.argv[1]}})+'\n');s.on('data',()=>s.end())});s.on('error',()=>process.exit(1))" %1
