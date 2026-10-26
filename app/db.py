#!/usr/bin/env python3
"""SQLite helper for the family renovation API. Reads a JSON request from stdin."""
import json
import sqlite3
import sys
from datetime import datetime


def output(value):
    sys.stdout.write(json.dumps(value, ensure_ascii=False))


def initialize(conn):
    conn.executescript("""
      CREATE TABLE IF NOT EXISTS project_meta (
        project_id TEXT PRIMARY KEY,
        revision INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS renovation_items (
        project_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        title TEXT NOT NULL,
        room TEXT NOT NULL,
        author TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        images_json TEXT NOT NULL DEFAULT '[]',
        measurements_json TEXT NOT NULL DEFAULT '[]',
        notes TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending',
        confirmed_by TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL,
        PRIMARY KEY (project_id, item_id)
      );
    """)


def to_item(row):
    return {
        'id': row['item_id'], 'title': row['title'], 'room': row['room'],
        'author': row['author'], 'description': row['description'],
        'images': json.loads(row['images_json']),
        'measurements': json.loads(row['measurements_json']),
        'notes': row['notes'], 'status': row['status'],
        'confirmedBy': row['confirmed_by'], 'updatedAt': row['updated_at'],
    }


def get_state(conn, project_id):
    meta = conn.execute('SELECT revision, updated_at FROM project_meta WHERE project_id = ?', (project_id,)).fetchone()
    rows = conn.execute('SELECT * FROM renovation_items WHERE project_id = ? ORDER BY updated_at DESC', (project_id,)).fetchall()
    if not meta:
        return {'state': None, 'revision': 0}
    return {
        'state': {'version': 2, 'updatedAt': meta['updated_at'], 'items': [to_item(row) for row in rows]},
        'revision': meta['revision'],
    }


def validate_item(item):
    if not isinstance(item, dict):
        raise ValueError('事项格式错误')
    required = ('id', 'title', 'room', 'updatedAt')
    if any(not isinstance(item.get(key), str) or not item.get(key).strip() for key in required):
        raise ValueError('事项缺少必要信息')
    if len(item['title']) > 80 or len(item['room']) > 80:
        raise ValueError('事项名称或位置过长')
    images = item.get('images', [])
    measurements = item.get('measurements', [])
    if not isinstance(images, list) or not isinstance(measurements, list) or len(images) > 4 or len(measurements) > 20:
        raise ValueError('图片或尺寸数据不合法')
    if any(not isinstance(url, str) or not url.startswith('/uploads/') for url in images):
        raise ValueError('图片必须先上传到服务器')


def put_state(conn, project_id, request):
    state = request.get('state')
    if not isinstance(state, dict) or not isinstance(state.get('items'), list):
        raise ValueError('数据格式错误')
    items = state['items']
    if len(items) > 500:
        raise ValueError('事项数量超出限制')
    for item in items:
        validate_item(item)
    expected = request.get('revision')
    now = state.get('updatedAt') if isinstance(state.get('updatedAt'), str) else datetime.utcnow().isoformat() + 'Z'
    conn.execute('BEGIN IMMEDIATE')
    current = conn.execute('SELECT revision FROM project_meta WHERE project_id = ?', (project_id,)).fetchone()
    revision = current['revision'] if current else 0
    if expected is not None and expected != revision:
        conn.rollback()
        return {'conflict': True, **get_state(conn, project_id)}
    conn.execute('DELETE FROM renovation_items WHERE project_id = ?', (project_id,))
    for item in items:
        conn.execute('''INSERT INTO renovation_items
          (project_id, item_id, title, room, author, description, images_json, measurements_json, notes, status, confirmed_by, updated_at)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
            project_id, item['id'], item['title'].strip(), item['room'].strip(),
            str(item.get('author') or '')[:80], str(item.get('description') or '')[:2000],
            json.dumps(item.get('images', []), ensure_ascii=False),
            json.dumps(item.get('measurements', []), ensure_ascii=False),
            str(item.get('notes') or '')[:2000],
            'done' if item.get('status') == 'done' else 'pending',
            str(item.get('confirmedBy') or '')[:80], item['updatedAt'],
        ))
    next_revision = revision + 1
    conn.execute('INSERT OR REPLACE INTO project_meta (project_id, revision, updated_at) VALUES (?, ?, ?)', (project_id, next_revision, now))
    conn.commit()
    return {'state': {'version': 2, 'updatedAt': now, 'items': items}, 'revision': next_revision}


def main():
    if len(sys.argv) != 3:
        raise ValueError('用法: db.py <get|put> <database>')
    action, database = sys.argv[1:]
    request = json.load(sys.stdin) if action == 'put' else {}
    conn = sqlite3.connect(database, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        initialize(conn)
        project_id = 'family-renovation-shared'
        if action == 'get':
            output(get_state(conn, project_id))
        elif action == 'put':
            output(put_state(conn, project_id, request))
        else:
            raise ValueError('未知操作')
    finally:
        conn.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        output({'error': str(error)})
        sys.exit(1)
