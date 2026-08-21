import sys
sys.path.insert(0, r'D:\Crawller\site-audit-crawler')
from app import db
from collections import Counter

scan = db.get_scan(14)
print('URL:', scan['start_url'])
print('UI:', scan['ui_score'], '| UX:', scan['ux_score'], '| SEO:', scan['seo_score'], '| Overall:', scan['overall_score'])

ui = db.get_findings(14, 'ui')
print('\nUI findings (%d total):' % len(ui))
c = Counter(f['check_name'] for f in ui)
for k, v in c.most_common():
    print('  %s: %d' % (k, v))

font_findings = [f for f in ui if 'font' in f['check_name'] or 'typo' in f['check_name']]
print('\nFont-related findings: %d' % len(font_findings))
for f in font_findings:
    print('  [%s] %s' % (f['severity'], f['message'][:100]))
