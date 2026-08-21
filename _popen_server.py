import subprocess, sys, os, asyncio
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI()

@app.get('/test')
async def test():
    python = sys.executable
    script = os.path.join(r'D:\Crawller\site-audit-crawler', '_popen_test.py')
    subprocess.Popen([python, '-u', script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    return PlainTextResponse('popped')

@app.get('/check')
async def check():
    path = r'D:\Crawller\site-audit-crawler\data\popen_test.txt'
    if os.path.exists(path):
        return PlainTextResponse(open(path).read())
    return PlainTextResponse('no file')
