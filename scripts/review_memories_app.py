from flask import Flask, render_template_string, request, redirect, url_for
import sqlite3
import json
from pathlib import Path

def get_db_path():
    return '../shared/db/brain/memories.db'

def query_memories(keyword=None, topic=None, show_reviewed=False):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    query = '''
        SELECT m.id, m.user_id, m.memory, m.created_at, m.access_count, m.last_accessed, m.priority, m.reviewed,
            GROUP_CONCAT(DISTINCT mt.tag) as keywords,
            (SELECT mt2.topic FROM memory_topic mt2 WHERE mt2.memory_id = m.id LIMIT 1) as topic
        FROM memories m
        LEFT JOIN memory_tags mt ON m.id = mt.memory_id
        LEFT JOIN memory_topic mt3 ON m.id = mt3.memory_id
    '''
    conditions = []
    params = []
    if keyword:
        conditions.append('mt.tag = ?')
        params.append(keyword)
    if topic:
        conditions.append('mt3.topic = ?')
        params.append(topic)
    if not show_reviewed:
        conditions.append('m.reviewed = 0')
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    query += ' GROUP BY m.id ORDER BY m.created_at DESC'
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return rows

def mark_reviewed(memory_id):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('UPDATE memories SET reviewed = 1 WHERE id = ?', (memory_id,))
    conn.commit()
    conn.close()

def get_unique_tags_and_topics():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT DISTINCT tag FROM memory_tags ORDER BY tag COLLATE NOCASE')
    tags = [row[0] for row in c.fetchall() if row[0]]
    c.execute('SELECT DISTINCT topic FROM memory_topic ORDER BY topic COLLATE NOCASE')
    topics = [row[0] for row in c.fetchall() if row[0]]
    conn.close()
    return tags, topics

app = Flask(__name__)

TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Memory Review</title>
    <style>
        body { font-family: sans-serif; font-size: 13px; }
        table { border-collapse: collapse; width: 100%; font-size: 12px; table-layout: auto; }
        th, td { border: 1px solid #ccc; padding: 0.3em; text-align: left; }
        th { background: #f0f0f0; cursor: pointer; font-size: 12px; }
        .mark-btn { padding: 0.15em 0.4em; font-size: 12px; }
        td.copyable { cursor: pointer; background: #f7faff; }
        td.copyable.selected { outline: 2px solid #0074d9; background: #d0eaff !important; }
        th.copied { background: #b3e6ff !important; }
        form, label, select, input, button { font-size: 12px; }
        td.memory-col { white-space: pre-line; word-break: break-word; }
        td.keywords-col { white-space: pre-line; word-break: break-word; }
        .approve-form { margin: 0; display: inline; }
        .approve-checkbox { transform: scale(1.2); margin: 0 0.5em 0 0; }
    </style>
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        // Copy individual cell
        const cells = document.querySelectorAll('td.copyable');
        cells.forEach(cell => {
            cell.addEventListener('click', function(e) {
                if (e.target.tagName === 'INPUT') return; // Don't trigger on checkbox click
                cells.forEach(c => c.classList.remove('selected'));
                this.classList.add('selected');
                navigator.clipboard.writeText(this.innerText);
            });
        });
        // Copy entire column
        const ths = document.querySelectorAll('th.copy-col');
        ths.forEach((th, colIdx) => {
            th.addEventListener('click', function(e) {
                ths.forEach(h => h.classList.remove('copied'));
                this.classList.add('copied');
                let cells = Array.from(document.querySelectorAll('tbody tr')).map(
                    row => row.children[colIdx].innerText
                );
                navigator.clipboard.writeText(cells.join('\n'));
            });
        });
    });
    </script>
</head>
<body>
    <h1 style="font-size: 16px;">Memory Review</h1>
    <form method="get">
        <label>Keyword:
            <select name="keyword">
                <option value="">-- Any --</option>
                {% for tag in tags %}
                <option value="{{ tag }}" {% if request.args.get('keyword') == tag %}selected{% endif %}>{{ tag }}</option>
                {% endfor %}
            </select>
        </label>
        <label>Topic:
            <select name="topic">
                <option value="">-- Any --</option>
                {% for t in topics %}
                <option value="{{ t }}" {% if request.args.get('topic') == t %}selected{% endif %}>{{ t }}</option>
                {% endfor %}
            </select>
        </label>
        <label><input type="checkbox" name="show_reviewed" value="1" {% if request.args.get('show_reviewed') %}checked{% endif %}> Show reviewed</label>
        <button type="submit">Filter</button>
    </form>
    <p style="font-size: 11px;"><em>Click a cell to copy its contents, or click a column header to copy the entire column. Check the box to approve a memory.</em></p>
    <form method="post" id="approve-form">
    <table>
        <thead>
            <tr>
                <th class="copy-col">ID</th>
                <th class="copy-col">User</th>
                <th class="copy-col">Memory</th>
                <th class="copy-col">Created</th>
                <th class="copy-col">Access Count</th>
                <th class="copy-col">Last Accessed</th>
                <th class="copy-col">Priority</th>
                <th class="copy-col">Reviewed</th>
                <th class="copy-col">Keywords</th>
                <th class="copy-col">Topic</th>
                <th>Approve</th>
                <th>Edit</th>
            </tr>
        </thead>
        <tbody>
        {% for m in memories %}
            <tr class="{% if m[7] %}reviewed{% else %}not-reviewed{% endif %}">
                <td class="copyable"><a href="{{ url_for('edit_memory', memory_id=m[0]) }}">{{ m[0] }}</a></td>
                <td class="copyable">{{ m[1] }}</td>
                <td class="copyable memory-col">{{ m[2] }}</td>
                <td class="copyable">{{ m[3] }}</td>
                <td class="copyable">{{ m[4] }}</td>
                <td class="copyable">{{ m[5] }}</td>
                <td class="copyable">{{ m[6] }}</td>
                <td class="copyable">{{ 'Yes' if m[7] else 'No' }}</td>
                <td class="copyable keywords-col">{{ m[8] or '' }}</td>
                <td class="copyable">{{ m[9] or '' }}</td>
                <td style="text-align: center;">
                    <input type="checkbox" class="approve-checkbox" name="approve_ids" value="{{ m[0] }}" {% if m[7] %}checked disabled{% endif %} onchange="this.form.submit()">
                </td>
                <td>
                    <a href="{{ url_for('edit_memory', memory_id=m[0]) }}">Edit</a>
                </td>
            </tr>
        {% endfor %}
        </tbody>
    </table>
    </form>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def review():
    if request.method == 'POST':
        approve_ids = request.form.getlist('approve_ids')
        for memory_id in approve_ids:
            mark_reviewed(memory_id)
        return redirect(url_for('review', **request.args))
    keyword = request.args.get('keyword') or None
    topic = request.args.get('topic') or None
    show_reviewed = bool(request.args.get('show_reviewed'))
    memories = query_memories(keyword, topic, show_reviewed)
    tags, topics = get_unique_tags_and_topics()
    return render_template_string(TEMPLATE, memories=memories, request=request, tags=tags, topics=topics)

@app.route('/edit/<memory_id>', methods=['GET', 'POST'])
def edit_memory(memory_id):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # Fetch memory
    c.execute('SELECT id, memory FROM memories WHERE id = ?', (memory_id,))
    mem_row = c.fetchone()
    if not mem_row:
        conn.close()
        return 'Memory not found', 404
    # Fetch keywords
    c.execute('SELECT tag FROM memory_tags WHERE memory_id = ?', (memory_id,))
    keywords = [row[0] for row in c.fetchall()]
    # Fetch topic
    c.execute('SELECT topic FROM memory_topic WHERE memory_id = ?', (memory_id,))
    topic_row = c.fetchone()
    topic = topic_row[0] if topic_row else ''
    # Get all unique tags and topics for dropdowns
    all_tags, all_topics = get_unique_tags_and_topics()
    if request.method == 'POST':
        # Update keywords
        new_keywords = request.form.get('keywords', '').split(',')
        new_keywords = [k.strip() for k in new_keywords if k.strip()]
        c.execute('DELETE FROM memory_tags WHERE memory_id = ?', (memory_id,))
        for kw in new_keywords:
            c.execute('INSERT OR IGNORE INTO memory_tags (memory_id, tag) VALUES (?, ?)', (memory_id, kw))
        # Update topic
        new_topic = request.form.get('topic', '').strip()
        c.execute('DELETE FROM memory_topic WHERE memory_id = ?', (memory_id,))
        if new_topic:
            c.execute('INSERT INTO memory_topic (memory_id, topic) VALUES (?, ?)', (memory_id, new_topic))
        conn.commit()
        conn.close()
        return redirect(url_for('review'))
    conn.close()
    edit_template = '''
    <!DOCTYPE html>
    <html><head><title>Edit Memory</title>
    <style>
        body { font-family: sans-serif; font-size: 13px; }
        label, input, select, button, textarea { font-size: 13px; }
        textarea { width: 100%; min-height: 60px; }
    </style>
    </head><body>
    <h2>Edit Memory</h2>
    <form method="post">
        <div><strong>ID:</strong> {{ mem_row[0] }}</div>
        <div><strong>Memory:</strong><br><textarea readonly>{{ mem_row[1] }}</textarea></div>
        <div><label>Keywords (comma separated):<br>
            <input type="text" name="keywords" value="{{ ', '.join(keywords) }}">
        </label></div>
        <div><label>Topic:<br>
            <select name="topic">
                <option value="">-- None --</option>
                {% for t in all_topics %}
                <option value="{{ t }}" {% if t == topic %}selected{% endif %}>{{ t }}</option>
                {% endfor %}
            </select>
        </label></div>
        <button type="submit">Save</button>
        <a href="{{ url_for('review') }}">Cancel</a>
    </form>
    </body></html>
    '''
    return render_template_string(edit_template, mem_row=mem_row, keywords=keywords, topic=topic, all_topics=all_topics)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
