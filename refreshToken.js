const axios = require("axios");
const fs = require("fs");
const path = require("path");
const { exec } = require("child_process");
const { promisify } = require("util");
const execPromise = promisify(exec);
const process = require('process');
// 로거 모듈 가져오기 (기존 로거를 재사용합니다)
const logger = require('./logger');

// -----------------------------------------------------------------------------
// 기존 스크립트의 헬퍼 함수 (수정 없이 그대로 사용)
// -----------------------------------------------------------------------------
async function getAllUserIds() {
  try {
    // 따옴표 문제를 해결하기 위해 Python 코드를 파일로 저장하고 실행
    const tempScriptPath = path.join(__dirname, 'temp_get_users.py');

    // 임시 Python 스크립트 작성
    fs.writeFileSync(tempScriptPath, `
import json
import sys
sys.path.append('.')
from library import secret

# Get all userIds from USER_AUTH_CONFIGS
user_ids = list(secret.USER_AUTH_CONFIGS.keys())

# Output as JSON
print(json.dumps(user_ids))
`);

    // 파일로 저장된 Python 스크립트 실행
    const { stdout } = await execPromise(`python ${tempScriptPath}`);

    // 임시 파일 삭제
    fs.unlinkSync(tempScriptPath);

    return JSON.parse(stdout.trim());
  } catch (error) {
    logger.error(`Error reading Python userIds: ${error}`);
    throw error;
  }
}
/**
 * Python secret 파일에서 특정 사용자의 auth 설정을 읽어옵니다.
 */
async function getUserAuthConfig(userId) {
  logger.info(`getUserAuthConfig 함수 실행: 사용자 ID = "${userId}"`);
  try {
    const tempScriptPath = path.join(__dirname, 'temp_get_config.py');
    fs.writeFileSync(tempScriptPath, `
import json
import sys
sys.path.append('.')
from library import secret

user_id = sys.argv[1]
user_config = secret.USER_AUTH_CONFIGS[user_id]
client_id = user_config["app_key"]
client_secret = user_config["secret"]

print(json.dumps({
    "clientId": client_id,
    "clientSecret": client_secret
}))
`);
    const { stdout } = await execPromise(`python ${tempScriptPath} "${userId}"`);
    fs.unlinkSync(tempScriptPath);
    return JSON.parse(stdout.trim());
  } catch (error) {
    logger.error(`Error reading Python credentials: ${error}`);
    throw error;
  }
}

/**
 * 갱신된 토큰을 JSON 파일에 저장합니다.
 */
function saveTokensToFile(userId, tokenData) {
  const tokensDir = path.join(__dirname, 'library', 'tokens');
  if (!fs.existsSync(tokensDir)) {
    fs.mkdirSync(tokensDir, { recursive: true });
  }

  const tokenFilePath = path.join(tokensDir, `schwab_token_${userId}.json`);
  const tokenContent = JSON.stringify({
    "creation_timestamp": Math.floor(Date.now() / 1000),
    "token": {
      "expires_in": tokenData.expires_in,
      "token_type": tokenData.token_type,
      "scope": tokenData.scope || "api",
      "refresh_token": tokenData.refresh_token,
      "access_token": tokenData.access_token,
      "id_token": tokenData.id_token || "",
      "expires_at": Math.floor(Date.now() / 1000) + tokenData.expires_in
    }
  }, null, 2);

  fs.writeFileSync(tokenFilePath, tokenContent);
  logger.info(`Tokens saved to ${tokenFilePath}`);
}

// -----------------------------------------------------------------------------
// 핵심 로직: 토큰 읽기 및 갱신 (수정된 함수)
// -----------------------------------------------------------------------------

/**
 * 파일에서 기존 refresh_token을 읽어옵니다.
 */
function getRefreshTokenFromFile(userId) {
  const tokenFilePath = path.join(__dirname, 'library', 'tokens', `schwab_token_${userId}.json`);

  if (!fs.existsSync(tokenFilePath)) {
    logger.error(`Token file not found for user ${userId} at ${tokenFilePath}`);
    throw new Error(`Token file not found for user ${userId}. Run manual auth first.`);
  }

  const tokenFileContent = fs.readFileSync(tokenFilePath, 'utf-8');
  const tokenData = JSON.parse(tokenFileContent);

  if (!tokenData.token || !tokenData.token.refresh_token) {
    logger.error(`Invalid token file format for user ${userId}`);
    throw new Error(`Invalid token file format for user ${userId}.`);
  }

  logger.info(`Found existing refresh token in ${tokenFilePath}`);
  return tokenData.token.refresh_token;
}

/**
 * API를 호출하여 Access Token을 갱신합니다.
 * (기존의 전역 변수 'refreshToken' 대신 파일에서 직접 읽도록 수정됨)
 */
async function refreshAuthToken(userId) {
  logger.info(`*** REFRESHING ACCESS TOKEN for ${userId} ***`);

  // 1. App Key/Secret 가져오기
  const { clientId, clientSecret } = await getUserAuthConfig(userId);
  const base64Credentials = Buffer.from(`${clientId}:${clientSecret}`).toString("base64");

  // 2. 파일에서 기존 Refresh Token 읽어오기
  let oldRefreshToken;
  try {
    oldRefreshToken = getRefreshTokenFromFile(userId);
  } catch (error) {
    logger.error(`Cannot refresh: ${error.message}`);
    throw error; // 토큰 파일이 없으면 중단
  }

  // 3. 갱신 API 호출
  try {
    const response = await axios({
      method: "POST",
      url: "https://api.schwabapi.com/v1/oauth/token",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Authorization: `Basic ${base64Credentials}`,
      },
      data: `grant_type=refresh_token&refresh_token=${oldRefreshToken}`,
    });

    // 4. 새 토큰 정보 파일에 저장 (기존 함수 재사용)
    saveTokensToFile(userId, response.data);

    logger.info(`Successfully refreshed tokens for ${userId}.`);
    logger.info(`New Access Token (expires in ${response.data.expires_in}s): ${response.data.access_token.substring(0, 10)}...`);

    return response.data; // 갱신된 토큰 데이터 반환

  } catch (error) {
    const errorMsg = error.response ? JSON.stringify(error.response.data) : error.message;
    logger.error(`Error refreshing auth token for ${userId}: ${errorMsg}`);
    // "invalid_grant" 에러는 보통 refresh_token이 만료되었음을 의미
    if (errorMsg.includes("invalid_grant")) {
        logger.warn(`Refresh token for ${userId} may be expired or invalid. Manual re-authentication might be needed.`);
    }
    throw error;
  }
}
async function exchangeCodeForToken(userId, authCode) {
  logger.info(`*** EXCHANGING AUTH CODE FOR TOKEN for ${userId} ***`);

  // 1. App Key/Secret 가져오기
  const { clientId, clientSecret } = await getUserAuthConfig(userId);
  const base64Credentials = Buffer.from(`${clientId}:${clientSecret}`).toString("base64");

  // 2. URL에서 복사한 'code' 값 디코딩 (예: %40 -> @)
  const decodedCode = decodeURIComponent(authCode);
  if (authCode !== decodedCode) {
      logger.info(`Decoded auth code (original: ${authCode.substring(0, 10)}... )`);
  }

  // 3. 토큰 발급 API 호출 (grant_type=authorization_code)
  try {
    const response = await axios({
      method: "POST",
      url: "https://api.schwabapi.com/v1/oauth/token",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Basic ${base64Credentials}`,
      },
      // grant_type과 파라미터가 refresh와 다릅니다.
      data: `grant_type=authorization_code&code=${decodedCode}&redirect_uri=https://127.0.0.1:8182`,
    });

    // 4. 새 토큰 정보 파일에 저장 (기존 함수 재사용)
    saveTokensToFile(userId, response.data);

    logger.info(`Successfully exchanged code and saved new tokens for ${userId}.`);
    logger.info(`New Access Token (expires in ${response.data.expires_in}s): ${response.data.access_token.substring(0, 10)}...`);
    logger.info(`New Refresh Token: ${response.data.refresh_token.substring(0, 10)}...`);

    return response.data; // 성공

  } catch (error) {
    const errorMsg = error.response ? JSON.stringify(error.response.data) : error.message;
    logger.error(`Error exchanging code for ${userId}: ${errorMsg}`);
    throw error;
  }
}
// -----------------------------------------------------------------------------
// 스크립트 실행 (Main)
// -----------------------------------------------------------------------------

async function main() {
  // 커맨드라인에서 사용자 ID를 받습니다.
  // 예: node refreshToken.js my_user_id
  const userIds = await getAllUserIds();

  if (userIds.length === 0) {
    logger.error("No users found in USER_AUTH_CONFIGS");
    process.exit(1);
  }

  logger.info(`Found ${userIds.length} users: ${userIds.join(', ')}`);

  const results = {};
  for (const id of userIds) {
    results[id] = await refreshAuthToken(id);
  }

  // Summary report
  logger.info("\n=========================================");
  logger.info("AUTHENTICATION SUMMARY");
  logger.info("=========================================");

  for (const [id, success] of Object.entries(results)) {
    logger.info(`${id}: ${success ? 'SUCCESS' : 'FAILED'}`);
  }

  const successCount = Object.values(results).filter(Boolean).length;
  logger.info(`\nCompleted: ${successCount}/${userIds.length} users processed successfully`);
  if (successCount !== userIds.length) {
    console.log("처리된 사용자 수와 전체 사용자 수가 일치하지 않습니다. 이메일을 보냅니다.");
    await sendEmailNotification(successCount, userIds.length);
  }

  process.exit();

}

// 스크립트 실행
(async () => {
  // process.argv[0] = node, process.argv[1] = refreshToken.js
  // process.argv[2] 부터 실제 인자가 시작됩니다.
  const args = process.argv.slice(2);

  // 모드 1: 수동 코드 교환 (인자가 2개: userId, code)
  // 예: node refreshToken.js guinea C0.b2F1...
  if (args.length === 2) {
    const userId = args[0];
    const authCode = args[1];

    logger.info(`Running in "Code Exchange" mode for user: ${userId}`);
    try {
      await exchangeCodeForToken(userId, authCode);
      logger.info(`Successfully processed code for ${userId}. Exiting.`);
      process.exit(0); // 성공 종료
    } catch (err) {
      logger.error(`Failed to process code for ${userId}. Exiting with error.`);
      process.exit(1); // 에러 종료
    }
  }
  // 모드 2: 정기 갱신 (인자가 0개 - 기존 방식)
  // 예: node refreshToken.js
  else if (args.length === 0) {
    logger.info('Running in "Refresh All" mode.');
    await main(); // 기존의 '모든 사용자 갱신' 로직 실행
  }
  // 잘못된 사용법
  else {
    logger.error("Invalid usage.");
    logger.info("To refresh all tokens: node refreshToken.js");
    logger.info("To exchange a new code: node refreshToken.js <userId> <auth_code>");
    process.exit(1);
  }
})();