#!/usr/bin/env python3
import argparse
import sqlite3
import sys
from pathlib import Path
from tabulate import tabulate

def get_db_path():
    return '../shared/db/brain/memories.db'

def connect_db():
    db_path = get_db_path()
    return sqlite3.connect(db_path)

def list_memories(topic=None):
    conn = connect_db()
    c = conn.cursor()
    query = '''
        SELECT m.id, m.user_id, m.memory, m.created_at, m.access_count, m.last_accessed, m.priority,
            GROUP_CONCAT(DISTINCT mt.tag) as keywords,
            (SELECT mt2.topic FROM memory_topic mt2 WHERE mt2.memory_id = m.id LIMIT 1) as topic
        FROM memories m
        LEFT JOIN memory_tags mt ON m.id = mt.memory_id
        LEFT JOIN memory_topic mt3 ON m.id = mt3.memory_id
    '''
    params = []
    if topic:
        query += ' WHERE mt3.topic = ?'
        params.append(topic)
    query += ' GROUP BY m.id ORDER BY m.created_at DESC'
    c.execute(query, params)
    rows = c.fetchall()
    headers = ['id', 'user_id', 'memory', 'created_at', 'access_count', 'last_accessed', 'priority', 'keywords', 'topic']
    # Print without extra lines between entries
    for row in rows:
        print(f"{row[0]}: {row[2]}\n")
    conn.close()

def add_memory(user_id, memory, topic, keywords=None, priority=None):
    import uuid, datetime
    conn = connect_db()
    c = conn.cursor()
    mem_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    c.execute('''INSERT INTO memories (id, user_id, memory, created_at, priority) VALUES (?, ?, ?, ?, ?)''',
              (mem_id, user_id, memory, now, priority))
    # Enforce only one topic per memory
    c.execute('DELETE FROM memory_topic WHERE memory_id = ?', (mem_id,))
    c.execute('INSERT INTO memory_topic (memory_id, topic) VALUES (?, ?)', (mem_id, topic))
    if keywords:
        for kw in keywords:
            c.execute('INSERT OR IGNORE INTO memory_tags (memory_id, tag) VALUES (?, ?)', (mem_id, kw))
    conn.commit()
    print(f"Added memory {mem_id}")
    conn.close()

def delete_memory(mem_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute('DELETE FROM memories WHERE id = ?', (mem_id,))
    conn.commit()
    print(f"Deleted memory {mem_id}")
    conn.close()

def add_keyword(mem_id, keyword):
    conn = connect_db()
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO memory_tags (memory_id, tag) VALUES (?, ?)', (mem_id, keyword))
    conn.commit()
    print(f"Added keyword '{keyword}' to memory {mem_id}")
    conn.close()

def remove_keyword(mem_id, keyword):
    conn = connect_db()
    c = conn.cursor()
    c.execute('DELETE FROM memory_tags WHERE memory_id = ? AND tag = ?', (mem_id, keyword))
    conn.commit()
    print(f"Removed keyword '{keyword}' from memory {mem_id}")
    conn.close()

def set_topic(mem_id, topic):
    conn = connect_db()
    c = conn.cursor()
    # Enforce only one topic per memory
    c.execute('DELETE FROM memory_topic WHERE memory_id = ?', (mem_id,))
    c.execute('INSERT INTO memory_topic (memory_id, topic) VALUES (?, ?)', (mem_id, topic))
    conn.commit()
    print(f"Set topic '{topic}' for memory {mem_id}")
    conn.close()

def remove_topic(mem_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute('DELETE FROM memory_topic WHERE memory_id = ?', (mem_id,))
    conn.commit()
    print(f"Removed topic from memory {mem_id}")
    conn.close()

def main():
    parser = argparse.ArgumentParser(description='Memories DB CLI')
    subparsers = parser.add_subparsers(dest='command')

    list_parser = subparsers.add_parser('list', help='List memories')
    list_parser.add_argument('--topic', help='Filter by topic')

    add_parser = subparsers.add_parser('add', help='Add a memory')
    add_parser.add_argument('user_id')
    add_parser.add_argument('memory')
    add_parser.add_argument('topic')
    add_parser.add_argument('--keywords', nargs='*', default=[])
    add_parser.add_argument('--priority', type=float, default=None)

    del_parser = subparsers.add_parser('delete', help='Delete a memory by id')
    del_parser.add_argument('id')

    addkw_parser = subparsers.add_parser('add-keyword', help='Add a keyword to a memory')
    addkw_parser.add_argument('id')
    addkw_parser.add_argument('keyword')

    rmkw_parser = subparsers.add_parser('remove-keyword', help='Remove a keyword from a memory')
    rmkw_parser.add_argument('id')
    rmkw_parser.add_argument('keyword')

    settopic_parser = subparsers.add_parser('set-topic', help='Set (replace) topic for a memory')
    settopic_parser.add_argument('id')
    settopic_parser.add_argument('topic')

    rmtopic_parser = subparsers.add_parser('remove-topic', help='Remove topic from a memory')
    rmtopic_parser.add_argument('id')

    args = parser.parse_args()
    if args.command == 'list':
        list_memories(topic=args.topic)
    elif args.command == 'add':
        add_memory(args.user_id, args.memory, args.topic, args.keywords, args.priority)
    elif args.command == 'delete':
        delete_memory(args.id)
    elif args.command == 'add-keyword':
        add_keyword(args.id, args.keyword)
    elif args.command == 'remove-keyword':
        remove_keyword(args.id, args.keyword)
    elif args.command == 'set-topic':
        set_topic(args.id, args.topic)
    elif args.command == 'remove-topic':
        remove_topic(args.id)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
