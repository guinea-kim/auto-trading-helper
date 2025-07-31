from library import alert
import json
import time
import requests
from pathlib import Path
from library import secret
from library.mysql_helper import DatabaseHandler
from library.secret import USER_AUTH_CONFIGS_KR

# Timeout settings for API requests (in seconds)
REQUEST_TIMEOUT = 30

def MakeToken(user):
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": USER_AUTH_CONFIGS_KR[user]['app_key'],
        "appsecret": USER_AUTH_CONFIGS_KR[user]['secret']
    }

    PATH = "oauth2/tokenP"
    URL = f"{secret.KR_REAL_URL}/{PATH}"
    res = requests.post(URL, headers=headers, data=json.dumps(body), timeout=REQUEST_TIMEOUT)

    if res.status_code == 200:
        my_token = res.json()["access_token"]

        # 빈 딕셔너리를 선언합니다!
        dataDict = dict()

        # 해당 토큰을 파일로 저장해 둡니다!
        dataDict["authorization"] = my_token
        lib_dir = Path(__file__).parent
        token_path = str(lib_dir / 'tokens' / f'kr_token_{user}.json')
        with open(token_path, 'w') as outfile:
            json.dump(dataDict, outfile)

        print("TOKEN : ", my_token)
    else:
        print('Get Authentification token fail!')

time_info = time.gmtime()
m_hour = time_info.tm_hour

alert.SendMessage("Generate Korea Token")
db_handler = DatabaseHandler(secret.db_name_kr)
users = db_handler.get_users()
for user in users:
    MakeToken(user)


