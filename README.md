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

### 거래 규칙 입력 방식
- **한계값**: limit_value (숫자 입력)
- **한계값 종류**: limit_type (가격/퍼센트 선택)
- 예시: [ 100.00 ][가격] 또는 [ 5.0 ][%]

### DB 구조 예시
| id | ... | limit_value | limit_type | ... |
|----|-----|-------------|-----------|-----|
| 1  | ... | 100.00      | price     | ... (미국 주식) |
| 2  | ... | 5.00        | percent   | ... (미국 주식) |
| 3  | ... | 50000       | price     | ... (한국 주식) |
| 4  | ... | 5.00        | percent   | ... (한국 주식) |

### 거래 로직
- limit_type이 'price'면 limit_value를 가격으로 사용
- limit_type이 'percent'면 average_price의 limit_value% 기준으로 매수/매도
  - 매수: average_price * (1 - limit_value/100)
  - 매도: average_price * (1 + limit_value/100)
  - average_price가 0이면 현재가로 매수만, 매도는 하지 않음

### 데이터 타입 차이
- **미국 주식**: limit_value는 DECIMAL(10,2) - 소수점 가격 지원
- **한국 주식**: limit_value는 DECIMAL(10) - 정수 가격만 지원 (소수점 없음)

### 사용 방법
1. 거래 규칙 추가 시 한계값 입력란에 숫자 입력, 옆 드롭다운에서 "가격" 또는 "%" 선택
2. 시스템이 자동으로 해당 기준에 따라 거래 조건을 계산

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
