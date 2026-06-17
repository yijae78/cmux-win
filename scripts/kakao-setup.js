// scripts/kakao-setup.js
// 사용법: node scripts/kakao-setup.js <REST_API_KEY>
//
// 1단계: 브라우저에서 인가코드 발급 URL을 열어줌
// 2단계: 리다이렉트된 URL에서 인가코드를 자동 수신
// 3단계: 토큰 교환 후 씨윈 소켓 API로 저장
const http = require('http');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const net = require('net');

const REST_API_KEY = process.argv[2];
const CLIENT_SECRET = process.argv[3] || '';
if (!REST_API_KEY) {
  console.error('Usage: node scripts/kakao-setup.js <REST_API_KEY> [CLIENT_SECRET]');
  process.exit(1);
}

const REDIRECT_URI = 'http://localhost:3939/callback';
const AUTH_URL = `https://kauth.kakao.com/oauth/authorize?client_id=${REST_API_KEY}&redirect_uri=${encodeURIComponent(REDIRECT_URI)}&response_type=code`;

async function main() {
  console.log('\n=== 카카오톡 알림 초기 설정 ===\n');
  console.log('브라우저가 열립니다. 카카오 로그인 후 동의해주세요.\n');

  // Start local callback server
  const code = await new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const url = new URL(req.url, `http://localhost:3939`);
      const authCode = url.searchParams.get('code');
      if (authCode) {
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end('<h1>인증 완료! 이 창을 닫아도 됩니다.</h1>');
        server.close();
        resolve(authCode);
      } else {
        res.writeHead(400);
        res.end('Error: no code');
      }
    });
    server.listen(3939, () => {
      console.log('콜백 서버 대기중 (localhost:3939)...');
      execSync(`start "" "${AUTH_URL}"`);
    });
  });

  console.log(`\n인가코드 수신: ${code.substring(0, 10)}...`);

  // Exchange code for tokens
  const tokenRes = await fetch('https://kauth.kakao.com/oauth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: REST_API_KEY,
      redirect_uri: REDIRECT_URI,
      code,
      ...(CLIENT_SECRET ? { client_secret: CLIENT_SECRET } : {}),
    }),
  });

  if (!tokenRes.ok) {
    console.error('토큰 교환 실패:', await tokenRes.text());
    process.exit(1);
  }

  const tokenData = await tokenRes.json();
  console.log('\n토큰 발급 성공!');

  const tokens = {
    accessToken: tokenData.access_token,
    refreshToken: tokenData.refresh_token,
    restApiKey: REST_API_KEY,
    expiresAt: new Date(Date.now() + tokenData.expires_in * 1000).toISOString(),
  };

  // Save tokens to pending file (app will encrypt on next startup)
  const pendingPaths = [
    path.join(process.env.APPDATA || '', 'cmux-win', 'kakao-tokens-pending.json'),
    path.join(process.env.APPDATA || '', 'Electron', 'kakao-tokens-pending.json'),
  ];

  for (const p of pendingPaths) {
    try {
      const dir = path.dirname(p);
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(p, JSON.stringify(tokens, null, 2));
      console.log(`토큰 저장: ${p}`);
    } catch {}
  }

  // Also try socket API (works if cmux-win has new code)
  const socketTokenPaths = [
    path.join(process.env.APPDATA || '', 'cmux-win', 'socket-token'),
    path.join(process.env.APPDATA || '', 'Electron', 'socket-token'),
  ];

  let socketToken = null;
  for (const p of socketTokenPaths) {
    try {
      socketToken = fs.readFileSync(p, 'utf8').split('\n')[0].trim();
      if (socketToken) break;
    } catch {}
  }

  if (socketToken) {
    const client = new net.Socket();
    let id = 0;

    client.connect(19840, '127.0.0.1', () => {
      client.write(JSON.stringify({
        jsonrpc: '2.0', id: id++,
        method: 'auth.handshake', token: socketToken,
      }) + '\n');
      setTimeout(() => {
        client.write(JSON.stringify({
          jsonrpc: '2.0', id: id++,
          method: 'kakao.set_tokens', params: tokens,
        }) + '\n');
        setTimeout(() => {
          console.log('\n설정 완료! 씨윈 재시작 시 카카오톡 알림이 활성화됩니다.');
          client.destroy();
          process.exit(0);
        }, 1000);
      }, 500);
    });

    client.on('data', (data) => {
      const lines = data.toString().split('\n').filter(Boolean);
      for (const line of lines) {
        try {
          const msg = JSON.parse(line);
          if (msg.error) console.warn('Socket:', msg.error.message);
          else console.log('Socket OK:', JSON.stringify(msg.result));
        } catch {}
      }
    });

    client.on('error', () => {
      console.log('\n토큰 파일 저장 완료. 씨윈 재시작 시 자동 로드됩니다.');
      process.exit(0);
    });
  } else {
    console.log('\n토큰 파일 저장 완료. 씨윈 재시작 시 자동 로드됩니다.');
  }
}

main().catch(console.error);
