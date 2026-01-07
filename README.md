# auto-trading-helper

## set up vitual env
```
conda create -n auto-trading-helper python=3.10
conda activate auto-trading-helper
```

if you have trouble, remove env with below and recreate

```
conda deactivate
conda env remove --name auto-trading-helper 
```

## install prerequiste
```pip install -r requirements.txt```

## set up library/secret.py
### set up alert
#### sender
```
alert_email='@gmail.com'
alert_password=''
```
#### how to create gmail app password
1. Sign into your Google Account.
2. Navigate to the Security section.
3. Under “Signing in to Google,” find and click on “App Passwords.
4. You might need to sign in again. If you don’t see “App Passwords,” ensure that 2FA is enabled.
5. At the bottom, select ‘Mail’ under ‘Select app’ and choose the device you’re using under ‘Select device’.
6. Click on ‘Generate’. Your app password will appear.
#### receiver
```
alerted_email=''
```
* 카카오 메일을 사용한다면 notification 설정으로 카카오톡 알림을 받을 수 있다.

### set up db connection
```
db_id = ''
db_ip = ''
db_passwd = ''
db_port = '3306'
db_name = ''
```
### set up viewer
```
app_secret = 'default'
```

### set up schwab credential 
```
USER_AUTH_CONFIGS = {
    'user_id': {
        'app_key': '',
        'secret': '',
        'callback_url': 'https://127.0.0.1:8182',
        "credentials": {  
            "username": "schwab_user_id",
            "password": "schwab_password"
        }
    }
```
## 새로운 기능: 한계값/퍼센트 통합 입력 방식

상세한 거래 규칙 입력 방식, DB 구조, 거래 로직 등에 대한 내용은 [DATABASE.md](DATABASE.md) 파일을 참고해주세요.

---

## Set up Automated schwab login
### OpenSSL and Certificates

Since the Express server requires HTTPS, you will need to generate a self-signed certificate using OpenSSL. Follow these steps to generate the necessary SSL key and certificate.

1. Install OpenSSL: If OpenSSL is not already installed, you can download and install it from OpenSSL's official website.

2. Generate a Private Key: Run the following command to generate a private key (server-key.pem):

```openssl genrsa -out server-key.pem 2048```

3. Create a Self-Signed Certificate: Run the following command to generate a self-signed certificate (server-cert.pem):

```openssl req -new -x509 -key server-key.pem -out server-cert.pem -days 365```

or

```openssl req -new -x509 -key server-key.pem -out server-cert.pem -days 365 -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"```

4. Place the Key and Certificate: Ensure that the generated server-key.pem and server-cert.pem are in the root directory of your project.

These certificates will allow your local HTTPS server to run securely. Note that since they are self-signed, your browser might show a security warning, which can be bypassed during development.

### Usage
Starting the Server and Running Puppeteer Automation
1. install node.js

```conda install -c conda-forge nodejs=22.13.0```
* for mac m1,m2 install .pkg of arm64 nodejs 
2. Install Dependencies: Run the following command to install all required dependencies:

```npm install```

2-1. trouble shooting for
```Error: Could not find Chrome (ver. 134.0.6998.35). ```

```npx puppeteer browsers install chrome```
``` npm i puppeteer --puppeteer-product=chrome --puppeteer-platform=mac --puppeteer-arch=arm64```
3. Run the Project: Start the project with the following command from the terminal:

```npm start```

4. Cron excution every Sunday

```
0 0 * * 0 cd /path/to/your/project && /usr/local/bin/node /path/to/your/project/script.js
```

## Transaction History Tracking
Since Jan 2026, we track the detailed transaction history for accurate contribution calculation.

1.  **Initialize DB**:
    ```bash
    python scripts/setup/init_contribution_history_db.py
    ```

2.  **Daily Update**:
    The cron job runs `scripts/transactions/update_transactions.py` daily to fetch recent transactions from Schwab.

3.  **Manual Entry**:
    If you need to manually add a missing transaction (e.g., Roth conversion):
    ```bash
    # Open scripts/transactions/manual_insert.py, edit target_account/date/amount, then run:
    python scripts/transactions/manual_insert.py
    ```
