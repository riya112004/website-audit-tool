import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import db; db.init_db()

s = db.get_scan(1)
print(f"Status: {s['status']} pages={s['pages_crawled']}")

findings = db.get_findings(1, "seo")
heading = [f for f in findings if f["check_name"] == "heading_order_broken"]
print(f"\nheading_order_broken: {len(heading)} findings (one per page)")
for f in heading:
    print(f"  {f['message']}")

link = [f for f in findings if f["check_name"] == "non_descriptive_link_text"]
print(f"\nnon_descriptive_link_text: {len(link)} findings (one per page)")
for f in link:
    print(f"  {f['message']}")

print(f"\nTotal SEO findings: {len(findings)}")
