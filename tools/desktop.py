"""Start the laptop dashboard once and open it in the default browser."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT=Path(__file__).resolve().parents[1]
URL="http://127.0.0.1:8765"


def ready():
    try:
        with urllib.request.urlopen(URL+"/api/health",timeout=2) as response:
            value=json.load(response)
        return value.get("application")=="praecursor-desktop" and Path(value["root"]).resolve()==ROOT
    except Exception:
        return False


def main():
    if not ready():
        (ROOT/"logs").mkdir(exist_ok=True)
        python=Path(sys.executable).with_name("python.exe") if os.name=="nt" else Path(sys.executable)
        env=os.environ.copy();env["PYTHONPATH"]=str(ROOT/"src")
        with (ROOT/"logs/desktop_server.log").open("a",encoding="utf-8") as log:
            process=subprocess.Popen([str(python),str(ROOT/"tools/run_dashboard.py"),"--port","8765"],
                cwd=str(ROOT),env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW|subprocess.DETACHED_PROCESS if os.name=="nt" else 0,
                start_new_session=os.name!="nt")
        for _ in range(60):
            if ready():break
            if process.poll() is not None:break
            time.sleep(.5)
        if not ready():
            if os.name=="nt":
                import ctypes
                ctypes.windll.user32.MessageBoxW(None,"The dashboard could not start. See logs/desktop_server.log in the Praecursor-EGX folder.","Praecursor",0x10)
            return 1
    webbrowser.open(URL)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
