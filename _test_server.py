import subprocess, sys, os
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI()

@app.get('/test')
async def test():
    python = sys.executable
    script = os.path.join(r'D:\Crawller\site-audit-crawler', '_run_scan.py')
    p = subprocess.Popen([python, '-u', script, '31'], cwd=r'D:\Crawller\site-audit-crawler')
    return PlainTextResponse(f'started pid={p.pid}')
