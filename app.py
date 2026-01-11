from flask import Flask
import os
from library import secret
from routes import bp

app = Flask(__name__)
# Use secret key from environment or secret.py
app.secret_key = os.getenv("SECRET_KEY", secret.app_secret)

# Register the blueprint
app.register_blueprint(bp)

if __name__ == '__main__':
    # Use port 5002 as seen in the original metadata (metadata showed 5002 active)
    # The original code was app.run(debug=True), which defaults to 5000.
    # But metadata showed "Page ... (http://127.0.0.1:5002/)".
    # User might be running it with `flask run --port 5002` or modifying it.
    # The original file said:
    # if __name__ == '__main__':
    #    app.run(debug=True)
    # So I should keep it as is. If they run via `python app.py`, it will go to 5000.
    # If they use `flask run`, port is cli arg.
    # I will stick to original.
    app.run(debug=True)