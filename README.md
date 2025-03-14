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
```npx puppeteer browsers install chrome```
``` npm i puppeteer --puppeteer-product=chrome --puppeteer-platform=mac --puppeteer-arch=arm64```
3. Run the Project: Start the project with the following command from the terminal:

```npm start```

4. Cron excution every Sunday

```
0 0 * * 0 cd /path/to/your/project && /usr/local/bin/node /path/to/your/project/script.js
```
