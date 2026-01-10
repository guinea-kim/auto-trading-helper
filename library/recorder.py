import json
import time
import functools
import threading
import queue
import atexit
import logging
import os
import subprocess
from datetime import datetime
from library import secret

def backup_databases(stage, logger=None):
    """
    Backs up the US and KR databases using mysqldump.
    stage: 'start' or 'end'
    """
    if logger is None:
        logger = logging.getLogger("recorder")
        
    targets = [
        getattr(secret, 'db_name', None),
        getattr(secret, 'db_name_kr', None)
    ]
    
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = "records"
    os.makedirs(backup_dir, exist_ok=True)
    
    env = os.environ.copy()
    env['MYSQL_PWD'] = secret.db_passwd

    import shutil
    mysqldump_cmd = "mysqldump"
    # Auto-detect mysqldump if not in PATH
    if not shutil.which(mysqldump_cmd):
        possible_paths = [
            "/opt/homebrew/bin/mysqldump", 
            "/usr/local/bin/mysqldump", 
            "/usr/bin/mysqldump",
            "/usr/local/opt/mysql-client/bin/mysqldump",
            "/usr/local/opt/mysql@8.4/bin/mysqldump",
            "/opt/homebrew/opt/mysql-client/bin/mysqldump"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                mysqldump_cmd = path
                break

    for db_name in targets:
        if not db_name: continue
        
        filename = f"{backup_dir}/backup_{db_name}_{timestamp}_{stage}.sql"
        cmd = [
            mysqldump_cmd,
            "-h", secret.db_ip,
            "-P", str(secret.db_port),
            "-u", secret.db_id,
            "--single-transaction", # Consistent snapshot without locking
            "--quick",
            db_name
        ]
        
        try:
            with open(filename, 'w') as f:
                subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env=env, check=True)
            
            # Verify file size (Empty file means failure usually, as dump has headers)
            if os.path.getsize(filename) == 0:
                logger.error(f"Backup created but empty: {filename}")
                if os.path.exists(filename):
                    os.remove(filename)  # Clean up empty file
            else:
                logger.info(f"Database backup successful: {filename}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to backup {db_name}: {e.stderr.decode()}")
            if os.path.exists(filename):
                os.remove(filename) # Clean up empty/partial file
        except Exception as e:
            logger.error(f"Error during backup of {db_name}: {e}")
            if os.path.exists(filename):
                os.remove(filename) # Clean up empty file

class AsyncDataRecorder:

    def __init__(self, filename):
        self.queue = queue.Queue(maxsize=10000) # Prevent Memory Overflow
        self.stop_event = threading.Event()
        self.filename = filename
        self.logger = logging.getLogger("recorder")
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # Run as Daemon Thread (Requires separate handling to prevent forced kill on main process exit)
        self.worker_thread = threading.Thread(target=self._write_loop, daemon=True)
        self.worker_thread.start()
        
        # Ensure file closes safely on program exit
        atexit.register(self.close)

    def record(self, method_name, args, kwargs, result=None, error=None):
        try:
            # Timestamp must record 'call time' accurately (not Queue processing time)
            entry = {
                "ts": time.time(),
                "method": method_name,
                "args": list(args), # Convert tuple to list for JSON serialization
                "kwargs": kwargs,
                "result": self._serialize(result),
                "error": str(error) if error else None
            }
            # Non-blocking: If queue is full, drop log rather than stopping main logic (block=False)
            self.queue.put_nowait(entry)
        except queue.Full:
            # Extreme case: Disk I/O too slow -> Queue full -> Drop log, prioritize trading
            self.logger.error("Recorder queue full! Dropping log entry.")
        except Exception as e:
            # Logging failure should not crash the app, but we want to know about it
            self.logger.error(f"Failed to enqueue log: {e}")

    def _serialize(self, obj):
        # Handle objects not serializable like Order object
        if hasattr(obj, 'is_success'):
             try:
                 # Attempt to serialize the object itself if it has a specific dict representation, 
                 # otherwise create a simple summary
                 base_info = {"is_success": obj.is_success}
                 if hasattr(obj, 'to_dict'):
                     base_info.update(obj.to_dict())
                 else:
                     base_info['raw'] = str(obj)
                 return base_info
             except:
                 return {"is_success": getattr(obj, 'is_success', None), "serialization_error": True}
        return obj

    def _write_loop(self):
        """Background Worker"""
        # Open file in append mode. 
        # buffering=1 (line buffering) might not perfectly work with binary modes or some systems, 
        # but for text files it's usually fine. We'll use default buffering but flush periodically or on writes.
        try:
            with open(self.filename, 'a', encoding='utf-8') as f:
                # Basic metadata at start of session if file is empty
                if f.tell() == 0:
                    meta = {
                        "meta": {
                            "created_at": datetime.now().isoformat(),
                            "type": "session_start"
                        }
                    }
                    f.write(json.dumps(meta) + "\n")

                while not self.stop_event.is_set() or not self.queue.empty():
                    try:
                        # 1s timeout to induce stop_event check
                        entry = self.queue.get(timeout=1)
                        f.write(json.dumps(entry, default=str) + "\n") # Handle datetime with default=str
                        f.flush() # Ensure data is written to disk
                        self.queue.task_done()
                    except queue.Empty:
                        continue
                    except Exception as e:
                        self.logger.error(f"File Write Error: {e}")
        except Exception as e:
            self.logger.critical(f"FATAL: Recorder thread crashed. Logging stopped. Error: {e}")

    def close(self):
        """Graceful Shutdown"""
        self.stop_event.set()
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5) # Wait max 5s then exit

def recordable(recorder):
    """
    Decorator for safe logging. 
    Ideally, this should be applied to methods where `recorder` instance is available (or passed in).
    Since we are monkey patching with a specific recorder instance, we use a closure.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 1. Execute Original Function
            try:
                result = func(*args, **kwargs)
                error_to_log = None
            except Exception as e:
                result = None
                error_to_log = e
                # We do NOT return here, we want to log the error, then re-raise
            
            # 2. Log Result (Success or Failure)
            try:
                # Filter 'self' from args if it's the first argument (heuristic)
                # However, args passed to wrapper are exactly what func receives.
                # If func is a bound method call (instance.method()), 'self' is NOT in args.
                # If func is called as Class.method(instance), 'self' IS in args.
                # Since we are decorating unbounded functions in the Class definition (monkey patching),
                # the 'self' WILL be the first argument in `args`.
                
                # We don't want to log the entire 'Manager' instance.
                valid_args = list(args)
                if len(valid_args) > 0 and hasattr(valid_args[0], 'user_id'):
                    # Check if the first arg looks like 'self' (the Manager instance)
                    # We assume Manager instances have 'user_id' attribute.
                    valid_args = valid_args[1:]

                recorder.record(func.__name__, valid_args, kwargs, result=result, error=error_to_log)
            
            except Exception as log_error:
                # ABSOLUTE SILENCE ON LOGGING ERRORS
                # We print to stderr just in case someone is watching logs, but never crash the app
                pass
                
            # 3. Re-raise original error or return result
            if error_to_log:
                raise error_to_log
            return result
        return wrapper
    return decorator

def apply_patches(recorder, classes_to_patch):
    """
    Applies the recordable decorator to a standard set of methods on the given classes.
    returns: Number of methods patched
    """
    target_methods = [
        'get_last_price', 'get_positions', 'get_positions_result', 
        'get_hashs', 'get_cash', 'get_account_result', 
        'get_market_hours', 'sell_etf_for_cash',
        'place_limit_buy_order', 'place_limit_sell_order', 'place_market_sell_order',
        'get_current_price'
    ]
    
    patched_count = 0
    for ManagerClass in classes_to_patch:
        for method_name in target_methods:
            if hasattr(ManagerClass, method_name):
                original_method = getattr(ManagerClass, method_name)
                # Apply decorator
                setattr(ManagerClass, method_name, recordable(recorder)(original_method))
                patched_count += 1
    return patched_count
