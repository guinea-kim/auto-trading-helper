# 데이터베이스 시스템 문서

## 개요
이 프로젝트는 미국 및 한국 주식 거래 데이터를 분리하기 위해 이중 데이터베이스 아키텍처를 사용합니다. 애플리케이션 로직은 `DatabaseHandler` 클래스를 사용하여 이러한 차이점을 추상화합니다.

- **미국 주식**: `helper_db` (기본값)
- **한국 주식**: `helper_kr_db`

## 1. 스키마 설계 (Schema Design)

### 공통 테이블 (Common Tables)
두 데이터베이스는 동일한 핵심 테이블 구조를 공유하며, 통화 정밀도에 따른 사소한 데이터 타입 차이만 있습니다.

#### 1.1. `accounts`
사용자의 증권 계좌 정보를 저장합니다.
| Column | Type | Description |
|--------|------|-------------|
| `id` | VARCHAR(20) | 고유 식별자 (예: `user_0`) |
| `user_id` | VARCHAR(20) | 사용자 식별자 |
| `description` | VARCHAR(50) | 계좌 별칭 |
| `hash_value` | VARCHAR(70) | 증권사에서 받은 암호화/해시된 계좌 값 |
| `account_number` | VARCHAR(20) | 실제 계좌 번호 (마스킹/내부용) |
| `cash_balance` | DECIMAL | 현재 주문 가능 현금 (예수금) |
| `contribution` | DECIMAL | 총 투자 원금 |
| `total_value` | DECIMAL | 총 계좌 가치 (현금 + 보유 주식) |

#### 1.2. `trading_rules`
자동 매매 로직을 정의하는 핵심 엔진 테이블입니다.
| Column | Type | Description |
|--------|------|-------------|
| `id` | INT (PK) | 자동 증가 ID |
| `status` | ENUM | `ACTIVE`, `COMPLETED`, `CANCELLED`, `PROCESSED` |
| `symbol` | VARCHAR | 티커 심볼 (예: AAPL) |
| `trade_action` | TINYINT | `0` (SELL), `1` (BUY) |
| `limit_type` | ENUM | 로직 타입: `price`, `percent`, `high_percent`, `weekly`, `monthly` |
| `limit_value` | DECIMAL | 임계값 (가격, %, 또는 날짜 정보) |
| `target_amount` | INT | 목표 보유 수량 |
| `daily_money` | DECIMAL | 일일 최대 운용 금액 (매수/매도 한도) |
| `current_holding`| INT | 증권사와 동기화된 보유 수량 |
| `average_price` | DECIMAL | 증권사와 동기화된 평균 매입가 |
| `high_price` | DECIMAL | 추적 중인 최고가 (Trailing Buy 로직용) |

#### 1.3. `trade_history`
실행된 모든 매매 로그입니다.
**주의**: 기록된 `quantity`와 `price`는 **주문 요청된** 값이며, 실제 체결 값과 다를 수 있습니다. 이는 당일 **중복 주문 방지**를 위해 사용되기 때문입니다. 따라서 과거 날짜의 체결되지 않은 주문 데이터가 남아있을 수 있습니다.
| Column | Type | Description |
|--------|------|-------------|
| `order_id` | VARCHAR | 증권사 주문 ID |
| `trade_type` | ENUM | `BUY`, `SELL` |
| `quantity` | INT | 주문 수량 (요청 값) |
| `price` | DECIMAL | 주문 가격 (요청 값) |
| `used_money` | DECIMAL | 총 거래 금액 (`price * quantity`) |
#### 1.4. `daily_records`
일일 자산 스냅샷을 저장하는 테이블입니다. (운영 섹션 참고)
| Column | Type | Description |
|--------|------|-------------|
| `id` | INT (PK) | 자동 증가 ID |
| `record_date` | DATE | 기록 날짜 |
| `account_id` | VARCHAR(20) | 계좌 ID |
| `symbol` | VARCHAR | 종목 심볼 (또는 `total`, `cash`) |
| `amount` | DECIMAL | 가치 금액 (평가금액) |

### 국가별 차이점 (Regional Differences)
| Feature | US DB (`helper_db`) | KR DB (`helper_kr_db`) |
|---------|---------------------|------------------------|
| **가격 정밀도** | `DECIMAL(10, 2)` (센트 단위 지원) | `DECIMAL(10)` 또는 `DECIMAL(15)` (원화 정수) |
| **종목명** | N/A (`symbol` 사용) | `stock_name` 컬럼 존재 |

---

## 2. 비즈니스 로직 & 규칙

### 2.1. 매매 로직 타입 (`limit_type`)
`limit_type` 컬럼은 트레이딩 엔진이 `limit_value`를 어떻게 평가할지 결정합니다.

| Type | Condition Logic | Description |
|------|----------------|-------------|
| **`price`** | `Current Price <= limit_value` | 특정 가격 이하일 때 지정가 매수. |
| **`percent`** | `Current Price <= Average Price * (1 - limit_value/100)` | 평단가 대비 X% 하락 시 매수 (물타기). <br> **※ 평단가 0일 경우**: 매수는 시장가(현재가)로 진행하며, 보유량이 없으므로 매도는 시도하지 않음. |
| **`high_percent`**| `Current Price <= High Price * (1 - limit_value/100)` | **Trailing Buy**: 기록된 고점 대비 X% 하락 시 매수. |
| **`weekly`** | `Current Day == limit_value (0=Mon...6=Sun)` | 매주 특정 요일에 매수. |
| **`monthly`** | `Current Date == limit_value (1-31)` | 매월 특정 날짜에 매수. |

### 2.2. 상태 라이프사이클 (Status Lifecycle)
`status` 컬럼은 자동화 흐름을 제어합니다.

- **`ACTIVE`**: 트레이딩 엔진이 활발하게 모니터링 중인 상태.
- **`COMPLETED`**: 목표 수량 달성(매수) 또는 전량 매도(매도)로 완료된 상태. 엔진이 무시함.
- **`CANCELLED`**: 사용자가 수동으로 중지한 상태.
- **`PROCESSED`**: 정기 매수 규칙(`weekly`/`monthly`)에 사용됨.
    - **로직**: 지정된 날짜가 될 때까지 `PROCESSED` 유지 -> 날짜가 되면 `ACTIVE`로 변경 -> 매매 실행 -> 다시 `PROCESSED`로 변경.

### 2.3. 자동 보정 (Automated Adjustments)
- **주식 분할/병합 (Stock Split/Merge)**: 시스템(`trader.py`)은 증권사의 평단가와 DB의 `average_price`를 비교하여 분할을 자동 감지합니다.
    - 분할이 감지되면, 로직의 연속성을 유지하기 위해 `high_price`와 `target_amount`를 자동으로 보정합니다.

---

## 3. 운영 (Operations)
### 일일 스냅샷 (`daily_records`)
시스템은 매일 다음 항목에 대한 스냅샷을 기록합니다. 이는 개별 계좌 단위로 기록되며, 계좌별 자금 상황 추적을 위함입니다:
1.  **총 자산 가치**: Symbol `total`
2.  **현금 잔고 (예수금)**: Symbol `cash`
3.  **모든 보유 종목**: ETF(`BIL`, `SGOV`)뿐만 아니라 **모든 보유 주식**에 대해 평가금액을 기록합니다.

### 애플리케이션 사용 (Application Usage)
- **Python**: `library/mysql_helper.py`가 커넥션 풀링 및 쿼리 실행을 처리합니다.
- **Node.js**: 공유 DB 또는 API를 통해 일부 프론트엔드/자동화 작업에 사용됩니다.
