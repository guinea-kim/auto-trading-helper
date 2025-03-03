import os
from schwab.auth import easy_client
from datetime import datetime
import logging
from pathlib import Path
from library.secret import USER_AUTH_CONFIGS
class UserAuthManager:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.auth_config = USER_AUTH_CONFIGS[user_id]
        self.client = None

        lib_dir = Path(__file__).parent
        self.token_path = str(lib_dir / 'tokens' / f'schwab_token_{user_id}.json')
        self.logger = logging.getLogger(__name__)

    def get_client(self):
        if self.client is None:
            try:
                self.client = easy_client(
                    api_key=self.auth_config['app_key'],
                    app_secret=self.auth_config['secret'],
                    callback_url=self.auth_config['callback_url'],
                    token_path=self.token_path,
                    max_token_age=561600.0,
                    callback_timeout=300.0,
                    interactive=False
                )
                self.logger.info(f"Successfully authenticated user {self.user_id} at {datetime.now()}")

            except Exception as e:
                self.logger.error(f"Authentication failed for user {self.user_id}: {str(e)}")
                raise

        return self.client