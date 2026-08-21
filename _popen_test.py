
import time
with open(r'D:\Crawller\site-audit-crawler\data\popen_test.txt', 'w') as f:
    f.write('subprocess alive at ' + time.strftime('%H:%M:%S') + '\n')
    f.flush()
time.sleep(2)
with open(r'D:\Crawller\site-audit-crawler\data\popen_test.txt', 'a') as f:
    f.write('subprocess done at ' + time.strftime('%H:%M:%S') + '\n')

