import threading, subprocess, sys, time, os

log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "thread_test.log")

def run_in_thread():
    with open(log, "w") as f:
        f.write("Thread started\n")
        f.flush()
    result = subprocess.run(
        [sys.executable, "-c", "print('child'); import time; time.sleep(3); print('done')"],
        capture_output=True, text=True, timeout=10
    )
    with open(log, "a") as f:
        f.write(f"exit={result.returncode} stdout={result.stdout}\n")

t = threading.Thread(target=run_in_thread, daemon=True)
t.start()
time.sleep(8)
with open(log) as f:
    print(f.read())
print("Thread alive:", t.is_alive())
