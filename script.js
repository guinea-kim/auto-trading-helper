// Load environment variables but now we'll also read from Python's secret file
const express = require("express");
const axios = require("axios");
const https = require("https");
const fs = require("fs");
const puppeteer = require("puppeteer");
const path = require("path");
const { exec } = require("child_process");
const { promisify } = require("util");
const execPromise = promisify(exec);

const app = express();

// Global variables
let authorizationCode;
let accessToken;
let refreshToken;
let server = null;
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
    console.error("Error reading Python userIds:", error);
    throw error;
  }
}

// Function to read USER_AUTH_CONFIGS from Python file
async function getUserAuthConfig(userId) {
  console.log(`getUserAuthConfig 함수 실행: 사용자 ID = "${userId}"`);
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
    console.error("Error reading Python credentials:", error);
    throw error;
  }
}

// Start the HTTPS server
function startServer(userId, redirectUri) {
  return new Promise((resolve, reject) => {
    const httpsOptions = {
      key: fs.readFileSync("server-key.pem"),
      cert: fs.readFileSync("server-cert.pem"),
    };

    server = https.createServer(httpsOptions, app);

    // Listen for GET requests on /
    app.get("/", (req, res) => {
      // Extract URL parameters
      authorizationCode = req.query.code;

      if (!authorizationCode) {
        return res.status(400).send("Missing authorization code");
      }

      // Call the getAuthToken function
      getAuthToken(userId, redirectUri)
        .then((tokens) => {
          // Send response to client
          res.send("Authorization process completed. Check the logs for details.");
          resolve(tokens); // Resolve with the tokens once received
        })
        .catch(reject);
    });

    // Start the server
    server.listen(8182, () => {
      console.log("Express server is listening on port 8182");
    });

    // Set a timeout to close the server after 60 seconds if no authorization code is received
    setTimeout(() => {
      if (!authorizationCode) {
        console.log("Timeout: No authorization code received. Shutting down the server.");
        server.close(() => resolve(null));
      }
    }, 60000);
  });
}

// Function to fetch the auth token
async function getAuthToken(userId, redirectUri) {
  const { clientId, clientSecret } = await getUserAuthConfig(userId);

  // Base64 encode the client_id:client_secret
  const base64Credentials = Buffer.from(`${clientId}:${clientSecret}`).toString("base64");

  try {
    const response = await axios({
      method: "POST",
      url: "https://api.schwabapi.com/v1/oauth/token",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Authorization: `Basic ${base64Credentials}`,
      },
      data: `grant_type=authorization_code&code=${authorizationCode}&redirect_uri=${redirectUri}`,
    });

    console.log("*** GOT NEW AUTH TOKEN ***");

    // Log the refresh_token and access_token before exiting
    accessToken = response.data.access_token;
    refreshToken = response.data.refresh_token;
    console.log("Access Token:", accessToken);
    console.log("Refresh Token:", refreshToken);

    // Save tokens to the specified path
    saveTokensToFile(userId, response.data);

    return response.data;
  } catch (error) {
    console.error("Error fetching auth token:", error);
    throw error;
  }
}

// Function to save tokens to file
function saveTokensToFile(userId, tokenData) {
  // Create tokens directory if it doesn't exist
  const tokensDir = path.join(__dirname, 'library', 'tokens');
  if (!fs.existsSync(tokensDir)) {
    fs.mkdirSync(tokensDir, { recursive: true });
  }

  // Save tokens to file
  const tokenFilePath = path.join(tokensDir, `schwab_token_${userId}.json`);
  const tokenContent = JSON.stringify({
    access_token: tokenData.access_token,
    refresh_token: tokenData.refresh_token,
    expires_in: tokenData.expires_in,
    scope: tokenData.scope,
    token_type: tokenData.token_type,
    timestamp: new Date().toISOString()
  }, null, 2);

  fs.writeFileSync(tokenFilePath, tokenContent);
  console.log(`Tokens saved to ${tokenFilePath}`);
}

// Function to automate the login process using Puppeteer
async function automateLogin(config) {
  const browser = await puppeteer.launch({
    headless: false, // May need to set to false in the future to avoid automation detection
    ignoreHTTPSErrors: true,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-blink-features=AutomationControlled", // To make automation less detectable
      "--ignore-certificate-errors", // Ignore all certificate errors
      "--disable-web-security", // Optionally disable web security
      "--disable-features=SecureDNS,EnableDNSOverHTTPS", // Disable Secure DNS and DNS-over-HTTPS
    ],
  });

  const page = await browser.newPage();

  // Set user agent to avoid detection
  await page.setUserAgent(
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
  );

  try {
    // Go to the OAuth authorization URL
    await page.goto(
      `https://api.schwabapi.com/v1/oauth/authorize?response_type=code&client_id=${config.clientId}&scope=readonly&redirect_uri=https://127.0.0.1:8182`,
      { waitUntil: "load" }
    );

    // Conditionally take a screenshot after loading the page
    if (takeScreenshots) await page.screenshot({ path: "login-page.png" });
    console.log("Navigation to login page successful.");

    // Wait for the login ID input field to be visible
    await page.waitForSelector("#loginIdInput", { visible: true });
    console.log("Login ID input is visible.");

    // Wait for the password input field to be visible
    await page.waitForSelector("#passwordInput", { visible: true });
    console.log("Password input is visible.");

    // Fill in the login ID with a slower typing speed
    await page.type("#loginIdInput", config.username, { delay: 100 });
    console.log("Login ID entered.");

    // Fill in the password with a slower typing speed
    await page.type("#passwordInput", config.password, { delay: 100 });
    console.log("Password entered.");

    // Conditionally take a screenshot after filling in the form
    if (takeScreenshots) await page.screenshot({ path: "filled-form.png" });

    // Click the login button
    await page.click("#btnLogin");
    console.log("Login button clicked.");

    // Wait for navigation to the terms acceptance page
    await page.waitForNavigation({ waitUntil: "load" });
    console.log("Navigation to terms page successful.");

    // Conditionally take a screenshot after navigating to the terms page
    if (takeScreenshots) await page.screenshot({ path: "terms-page.png" });

    // Wait for the terms checkbox to be visible
    await page.waitForSelector("#acceptTerms", { visible: true });
    console.log("Terms checkbox is visible.");

    // Check the terms checkbox
    await page.click("#acceptTerms");
    console.log("Terms checkbox clicked.");

    // Conditionally take a screenshot after checking the checkbox
    if (takeScreenshots) await page.screenshot({ path: "terms-checkbox.png" });

    // Click the "Continue" button
    await page.click("#submit-btn");
    console.log("Continue button clicked.");

    // Wait for the modal dialog to appear
    await page.waitForSelector("#agree-modal-btn-", { visible: true });
    console.log("Modal dialog is visible.");

    // Conditionally take a screenshot of the modal
    if (takeScreenshots) await page.screenshot({ path: "modal-dialog.png" });

    // Click the "Accept" button in the modal
    await page.click("#agree-modal-btn-");
    console.log("Modal 'Accept' button clicked.");

    // Wait for navigation to the accounts page
    await page.waitForNavigation({ waitUntil: "load" });
    console.log("Navigation to accounts page successful.");

    // Wait for checkbox's to appear
    await page.waitForSelector("input[type='checkbox']", { visible: true });

    // Conditionally take a screenshot after navigating to accounts page
    if (takeScreenshots) await page.screenshot({ path: "accounts-page.png" });

    // Make sure all accounts are checked (if they aren't by default)
    const accountsChecked = await page.$eval("input[type='checkbox']", (checkbox) => checkbox.checked);
    if (!accountsChecked) {
      await page.click("input[type='checkbox']");
      console.log("Account checkbox clicked.");
    } else {
      console.log("Account checkbox was already checked.");
    }

    // Conditionally take a screenshot after ensuring accounts are checked
    if (takeScreenshots) await page.screenshot({ path: "accounts-checked.png" });

    // Click the "Continue" button on the accounts page
    await page.click("#submit-btn");
    console.log("Continue button clicked on accounts page.");

    // Wait for navigation to the confirmation page
    await page.waitForNavigation({ waitUntil: "load" });
    console.log("Navigation to confirmation page successful.");

    // Conditionally take a screenshot after navigating to the confirmation page
    if (takeScreenshots) await page.screenshot({ path: "confirmation-page.png" });

    // Click the "Done" button on the confirmation page
    await page.click("#cancel-btn");
    console.log("Done button clicked.");

    // Wait for the final redirect to your HTTPS server
    await page.waitForNavigation({ waitUntil: "load" });
    console.log("Redirect to HTTPS server successful.");

    // Conditionally take a screenshot after the final redirect
    if (takeScreenshots) await page.screenshot({ path: "final-redirect.png" });

    console.log("Puppeteer automation completed.");
  } catch (error) {
    console.error("Error during automation:", error);
  } finally {
    await browser.close();
  }
}

async function refreshAuthToken(userId) {
  console.log("*** REFRESHING ACCESS TOKEN ***");

  const { clientId, clientSecret } = await getUserAuthConfig(userId);

  // Base64 encode the client_id:client_secret
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

    // Log the new refresh_token and access_token
    accessToken = response.data.access_token;
    refreshToken = response.data.refresh_token;
    console.log("New Refresh Token:", response.data.refresh_token);
    console.log("New Access Token:", response.data.access_token);

    // Save updated tokens to file
    saveTokensToFile(userId, response.data);

    return response.data;
  } catch (error) {
    console.error("Error refreshing auth token:", error.response ? error.response.data : error.message);
    throw error;
  }
}

async function getAccounts() {
  console.log("*** API TEST CALL: ACCOUNTS ***");

  const res = await axios({
    method: "GET",
    url: "https://api.schwabapi.com/trader/v1/accounts?fields=positions",
    contentType: "application/json",
    headers: {
      "Accept-Encoding": "application/json",
      Authorization: "Bearer " + accessToken,
    },
  });

  console.log(res.data);
}
// 서버 종료 함수 추가
function closeServer() {
  return new Promise((resolve) => {
    if (server && server.listening) {
      console.log("Closing the server...");
      server.close(() => {
        console.log("Server closed successfully");
        resolve();
      });
    } else {
      console.log("Server was not running");
      resolve();
    }
  });
}
// Function to process a single user
async function processUser(userId) {
  console.log(`\n=========================================`);
  console.log(`PROCESSING USER: ${userId}`);
  console.log(`=========================================\n`);

  try {
    // Get auth configuration for the specified userId
    const config = await getUserAuthConfig(userId);

    // Start the HTTPS server
    const serverPromise = startServer(userId, 'https://127.0.0.1:8182');

    // Run Puppeteer automation
    await automateLogin(config);

    // Wait for the server to finish (either timeout or successful authorization)
    const tokens = await serverPromise;
    await closeServer();
    if (tokens) {
      console.log(`Authorization process completed successfully for ${userId}.`);

      // Test api with new accessToken
      await getAccounts();

      // Test refreshToken
      await refreshAuthToken(userId);

      // Test api with refreshed accessToken
      await getAccounts();

      return true;
    } else {
      console.log(`No tokens received within the timeout period for ${userId}.`);
      return false;
    }
  } catch (error) {
    console.error(`Error processing user ${userId}:`, error);
    await closeServer();
    return false;
  }
}

// Main function to coordinate the server and Puppeteer for all users
async function main() {
  // Get all userIds from USER_AUTH_CONFIGS
  const userIds = await getAllUserIds();

  if (userIds.length === 0) {
    console.error("No users found in USER_AUTH_CONFIGS");
    process.exit(1);
  }

  console.log(`Found ${userIds.length} users: ${userIds.join(', ')}`);

  // Optional: filter users from command line arguments
  let usersToProcess = userIds;
  if (process.argv.length >= 3) {
    const requestedUsers = process.argv.slice(2);
    usersToProcess = userIds.filter(id => requestedUsers.includes(id));
    console.log(`Processing only requested users: ${usersToProcess.join(', ')}`);
  }

  if (usersToProcess.length === 0) {
    console.error("No matching users found to process");
    process.exit(1);
  }

  // Process each user sequentially
  const results = {};
  for (const id of usersToProcess) {
    results[id] = await processUser(id);
  }

  // Summary report
  console.log("\n=========================================");
  console.log("AUTHENTICATION SUMMARY");
  console.log("=========================================");

  for (const [id, success] of Object.entries(results)) {
    console.log(`${id}: ${success ? 'SUCCESS' : 'FAILED'}`);
  }

  const successCount = Object.values(results).filter(Boolean).length;
  console.log(`\nCompleted: ${successCount}/${usersToProcess.length} users processed successfully`);

  process.exit();
}

// Run the main function
main().catch(error => {
  console.error("Fatal error in main process:", error);
  process.exit(1);
});