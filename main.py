# main.py
import os
import threading
import uvicorn
from oauth_server import app
from bot import run_bot

def start_api():
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ["PORT"]))

if __name__ == "__main__":
    threading.Thread(target=start_api).start()
    run_bot()
