import re
import os
import time

class CrontabService:
    def __init__(self, crontab_md_path='CRONTAB.md'):
        self.crontab_md_path = crontab_md_path

    def parse_crontab_md(self):
        """
        Parses CRONTAB.md to extract job details.
        Expected format in MD:
        ### N. Title
        * **Schedule**: ...
        * **Description**: ...
        ```bash
        <schedule> <command>
        ```
        """
        jobs = []
        if not os.path.exists(self.crontab_md_path):
            return []

        with open(self.crontab_md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Regex to find sections
        # This is a simple parser based on the known format
        # It looks for code blocks containing cron expressions
        
        # Strategy: processing line by line might be safer or regex for blocks
        # Let's try to extract code blocks first
        
        code_blocks = re.findall(r'```bash\s+(.*?)\s+```', content, re.DOTALL)
        
        for i, block in enumerate(code_blocks):
            # Example block:
            # 30 6 * * 1-5 cd ... && ...
            
            line = block.strip()
            # Split schedule and command
            # Standard cron has 5 parts for schedule
            parts = line.split()
            if len(parts) < 6:
                continue
                
            schedule = " ".join(parts[:5])
            command = " ".join(parts[5:])
            
            # Simple ID generation
            job_id = i + 1
            
            # Try to find description near the code block? 
            # For simplicity in this demo, we will just use a generic format or try to parse the MD structure better if needed.
            # But the user asked to "refer to CRONTAB.md".
            # Let's map known knowns or just use the extracted command.
            
            jobs.append({
                "id": job_id,
                "enabled": True, # Assume true for MD documentation
                "schedule": schedule,
                "command": command,
                "comment": f"# Job from CRONTAB.md Section {job_id}", # Placeholder
                "lastExitCode": 0,
                "lastDuration": "Unknown",
                "lastRunAt": "-",
                "nextRunAt": "-",
                "status": "idle",
                "pid": None
            })
            
        return jobs

    def mock_run_job(self, job_id):
        # Return a fake PID and status
        return {
            "job_id": job_id,
            "pid": 1234 + job_id,
            "status": "running"
        }

    def mock_kill_job(self, job_id):
        return {
            "job_id": job_id,
            "status": "killed"
        }
