import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(name, log_folder='log', level=logging.INFO):
    """
    로깅 설정을 초기화하는 함수

    Args:
        name (str): 로거 이름
        log_folder (str): 로그 파일을 저장할 폴더 경로
        level (int): 로깅 레벨

    Returns:
        logging.Logger: 설정된 로거 인스턴스
    """
    # 로그 폴더 생성
    log_dir = Path(log_folder)
    if not log_dir.exists():
        log_dir.mkdir(parents=True)

    # 로거 인스턴스 생성
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 이미 핸들러가 설정되어 있으면 추가하지 않음
    if logger.handlers:
        return logger

    # 파일 핸들러 설정 (10MB 크기로 제한, 최대 5개 백업 파일)
    log_file = log_dir / f"{name}.log"
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding='utf-8'
    )

    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler()

    # 로그 포맷 설정
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 핸들러 추가
    #logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger