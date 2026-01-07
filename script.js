// Load environment variables but now we'll also read from Python's secret file
const express = require("express");
const axios = require("axios");
const https = require("https");
const fs = require("fs");
//const puppeteer = require("puppeteer");
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());

const path = require("path");
const { exec } = require("child_process");
const { promisify } = require("util");
const execPromise = promisify(exec);
const process = require('process');
// 로거 모듈 가져오기
const logger = require('./logger');
const nodemailer = require("nodemailer");

// Global variables
let authorizationCode;
let accessToken;
let refreshToken;
let server = null;
let app = express();
const takeScreenshots = false; // Set to true to enable screenshots

// Function to get all userIds from USER_AUTH_CONFIGS
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

// Function to read USER_AUTH_CONFIGS from Python file
async function getUserAuthConfig(userId) {
  logger.info(`getUserAuthConfig 함수 실행: 사용자 ID = "${userId}"`);
  try {
    // 따옴표 문제를 해결하기 위해 Python 코드를 파일로 저장하고 실행
    const tempScriptPath = path.join(__dirname, 'temp_get_config.py');

    // 임시 Python 스크립트 작성
    fs.writeFileSync(tempScriptPath, `
import json
import sys
sys.path.append('.')
from library import secret

# Extract credentials for the specified userId
user_id = sys.argv[1]
user_config = secret.USER_AUTH_CONFIGS[user_id]
client_id = user_config["app_key"]
client_secret = user_config["secret"]
callback_url = user_config["callback_url"]
username = user_config["credentials"]["username"]
password = user_config["credentials"]["password"]

# Output as JSON
print(json.dumps({
    "clientId": client_id,
    "clientSecret": client_secret,
    "redirectUri": callback_url,
    "username": username,
    "password": password
}))
`);

    // 파일로 저장된 Python 스크립트 실행
    const { stdout } = await execPromise(`python ${tempScriptPath} "${userId}"`);

    // 임시 파일 삭제
    fs.unlinkSync(tempScriptPath);

    return JSON.parse(stdout.trim());
  } catch (error) {
    logger.error(`Error reading Python credentials: ${error}`);
    throw error;
  }
}

// -----------------------------------------------------------------------------
// Core Authentication Logic
// -----------------------------------------------------------------------------

async function getAuthToken(userId, code, redirectUri) {
  logger.info(`*** EXCHANGING AUTH CODE FOR TOKEN for ${userId} ***`);

  const { clientId, clientSecret } = await getUserAuthConfig(userId);
  const base64Credentials = Buffer.from(`${clientId}:${clientSecret}`).toString("base64");

  try {
    const response = await axios({
      method: "POST",
      url: "https://api.schwabapi.com/v1/oauth/token",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Authorization: `Basic ${base64Credentials}`,
      },
      data: `grant_type=authorization_code&code=${code}&redirect_uri=${redirectUri}`,
    });

    logger.info("*** GOT NEW AUTH TOKEN ***");
    const accessToken = response.data.access_token;
    const refreshToken = response.data.refresh_token;

    // Save tokens to file
    saveTokensToFile(userId, response.data);

    return response.data;
  } catch (error) {
    logger.error(`Error fetching auth token: ${error.response ? JSON.stringify(error.response.data) : error.message}`);
    throw error;
  }
}

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

async function refreshAuthToken(userId) {
  logger.info("*** REFRESHING ACCESS TOKEN ***");

  // Read existing token to get refresh_token
  let refreshToken;
  try {
    const tokenFilePath = path.join(__dirname, 'library', 'tokens', `schwab_token_${userId}.json`);
    if (fs.existsSync(tokenFilePath)) {
      const tokenData = JSON.parse(fs.readFileSync(tokenFilePath, 'utf-8'));
      refreshToken = tokenData.token.refresh_token;
    }
  } catch (e) {
    logger.warn(`Could not read existing token for ${userId}: ${e.message}`);
  }

  if (!refreshToken) {
    logger.error(`No refresh token found for ${userId}. manual login required.`);
    return null;
  }

  const { clientId, clientSecret } = await getUserAuthConfig(userId);
  const base64Credentials = Buffer.from(`${clientId}:${clientSecret}`).toString("base64");

  try {
    const response = await axios({
      method: "POST",
      url: "https://api.schwabapi.com/v1/oauth/token",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Authorization: `Basic ${base64Credentials}`,
      },
      data: `grant_type=refresh_token&refresh_token=${refreshToken}`,
    });

    saveTokensToFile(userId, response.data);
    return response.data;
  } catch (error) {
    logger.error(`Error refreshing auth token: ${error.response ? JSON.stringify(error.response.data) : error.message}`);
    throw error;
  }
}

async function getAccounts(userId) {
  logger.info(`*** API TEST CALL: ACCOUNTS for ${userId} ***`);

  let accessToken;
  try {
    const tokenFilePath = path.join(__dirname, 'library', 'tokens', `schwab_token_${userId}.json`);
    const tokenData = JSON.parse(fs.readFileSync(tokenFilePath, 'utf-8'));
    accessToken = tokenData.token.access_token;
  } catch (e) {
    logger.error("Failed to read access token for account call");
    return;
  }

  const res = await axios({
    method: "GET",
    url: "https://api.schwabapi.com/trader/v1/accounts?fields=positions",
    headers: {
      "Accept-Encoding": "application/json",
      "Authorization": "Bearer " + accessToken,
    },
  });

  logger.info(`Successfully fetched ${res.data.length} accounts.`);
}

// -----------------------------------------------------------------------------
// Robust Puppeteer Automation (System Chrome + Interception)
// -----------------------------------------------------------------------------

async function randomDelay(min, max) {
  return new Promise(r => setTimeout(r, min + Math.random() * (max - min)));
}

async function automateLogin(config) {
  const EXECUTABLE_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const OAUTH_URL = `https://api.schwabapi.com/v1/oauth/authorize?response_type=code&client_id=${config.clientId}&scope=readonly&redirect_uri=${config.redirectUri}`;

  logger.info('[REAL-AUTO] Launching System Chrome with Interception...');

  const browser = await puppeteer.launch({
    headless: false,
    executablePath: EXECUTABLE_PATH,
    userDataDir: './chrome_profile_real', // Keeps session alive
    args: ['--no-sandbox', '--disable-blink-features=AutomationControlled', '--window-position=0,0'],
    ignoreDefaultArgs: ['--enable-automation'],
    defaultViewport: null
  });

  try {
    const pages = await browser.pages();
    const page = pages.length > 0 ? pages[0] : await browser.newPage();

    // *** INTERCEPTION LOGIC ***
    await page.setRequestInterception(true);
    let capturedCode = null;

    page.on('request', request => {
      const url = request.url();
      if (url.startsWith('https://127.0.0.1') || url.startsWith('http://127.0.0.1')) {
        // logger.info('Intercepted Redirect URL:', url);
        try {
          const urlObj = new URL(url);
          const code = urlObj.searchParams.get('code');
          if (code) {
            logger.info('SUCCESS! OAuth Code found via Network Interception.');
            capturedCode = code;
          }
        } catch (e) { }
        request.abort();
      } else {
        request.continue();
      }
    });

    logger.info('Navigating to OAuth URL...');
    await page.goto(OAUTH_URL, { waitUntil: 'networkidle2' });

    // --- LOGIN ---
    logger.info('Checking Login Page...');
    try {
      const loginSel = '#loginIdInput';
      if (await page.$(loginSel) !== null) {
        logger.info('Login form found. Typing credentials...');
        await page.type(loginSel, config.username, { delay: 50 });
        await page.type('#passwordInput', config.password, { delay: 50 });
        await page.click('#btnLogin');
      } else {
        logger.info('Login form not detected (Likely already logged in).');
      }
    } catch (e) { }

    logger.info('Entering URL monitoring loop...');
    const startTime = Date.now();
    const timeout = 60000; // 60 seconds timeout

    while (Date.now() - startTime < timeout) {
      if (capturedCode) {
        await browser.close();
        return capturedCode;
      }

      const currentUrl = page.url();
      let bodyText = '';
      try { bodyText = await page.evaluate(() => document.body.innerText.toLowerCase()); } catch (e) { }

      // --- TERMS & POPUP ---
      if (currentUrl.includes('cag') || (bodyText.includes('terms') && bodyText.includes('agree'))) {
        try {
          // Click Accept button in modal if exists
          const modalClicked = await page.evaluate(() => {
            const buttons = Array.from(document.querySelectorAll('button, a, div[role="button"]'));
            const target = buttons.find(b => {
              const t = b.innerText.trim().toLowerCase();
              const rect = b.getBoundingClientRect();
              const visible = rect.width > 0 && rect.height > 0;
              return t === 'accept' && visible;
            });
            if (target) { target.click(); return true; }
            return false;
          });
          if (modalClicked) {
            logger.info('Clicked Accept in modal');
            await randomDelay(1000, 2000);
            continue;
          }

          // Checkboxes
          await page.evaluate(() => {
            document.querySelectorAll('input[type="checkbox"]').forEach(b => { if (!b.checked) b.click(); });
          });

          // Continue button
          const continueClicked = await page.evaluate(() => {
            const buttons = Array.from(document.querySelectorAll('button, a, input[type="submit"]'));
            const target = buttons.find(b => {
              const txt = b.innerText.toLowerCase();
              return (txt.includes('continue') || txt.includes('agree')) && !b.disabled;
            });
            if (target) { target.click(); return true; }
            return false;
          });
          if (continueClicked) logger.info('Clicked Continue on Terms');
        } catch (e) { }
        await randomDelay(2000, 3000);
      }

      // --- ACCOUNT SELECTION ---
      else if (currentUrl.includes('account') || bodyText.includes('select the accounts')) {
        await page.evaluate(() => {
          document.querySelectorAll('input[type="checkbox"]').forEach(b => { if (!b.checked) b.click(); });
        });
        await page.evaluate(() => {
          const buttons = Array.from(document.querySelectorAll('button'));
          const target = buttons.find(b => {
            const t = b.innerText.toLowerCase();
            return (t.includes('authorize') || t.includes('continue') || t.includes('allow')) && !b.disabled;
          });
          if (target) { target.click(); }
        });
        logger.info('Handled Account Selection');
        await randomDelay(2000, 4000);
      }

      // --- CONFIRMATION / DONE ---
      else if (currentUrl.includes('confirmation') || bodyText.includes('done') || bodyText.includes('success')) {
        await page.evaluate(() => {
          const buttons = Array.from(document.querySelectorAll('button, a'));
          const target = buttons.find(b => {
            const t = b.innerText.toLowerCase();
            return (t.includes('done') || t.includes('close') || t.includes('finish') || t.includes('continue')) && !b.disabled;
          });
          if (target) { target.click(); }
        });
        logger.info('Handled Confirmation');
        await randomDelay(2000, 4000);
      }

      await new Promise(r => setTimeout(r, 1000));
    }

    await browser.close();
    if (capturedCode) return capturedCode;
    throw new Error("Timeout waiting for OAuth code");

  } catch (error) {
    logger.error(`Error during automation: ${error}`);
    await browser.close();
    throw error;
  }
}

async function processUser(userId) {
  logger.info(`\n=========================================`);
  logger.info(`PROCESSING USER: ${userId}`);
  logger.info(`=========================================\n`);

  try {
    const config = await getUserAuthConfig(userId);

    // 1. Get Code via Puppeteer
    const code = await automateLogin(config);

    // 2. Exchange Code for Tokens
    if (code) {
      await getAuthToken(userId, code, config.redirectUri);
      logger.info(`Authorization process completed successfully for ${userId}.`);

      // 3. Verify
      await getAccounts(userId);
      return true;
    } else {
      logger.error('Failed to obtain auth code.');
      return false;
    }

  } catch (error) {
    logger.error(`Error processing user ${userId}: ${error.message}`);
    await sendErrorToEmail(error.message);
    return false;
  }
}


// Main function to coordinate the server and Puppeteer for all users
async function main() {
  logger.info("Starting Schwab authentication script");

  // Get all userIds from USER_AUTH_CONFIGS
  const userIds = await getAllUserIds();

  if (userIds.length === 0) {
    logger.error("No users found in USER_AUTH_CONFIGS");
    process.exit(1);
  }

  logger.info(`Found ${userIds.length} users: ${userIds.join(', ')}`);

  // Optional: filter users from command line arguments
  let usersToProcess = userIds;
  if (process.argv.length >= 3) {
    const requestedUsers = process.argv.slice(2);
    usersToProcess = userIds.filter(id => requestedUsers.includes(id));
    logger.info(`Processing only requested users: ${usersToProcess.join(', ')}`);
  }

  if (usersToProcess.length === 0) {
    logger.error("No matching users found to process");
    process.exit(1);
  }

  // Process each user sequentially
  const results = {};
  for (const id of usersToProcess) {
    results[id] = await processUser(id);
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
  if (successCount !== usersToProcess.length) {
    console.log("처리된 사용자 수와 전체 사용자 수가 일치하지 않습니다. 이메일을 보냅니다.");
    await sendEmailNotification(successCount, usersToProcess.length);
  }

  process.exit();
}
async function getEmailSecretsFromPython() {
  const tempEmailScriptPath = path.join(__dirname, 'temp_get_email_secrets.py');

  // 임시 Python 스크립트 작성
  fs.writeFileSync(tempEmailScriptPath, `
import json
import sys
sys.path.append('.')
from library import secret

email_secrets = {
    "alert_email": secret.alert_email,
    "alert_password": secret.alert_password,
    "alerted_email": secret.alerted_email
}
print(json.dumps(email_secrets))
`);

  try {
    const { stdout, stderr } = await execPromise(`python ${tempEmailScriptPath}`);
    // 임시 파일 삭제
    fs.unlinkSync(tempEmailScriptPath);

    return JSON.parse(stdout.trim()); // JSON 파싱 후 반환
  } catch (error) {
    console.error('Python 스크립트 실행 또는 출력 파싱 실패:', error);
    throw error;
  }
}
async function sendEmailNotification(successCount, totalUsers) {
  const nodemailer = require('nodemailer');
  let emailSecrets;

  try {
    emailSecrets = await getEmailSecretsFromPython();
  } catch (error) {
    console.error('이메일 비밀 정보를 가져오는 데 실패했습니다. 이메일 전송을 중단합니다.', error);
    return;
  }

  let transporter = nodemailer.createTransport({
    service: 'gmail',
    auth: {
      user: emailSecrets.alert_email,
      pass: emailSecrets.alert_password
    }
  });

  // 메일 옵션 설정
  let mailOptions = {
    from: emailSecrets.alert_email,
    to: emailSecrets.alerted_email,
    subject: '작업 완료 알림: 사용자 처리 불일치',
    text: `성공적으로 처리된 사용자 수에 불일치가 있습니다.\n\n` +
      `총 사용자 수: ${totalUsers}\n` +
      `성공적으로 처리된 사용자 수: ${successCount}\n\n`
  };

  try {
    await transporter.sendMail(mailOptions);
    console.log('이메일이 성공적으로 전송되었습니다.');
  } catch (error) {
    console.error('이메일 전송 중 오류 발생:', error);
  }
}
async function sendErrorToEmail(message) {
  const nodemailer = require('nodemailer');
  let emailSecrets;

  try {
    emailSecrets = await getEmailSecretsFromPython();
  } catch (error) {
    console.error('이메일 비밀 정보를 가져오는 데 실패했습니다. 이메일 전송을 중단합니다.', error);
    return;
  }

  let transporter = nodemailer.createTransport({
    service: 'gmail',
    auth: {
      user: emailSecrets.alert_email,
      pass: emailSecrets.alert_password
    }
  });

  // 메일 옵션 설정
  let mailOptions = {
    from: emailSecrets.alert_email,
    to: emailSecrets.alerted_email,
    subject: 'token 발행 중 에러',
    text: `${message}\n`
  };

  try {
    await transporter.sendMail(mailOptions);
    console.log('이메일이 성공적으로 전송되었습니다.');
  } catch (error) {
    console.error('이메일 전송 중 오류 발생:', error);
  }
}
// Run the main function
main().catch(error => {
  logger.error(`Fatal error in main process: ${error}`);
  process.exit(1);
});