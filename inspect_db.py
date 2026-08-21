import sqlite3

DB = r"D:\Crawller\site-audit-crawler\data\memory.sqlite"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# 1. List all tables
print("=== TABLES ===")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
for t in tables:
    cnt = conn.execute(f"SELECT COUNT(*) FROM [{t['name']}]").fetchone()[0]
    print(f"  {t['name']} ({cnt} rows)")

# 2. All scans
print("\n=== SCANS ===")
scans = conn.execute("SELECT * FROM scans ORDER BY id").fetchall()
if not scans:
    print("  (none)")
else:
    for s in scans:
        print(f"  id={s['id']}  status={s['status']}  pages_crawled={s['pages_crawled']}  elements_found={s['elements_found']}  error={s['error']}")
        print(f"       start_url={s['start_url']}  started={s['started_at']}  finished={s['finished_at']}")

# 3. All findings
print("\n=== FINDINGS ===")
findings = conn.execute("SELECT * FROM findings ORDER BY id").fetchall()
if not findings:
    print("  (none)")
else:
    for f in findings:
        print(f"  id={f['id']}  scan={f['scan_id']}  page={f['page_id']}  category={f['category']}  check={f['check_name']}  severity={f['severity']}")
        print(f"       message={f['message'][:120]}")

# 4. All pages
print("\n=== PAGES ===")
pages = conn.execute("SELECT * FROM pages ORDER BY id").fetchall()
if not pages:
    print("  (none)")
else:
    for p in pages:
        print(f"  id={p['id']}  scan={p['scan_id']}  depth={p['depth']}  status={p['status_code']}  url={p['url']}")
        print(f"       title={p['title']}  crawled_at={p['crawled_at']}")

conn.close()
