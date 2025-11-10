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
  logger.info(`\nCompleted: ${successCount}/${usersToProcess.length} users processed successfully`);
  if (successCount !== userIds.length) {
    console.log("처리된 사용자 수와 전체 사용자 수가 일치하지 않습니다. 이메일을 보냅니다.");
    await sendEmailNotification(successCount, usersToProcess.length);
  }

  process.exit();

}

// 스크립트 실행
main();