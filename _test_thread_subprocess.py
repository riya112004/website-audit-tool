import subprocess, threading, sys

def run_from_thread():
    print('[thread] Starting subprocess...', flush=True)
    proc = subprocess.Popen(
        [sys.executable, '-c', 'print("hello from child")'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = proc.communicate(timeout=10)
    print('[thread] stdout:', stdout.decode().strip(), flush=True)
    print('[thread] stderr:', stderr.decode().strip(), flush=True)

t = threading.Thread(target=run_from_thread)
t.start()
t.join(timeout=15)
print('[main] Thread alive:', t.is_alive(), flush=True)
