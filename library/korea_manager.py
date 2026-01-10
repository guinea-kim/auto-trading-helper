from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import logging
from datetime import datetime
import json
from typing import Dict, Optional, Tuple
import time
from math import ceil
import requests

# Timeout settings for API requests (in seconds)
REQUEST_TIMEOUT = 30

from library.secret import USER_AUTH_CONFIGS_KR
from library import secret
from library.mysql_helper import DatabaseHandler
from library.clock import Clock

class KoreaManager:
    def __init__(self, user_id: str, clock: Clock = None):
        self.user_id = user_id
        self.auth_config = USER_AUTH_CONFIGS_KR[user_id]
        self.app_key = USER_AUTH_CONFIGS_KR[self.user_id]['app_key']
        self.secret = USER_AUTH_CONFIGS_KR[self.user_id]['secret']
        self.product = USER_AUTH_CONFIGS_KR[self.user_id]['product_cd']
        self.hash_dict = None
        self.logger = logging.getLogger(__name__)
        self.clock = clock or Clock()

        lib_dir = Path(__file__).parent
        self.token_path = str(lib_dir / 'tokens' / f'kr_token_{user_id}.json')
        self.token = None
        self.today_open = None
        self.db_handler = DatabaseHandler(secret.db_name_kr)
    def get_hashs(self):
        user_account = self.db_handler.get_user_accounts(self.user_id)
        accounts = {}
        for account in user_account:
            accounts[account['account_number']] = account['account_number']
        return accounts
    def get_token(self):
        if self.token is None:
            try:
                # 이 부분이 파일을 읽어서 딕셔너리에 넣어주는 로직입니다.
                with open(self.token_path, 'r') as json_file:
                    dataDict = json.load(json_file)
                self.token = dataDict['authorization']
            except Exception as e:
                print("Exception by First")
        return self.token
    def IsTodayOpenCheck(self):
        time.sleep(0.2)

        now_time = self.clock.now(ZoneInfo('Asia/Seoul'))
        formattedDate = now_time.strftime("%Y%m%d")

        PATH = "uapi/domestic-stock/v1/quotations/chk-holiday"
        URL = f"{secret.KR_REAL_URL}/{PATH}"

        headers = self._get_base_headers("CTCA0903R")
        params = {
            "BASS_DT": formattedDate,
            "CTX_AREA_NK": "",
            "CTX_AREA_FK": ""
        }

        # 호출
        res = requests.get(URL, headers=headers, params=params, timeout=REQUEST_TIMEOUT)

        if res.status_code == 200 and res.json()["rt_cd"] == '0':
            DayList = res.json()['output']

            IsOpen = 'Y'
            for dayInfo in DayList:
                if dayInfo['bass_dt'] == formattedDate:
                    IsOpen = dayInfo['opnd_yn']
                    break

            return IsOpen
        else:
            print("Error Code : " + str(res.status_code) + " | " + res.text)
            return res.json()["msg_cd"]
    def get_market_hours(self):
        now_time = self.clock.now(ZoneInfo('Asia/Seoul'))
        date_week = now_time.weekday()

        IsOpen = False

        # 주말은 무조건 장이 안열리니 False 리턴!
        if date_week == 5 or date_week == 6:
            IsOpen = False
        else:
            # 9시 부터 3시 반
            if now_time.hour >= 9 and now_time.hour <= 15:
                IsOpen = True

                if now_time.hour == 15 and now_time.minute > 30:
                    IsOpen = False

        # 평일 장 시간이어도 공휴일같은날 장이 안열린다.
        if IsOpen == True:
            print("Time is OK... but one more checked!!!")
            if self.today_open is None:
                if self.IsTodayOpenCheck() == 'N':
                    self.today_open = False
                else:
                    self.today_open = True
            return self.today_open
        else:
            print("Time is NO!!!")
            return False

    def _get_base_headers(self, tr_id, include_custtype=False):
        """기본 헤더 생성 - custtype 선택적 추가"""
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.get_token()}",
            "appKey": self.app_key,
            "appSecret": self.secret,
            "tr_id": tr_id
        }

        if include_custtype:
            headers["custtype"] = "P"

        return headers
    def _get_base_data(self, account, stockcode, quantity, price, dvsn):
        return {
            "CANO": account,
            "ACNT_PRDT_CD": self.product,
            "PDNO": stockcode,
            "ORD_DVSN": dvsn,
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(price),
        }
    def get_positions(self, account: str) -> Dict[str, float]:
        """Get account positions"""
        PATH = "uapi/domestic-stock/v1/trading/inquire-balance"
        URL = f"{secret.KR_REAL_URL}/{PATH}"

        positions = {}
        fk_key, nk_key, prev_nk_key, tr_cont = "", "", "", ""
        count = 0

        # 드물지만 보유종목이 많으면 연속조회를 위한 반복 처리
        while True:
            time.sleep(0.2)

            headers = self._get_base_headers("TTTC8434R", include_custtype=True)
            headers["tr_cont"] = tr_cont

            params = {
                "CANO": account,
                "ACNT_PRDT_CD": self.product,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "01",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "00",
                "CTX_AREA_FK100": fk_key,
                "CTX_AREA_NK100": nk_key
            }

            res = requests.get(URL, headers=headers, params=params, timeout=REQUEST_TIMEOUT)

            # 연속 조회 처리
            tr_cont = "N" if res.headers['tr_cont'] in ["M", "F"] else ""

            if res.status_code == 200 and res.json()["rt_cd"] == '0':
                nk_key = res.json()['ctx_area_nk100'].strip()
                fk_key = res.json()['ctx_area_fk100'].strip()

                # 보유 종목 추가
                for stock in res.json()['output1']:
                    if int(stock['hldg_qty']) > 0:
                        positions[stock['pdno']] = int(stock['hldg_qty'])

                # 연속 조회 여부 확인
                if prev_nk_key == nk_key or not nk_key:
                    break
                prev_nk_key = nk_key
            else:
                print(f"Error Code: {res.status_code} | {res.text}")
                if res.json().get("msg_cd") == "EGW00123" or count > 10:
                    break
                count += 1

        return positions

    def get_positions_result(self, account: str) -> Dict[str, Dict[str, float]]:
        PATH = "uapi/domestic-stock/v1/trading/inquire-balance"
        URL = f"{secret.KR_REAL_URL}/{PATH}"

        positions = {}
        fk_key, nk_key, prev_nk_key, tr_cont = "", "", "", ""
        count = 0

        # 드물지만 보유종목이 많으면 연속조회를 위한 반복 처리
        while True:
            time.sleep(0.2)

            headers = self._get_base_headers("TTTC8434R", include_custtype=True)
            headers["tr_cont"] = tr_cont
            params = {
                "CANO": account,
                "ACNT_PRDT_CD": self.product,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "01",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "00",
                "CTX_AREA_FK100": fk_key,
                "CTX_AREA_NK100": nk_key
            }

            res = requests.get(URL, headers=headers, params=params, timeout=REQUEST_TIMEOUT)

            # 연속 조회 처리
            tr_cont = "N" if res.headers['tr_cont'] in ["M", "F"] else ""

            if res.status_code == 200 and res.json()["rt_cd"] == '0':
                nk_key = res.json()['ctx_area_nk100'].strip()
                fk_key = res.json()['ctx_area_fk100'].strip()

                # 보유 종목 추가
                for stock in res.json()['output1']:
                    if int(stock['hldg_qty']) > 0:
                        symbol = stock['prdt_name']
                        quantity = stock['hldg_qty']
                        average_price = float(stock['pchs_avg_pric'])
                        last_price = float(stock['prpr'])

                        positions[symbol] = {
                            "quantity": quantity,
                            "average_price": average_price,
                            "last_price": last_price
                        }

                # 연속 조회 여부 확인
                if prev_nk_key == nk_key or not nk_key:
                    break
                prev_nk_key = nk_key
            else:
                print(f"Error Code: {res.status_code} | {res.text}")
                if res.json().get("msg_cd") == "EGW00123" or count > 10:
                    break
                count += 1

        return positions
    def get_cash(self, account: str) -> float:
        time.sleep(0.2)
        PATH = "uapi/domestic-stock/v1/trading/inquire-psbl-order"
        URL = f"{secret.KR_REAL_URL}/{PATH}"

        headers = self._get_base_headers("TTTC8908R", include_custtype=True)
        params = {
            "CANO": account,
            "ACNT_PRDT_CD" : self.product,
            "PDNO": "",
            "ORD_UNPR": "",
            "ORD_DVSN": "01",
            "CMA_EVLU_AMT_ICLD_YN" : "N",
            "OVRS_ICLD_YN" : "N"
        }

        res = requests.get(URL, headers=headers, params=params, timeout=REQUEST_TIMEOUT)

        if res.status_code == 200 and res.json()["rt_cd"] == '0':
            result = res.json()['output']
            return float(result['nrcvb_buy_amt'])
        else:
            print("Error Code : " + str(res.status_code) + " | " + res.text)
            return res.json()["msg_cd"]
    def get_account_result(self, account: str) -> float:
        time.sleep(0.2)
        PATH = "uapi/domestic-stock/v1/trading/inquire-balance"
        URL = f"{secret.KR_REAL_URL}/{PATH}"

        headers = self._get_base_headers("TTTC8434R", include_custtype=True)
        params = {
            "CANO": account,
            "ACNT_PRDT_CD" : self.product,
            "AFHR_FLPR_YN" : "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN" : "N",
            "FNCG_AMT_AUTO_RDPT_YN" : "N",
            "PRCS_DVSN" : "01",
            "CTX_AREA_FK100" : "",
            "CTX_AREA_NK100" : ""
        }

        res = requests.get(URL, headers=headers, params=params, timeout=REQUEST_TIMEOUT)

        if res.status_code == 200 and res.json()["rt_cd"] == '0':
            result = res.json()['output2'][0]
            return self.get_cash(account), float(result['tot_evlu_amt'])
        else:
            print("Error Code : " + str(res.status_code) + " | " + res.text)
            return res.json()["msg_cd"]

    def get_last_price(self, symbol: str) -> float:
        PATH = "uapi/domestic-stock/v1/quotations/inquire-price"
        URL = f"{secret.KR_REAL_URL}/{PATH}"

        headers = self._get_base_headers("FHKST01010100")
        params = {
            "FID_COND_MRKT_DIV_CODE":"J",
            "FID_INPUT_ISCD": symbol
        }

        # 호출
        res = requests.get(URL, headers=headers, params=params, timeout=REQUEST_TIMEOUT)

        if res.status_code == 200 and res.json()["rt_cd"] == '0':
            return int(res.json()['output']['stck_prpr'])
        else:
            print("Error Code : " + str(res.status_code) + " | " + res.text)
            return res.json()["msg_cd"]

    def get_hash(self, datas):
        PATH = "uapi/hashkey"
        URL = f"{secret.KR_REAL_URL}/{PATH}"

        headers = {
            'content-Type': 'application/json',
            'appKey': self.app_key,
            'appSecret': self.secret,
        }

        res = requests.post(URL, headers=headers, data=json.dumps(datas), timeout=REQUEST_TIMEOUT)

        if res.status_code == 200:
            return res.json()["HASH"]
        else:
            print("Error Code : " + str(res.status_code) + " | " + res.text)
            return None
    def place_market_sell_order(self, account: str, stockcode: str, quantity: int) -> bool:
        PATH = "uapi/domestic-stock/v1/trading/order-cash"
        URL = f"{secret.KR_REAL_URL}/{PATH}"
        data = self._get_base_data(account, stockcode, quantity, 0, "01")
        headers = self._get_base_headers("TTTC0011U", include_custtype=True)
        headers["hashkey"] = self.get_hash(data)
        res = requests.post(URL, headers=headers, data=json.dumps(data), timeout=REQUEST_TIMEOUT)

        if res.status_code == 200 and res.json()["rt_cd"] == '0':

            order = res.json()['output']
            OrderInfo = SimpleNamespace(**{
                "is_success": True
            })
            return OrderInfo
        else:
            print("Error Code : " + str(res.status_code) + " | " + res.text)
            return False

    def place_limit_buy_order(self, account: str, stockcode: str, quantity: int, price: float) -> bool:
        """Place limit buy order"""
        time.sleep(0.2)

        PATH = "uapi/domestic-stock/v1/trading/order-cash"
        URL = f"{secret.KR_REAL_URL}/{PATH}"

        data = self._get_base_data(account, stockcode, quantity, price, "00")
        headers = self._get_base_headers("TTTC0012U", include_custtype=True)
        headers["hashkey"] = self.get_hash(data)
        res = requests.post(URL, headers=headers, data=json.dumps(data), timeout=REQUEST_TIMEOUT)

        if res.status_code == 200 and res.json()["rt_cd"] == '0':
            order = res.json()['output']
            OrderInfo = SimpleNamespace(**{
                "is_success": True,
                "order_id": order['ODNO']
            })
            return OrderInfo
        else:
            return False
    def place_limit_sell_order(self, account: str, stockcode: str, quantity: int, price: float) -> bool:
        """Place limit buy order"""
        time.sleep(0.2)

        PATH = "uapi/domestic-stock/v1/trading/order-cash"
        URL = f"{secret.KR_REAL_URL}/{PATH}"
        data = self._get_base_data(account, stockcode, quantity, price, "00")
        headers = self._get_base_headers("TTTC0011U", include_custtype=True)
        headers["hashkey"] = self.get_hash(data)
        res = requests.post(URL, headers=headers, data=json.dumps(data), timeout=REQUEST_TIMEOUT)

        if res.status_code == 200 and res.json()["rt_cd"] == '0':
            order = res.json()['output']
            OrderInfo = SimpleNamespace(**{
                "is_success": True,
                "order_id": order['ODNO']
            })
            return OrderInfo
        else:
            return False
    def sell_etf_for_cash(self, hash_value: str, required_cash: float, positions: Dict[str, float]) -> Optional[float]:
        """Sell SGOV or BIL to get required cash"""
        etfs_to_sell = ['BIL','SGOV']

        for etf in etfs_to_sell:
            if etf in positions and positions[etf] > 0:
                current_price = self.get_last_price(etf)
                shares_to_sell = min(
                    positions[etf],
                    ceil(required_cash / current_price)
                )

                if shares_to_sell > 0:
                    return self.place_market_sell_order(hash_value, etf, shares_to_sell)

        return None
