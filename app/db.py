import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "memory.sqlite")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sites (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            origin      TEXT UNIQUE NOT NULL,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scans (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id           INTEGER NOT NULL REFERENCES sites(id),
            start_url         TEXT NOT NULL,
            status            TEXT NOT NULL DEFAULT 'queued',
            max_pages         INTEGER NOT NULL DEFAULT 50,
            max_depth         INTEGER NOT NULL DEFAULT 3,
            started_at        TEXT,
            finished_at       TEXT,
            pages_crawled     INTEGER DEFAULT 0,
            elements_found    INTEGER DEFAULT 0,
            interactions_run  INTEGER DEFAULT 0,
            error             TEXT,
            ui_score          INTEGER DEFAULT 0,
            ux_score          INTEGER DEFAULT 0,
            seo_score         INTEGER DEFAULT 0,
            overall_score     INTEGER DEFAULT 0,
            mobile_score      INTEGER DEFAULT 0,
            missing_features_score INTEGER DEFAULT 0,
            cta_score         INTEGER DEFAULT 0,
            security_score    INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS pages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id         INTEGER NOT NULL REFERENCES scans(id),
            site_id         INTEGER NOT NULL REFERENCES sites(id),
            url             TEXT NOT NULL,
            normalized_url  TEXT NOT NULL,
            title           TEXT,
            depth           INTEGER NOT NULL DEFAULT 0,
            status_code     INTEGER,
            screenshot_path TEXT,
            raw_html_path   TEXT,
            response_headers TEXT,
            crawled_at      TEXT
        );

        CREATE TABLE IF NOT EXISTS elements (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id             INTEGER NOT NULL REFERENCES pages(id),
            role                TEXT NOT NULL,
            accessible_name     TEXT,
            selector            TEXT NOT NULL,
            revealed_by         TEXT,
            first_seen_scan_id  INTEGER REFERENCES scans(id),
            screenshot_path     TEXT
        );

        CREATE TABLE IF NOT EXISTS edges (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            from_page_id    INTEGER NOT NULL REFERENCES pages(id),
            to_url          TEXT NOT NULL,
            via_element_id  INTEGER REFERENCES elements(id)
        );

        CREATE TABLE IF NOT EXISTS interactions (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            element_id        INTEGER NOT NULL REFERENCES elements(id),
            action            TEXT NOT NULL,
            result            TEXT NOT NULL,
            note              TEXT,
            screenshot_before TEXT,
            screenshot_after  TEXT,
            created_at        TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS findings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id         INTEGER NOT NULL REFERENCES scans(id),
            page_id         INTEGER REFERENCES pages(id),
            category        TEXT NOT NULL,
            check_name      TEXT NOT NULL,
            severity        TEXT NOT NULL DEFAULT 'info',
            message         TEXT NOT NULL,
            recommendation  TEXT,
            created_at      TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_pages_scan ON pages(scan_id);
        CREATE INDEX IF NOT EXISTS idx_pages_site ON pages(site_id);
        CREATE INDEX IF NOT EXISTS idx_elements_page ON elements(page_id);
        CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_page_id);
        CREATE INDEX IF NOT EXISTS idx_interactions_element ON interactions(element_id);
        CREATE INDEX IF NOT EXISTS idx_findings_scan ON findings(scan_id);
        CREATE INDEX IF NOT EXISTS idx_findings_page ON findings(page_id);
        CREATE INDEX IF NOT EXISTS idx_findings_category ON findings(category);
    """)
    # migrations
    try:
        conn.execute("ALTER TABLE scans ADD COLUMN mobile_score INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE scans ADD COLUMN missing_features_score INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE scans ADD COLUMN cta_score INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE scans ADD COLUMN security_score INTEGER DEFAULT 0")
    except Exception:
        pass
    conn.commit()
    conn.close()


# ─── Site ───────────────────────────────────────────────────

def get_or_create_site(origin: str) -> dict:
    conn = get_conn()
    row = conn.execute("SELECT * FROM sites WHERE origin = ?", (origin,)).fetchone()
    if row:
        site = dict(row)
    else:
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute("INSERT INTO sites (origin, created_at) VALUES (?, ?)", (origin, now))
        conn.commit()
        site = {"id": cur.lastrowid, "origin": origin, "created_at": now}
    conn.close()
    return site


# ─── Scan ───────────────────────────────────────────────────

def create_scan(site_id: int, start_url: str, max_pages: int = 50, max_depth: int = 3) -> dict:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO scans (site_id, start_url, max_pages, max_depth) VALUES (?, ?, ?, ?)",
        (site_id, start_url, max_pages, max_depth),
    )
    conn.commit()
    scan_id = cur.lastrowid
    row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    conn.close()
    return dict(row)


def update_scan(scan_id: int, **fields):
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [scan_id]
    conn = get_conn()
    conn.execute(f"UPDATE scans SET {sets} WHERE id = ?", vals)
    conn.commit()
    conn.close()


def get_scan(scan_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_scans(site_id: int | None = None) -> list[dict]:
    conn = get_conn()
    if site_id:
        rows = conn.execute("SELECT * FROM scans WHERE site_id = ? ORDER BY id DESC", (site_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM scans ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Pages ──────────────────────────────────────────────────

def insert_page(scan_id: int, site_id: int, url: str, normalized_url: str,
                title: str | None, depth: int, status_code: int | None,
                screenshot_path: str | None = None,
                raw_html_path: str | None = None,
                response_headers: str | None = None) -> dict:
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO pages (scan_id, site_id, url, normalized_url, title, depth, status_code, screenshot_path, raw_html_path, response_headers, crawled_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (scan_id, site_id, url, normalized_url, title, depth, status_code, screenshot_path, raw_html_path, response_headers, now),
    )
    conn.commit()
    page_id = cur.lastrowid
    row = conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
    conn.close()
    return dict(row)


def get_pages(scan_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM pages WHERE scan_id = ? ORDER BY depth, id", (scan_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_page(page_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def find_page_by_url(scan_id: int, normalized_url: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM pages WHERE scan_id = ? AND normalized_url = ?", (scan_id, normalized_url)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ─── Elements ───────────────────────────────────────────────

def insert_element(page_id: int, role: str, accessible_name: str | None,
                   selector: str, revealed_by: str | None = None,
                   first_seen_scan_id: int | None = None,
                   screenshot_path: str | None = None) -> dict:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO elements (page_id, role, accessible_name, selector, revealed_by, first_seen_scan_id, screenshot_path) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (page_id, role, accessible_name, selector, revealed_by, first_seen_scan_id, screenshot_path),
    )
    conn.commit()
    elem_id = cur.lastrowid
    row = conn.execute("SELECT * FROM elements WHERE id = ?", (elem_id,)).fetchone()
    conn.close()
    return dict(row)


def get_elements(page_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM elements WHERE page_id = ? ORDER BY id", (page_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_element(element_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM elements WHERE id = ?", (element_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ─── Edges ──────────────────────────────────────────────────

def insert_edge(from_page_id: int, to_url: str, via_element_id: int | None = None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO edges (from_page_id, to_url, via_element_id) VALUES (?, ?, ?)",
        (from_page_id, to_url, via_element_id),
    )
    conn.commit()
    conn.close()


def get_edges(scan_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT e.*, p.url AS from_url
        FROM edges e
        JOIN pages p ON p.id = e.from_page_id
        WHERE p.scan_id = ?
        ORDER BY e.id
    """, (scan_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Interactions ───────────────────────────────────────────

def insert_interaction(element_id: int, action: str, result: str,
                       note: str | None = None, screenshot_before: str | None = None,
                       screenshot_after: str | None = None) -> dict:
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO interactions (element_id, action, result, note, screenshot_before, screenshot_after, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (element_id, action, result, note, screenshot_before, screenshot_after, now),
    )
    conn.commit()
    ix_id = cur.lastrowid
    row = conn.execute("SELECT * FROM interactions WHERE id = ?", (ix_id,)).fetchone()
    conn.close()
    return dict(row)


def get_interactions(page_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT i.*, e.selector, e.role, e.accessible_name
        FROM interactions i
        JOIN elements e ON e.id = i.element_id
        WHERE e.page_id = ?
        ORDER BY i.id
    """, (page_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Diff ───────────────────────────────────────────────────

def diff_against_previous_scan(scan_id: int) -> dict:
    conn = get_conn()
    scan = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    if not scan:
        conn.close()
        return {"error": "scan not found"}

    prev = conn.execute(
        "SELECT id FROM scans WHERE site_id = ? AND id < ? ORDER BY id DESC LIMIT 1",
        (scan["site_id"], scan_id),
    ).fetchone()

    if not prev:
        conn.close()
        return {"new_pages": [], "missing_pages": [], "new_elements": [], "missing_elements": []}

    prev_id = prev["id"]

    new_pages = [dict(r) for r in conn.execute(
        "SELECT * FROM pages WHERE scan_id = ? AND normalized_url NOT IN "
        "(SELECT normalized_url FROM pages WHERE scan_id = ?)",
        (scan_id, prev_id),
    ).fetchall()]

    missing_pages = [dict(r) for r in conn.execute(
        "SELECT * FROM pages WHERE scan_id = ? AND normalized_url NOT IN "
        "(SELECT normalized_url FROM pages WHERE scan_id = ?)",
        (prev_id, scan_id),
    ).fetchall()]

    new_elements = [dict(r) for r in conn.execute(
        "SELECT * FROM elements WHERE page_id IN (SELECT id FROM pages WHERE scan_id = ?) "
        "AND selector NOT IN "
        "(SELECT e2.selector FROM elements e2 JOIN pages p2 ON p2.id = e2.page_id WHERE p2.scan_id = ?)",
        (scan_id, prev_id),
    ).fetchall()]

    missing_elements = [dict(r) for r in conn.execute(
        "SELECT * FROM elements WHERE page_id IN (SELECT id FROM pages WHERE scan_id = ?) "
        "AND selector NOT IN "
        "(SELECT e2.selector FROM elements e2 JOIN pages p2 ON p2.id = e2.page_id WHERE p2.scan_id = ?)",
        (prev_id, scan_id),
    ).fetchall()]

    conn.close()
    return {
        "new_pages": new_pages,
        "missing_pages": missing_pages,
        "new_elements": new_elements,
        "missing_elements": missing_elements,
    }


# ─── Findings CRUD ─────────────────────────────────────────

def insert_finding(scan_id: int, category: str, check_name: str, severity: str,
                   message: str, page_id: int | None = None,
                   recommendation: str | None = None) -> dict:
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO findings (scan_id, page_id, category, check_name, severity, message, recommendation, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (scan_id, page_id, category, check_name, severity, message, recommendation, now),
    )
    conn.commit()
    finding_id = cur.lastrowid
    row = conn.execute("SELECT * FROM findings WHERE id = ?", (finding_id,)).fetchone()
    conn.close()
    return dict(row)


def save_mobile_findings(scan_id: int, mobile_result: dict):
    """Save mobile findings to DB and update scan mobile_score."""
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()

    pages_map = {}
    for row in conn.execute("SELECT id, url FROM pages WHERE scan_id = ?", (scan_id,)):
        pages_map[row["url"]] = row["id"]

    for f in mobile_result.get("all_findings", []):
        page_url = f.get("page_url")
        page_id = pages_map.get(page_url)
        conn.execute(
            "INSERT INTO findings (scan_id, page_id, category, check_name, severity, message, recommendation, created_at) "
            "VALUES (?, ?, 'mobile', ?, ?, ?, ?, ?)",
            (scan_id, page_id, f["check_name"], f["severity"], f["message"], f.get("recommendation"), now),
        )

    conn.execute(
        "UPDATE scans SET mobile_score = ? WHERE id = ?",
        (mobile_result.get("mobile_score", 0), scan_id),
    )
    conn.commit()
    conn.close()


def save_missing_features_findings(scan_id: int, mf_result: dict):
    """Save missing features findings to DB and update scan missing_features_score."""
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()

    for f in mf_result.get("findings", []):
        conn.execute(
            "INSERT INTO findings (scan_id, page_id, category, check_name, severity, message, recommendation, created_at) "
            "VALUES (?, NULL, 'missing_features', ?, ?, ?, ?, ?)",
            (scan_id, f["feature_id"], f["severity"], f["message"], f.get("feature_name"), now),
        )

    conn.execute(
        "UPDATE scans SET missing_features_score = ? WHERE id = ?",
        (mf_result.get("missing_features_score", 0), scan_id),
    )
    conn.commit()
    conn.close()


def save_cta_findings(scan_id: int, cta_result: dict):
    """Save CTA audit findings to DB and update scan cta_score."""
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()

    for f in cta_result.get("findings", []):
        conn.execute(
            "INSERT INTO findings (scan_id, page_id, category, check_name, severity, message, recommendation, created_at) "
            "VALUES (?, NULL, 'cta', ?, ?, ?, ?, ?)",
            (scan_id, f["check"], f["severity"], f["message"], f.get("recommendation", ""), now),
        )

    conn.execute(
        "UPDATE scans SET cta_score = ? WHERE id = ?",
        (cta_result.get("cta_score", 0), scan_id),
    )
    conn.commit()
    conn.close()


def save_security_findings(scan_id: int, sec_result: dict):
    """Save security audit findings to DB and update scan security_score."""
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()

    for f in sec_result.get("findings", []):
        conn.execute(
            "INSERT INTO findings (scan_id, page_id, category, check_name, severity, message, recommendation, created_at) "
            "VALUES (?, NULL, 'security', ?, ?, ?, ?, ?)",
            (scan_id, f["check"], f["severity"], f["message"], f.get("recommendation", ""), now),
        )

    conn.execute(
        "UPDATE scans SET security_score = ? WHERE id = ?",
        (sec_result.get("security_score", 0), scan_id),
    )
    conn.commit()
    conn.close()


def get_findings(scan_id: int, category: str | None = None) -> list[dict]:
    conn = get_conn()
    if category:
        rows = conn.execute(
            "SELECT * FROM findings WHERE scan_id = ? AND category = ? ORDER BY severity, id",
            (scan_id, category),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM findings WHERE scan_id = ? ORDER BY category, severity, id",
            (scan_id,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_findings_summary(scan_id: int) -> dict:
    conn = get_conn()
    rows = conn.execute(
        "SELECT category, severity, COUNT(*) as cnt FROM findings WHERE scan_id = ? GROUP BY category, severity",
        (scan_id,),
    ).fetchall()
    conn.close()
    summary = {}
    for r in rows:
        cat = r["category"]
        if cat not in summary:
            summary[cat] = {"info": 0, "warning": 0, "critical": 0}
        summary[cat][r["severity"]] = r["cnt"]
    return summary


def delete_findings(scan_id: int, category: str | None = None):
    conn = get_conn()
    if category:
        conn.execute("DELETE FROM findings WHERE scan_id = ? AND category = ?", (scan_id, category))
    else:
        conn.execute("DELETE FROM findings WHERE scan_id = ?", (scan_id,))
    conn.commit()
    conn.close()
