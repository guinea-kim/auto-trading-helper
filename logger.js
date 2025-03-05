// logger.js - 로깅 설정 모듈
const winston = require('winston');
const fs = require('fs');
const path = require('path');

// 로그 디렉토리 생성
const logDir = path.join(__dirname, 'library', 'log');
if (!fs.existsSync(logDir)) {
  fs.mkdirSync(logDir, { recursive: true });
}

// Winston 로거 설정
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp({
      format: 'YYYY-MM-DD HH:mm:ss'
    }),
    winston.format.printf(info => `${info.timestamp} - ${info.level}: ${info.message}`)
  ),
  transports: [
    // 콘솔 출력
    new winston.transports.Console(),

    // 파일 출력 (10MB 제한, 최대 5개 백업 파일)
    new winston.transports.File({
      filename: path.join(logDir, 'schwab_auth.log'),
      maxsize: 10 * 1024 * 1024,
      maxFiles: 5,
      tailable: true
    })
  ]
});

module.exports = logger;