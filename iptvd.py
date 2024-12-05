#!/bin/python3

import sqlite3
import re
import requests
import sys
import subprocess
import threading
import math

# Path to database file
database = 'playlist.db'
# Max number of threads to check sources
max_threads = 20
# Hours between check attemptions
check_period = 12

def parse_m3u(text):
    """
    Parsing .m3u file
    Returns list with TV programs
    """
    playlist = []
    current_entry = {}
    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF:"):
            # Extract from EXTINF tag
            # Program name
            match = re.search(r'#EXTINF.*,(.*)', line)
            if match:
                name = match.group(1)
                name = re.sub(r'\([^\)]*\)', '', name, count = 99)
                name = re.sub(r'\[[^\]]*\]', '', name, count = 99)
                name = re.sub(r'\?', '', name, count = 99)
                name = re.sub(r'  ', ' ', name, count = 99)
                current_entry['name'] = name.strip()
            # Group
            match = re.search(r'.*group-title *= *"([^"]*)".*', line)
            if match:
                group = match.group(1).strip();
                if group.startswith('Обще') or group.startswith('Общи'):
                    group = 'Общественные'
                if group.startswith('Кино') or group.find('кино') >= 0 or group.startswith('Фильм'):
                    group = 'Фильмы'
                if group.startswith('Детск'):
                    group = 'Детские'
                if group.startswith('Музык'):
                    group = 'Музыка'
                if group.startswith('Развлека'):
                    group = 'Развлекательные'
                if group.startswith('Спорт'):
                    group = 'Спортивные'
                if group.startswith('Хобб'):
                    group = 'Хобби'
                if group.startswith('Познава'):
                    group = 'Познавательные'
                if group.startswith('Религи'):
                    group = 'Религиозные'
                current_entry['group'] = group.strip()
            # Icon
            match = re.search(r'.*tvg-logo *= *"([^"]*)".*', line)
            if match:
                current_entry['icon'] = match.group(1).strip()
        elif line.startswith("#EXTVLCOPT:"):
            match = re.search(r'.*http-user-agent *= *(.*)', line)
            if match:
                ua = match.group(1).strip()
                if ua.find('Donate') < 0:
                    current_entry['user-agent'] = ua
        elif line and not line.startswith("#"):
            if line.find('50na50') < 0 and (line.startswith('http') or line.startswith('rt')) and current_entry.get('name') != None:
                if current_entry.get('group') == None:
                    current_entry['group'] = 'Разное'
                # Track URL
                current_entry['url'] = line
                # Add entry to list
                playlist.append(current_entry)
            current_entry = {}
    return playlist

def create_database(db_name):
    """
    Creates SQLite database and playlist table
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS playlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            group_name TEXT,
            icon TEXT,
            url TEXT NOT NULL,
            user_agent TEXT,
            active INTEGER,
            checktime TEXT,
            lastonline TEXT
        )
    ''')
    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS playlist_url ON playlist(url)')
    conn.commit()
    conn.close()

def insert_playlist_to_db(db_name, playlist):
    """
    Add parsed playlist to database
    """
    inserted = 0
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    for entry in playlist:
        cursor.execute('SELECT count(*) AS cnt FROM playlist WHERE url=?', (entry.get('url'),))
        cnt = cursor.fetchone()[0]
        if cnt == 0:
            cursor.execute('INSERT INTO playlist (name, group_name, icon, url, user_agent, active) VALUES (?, ?, ?, ?, ?, 0)', (
                entry.get('name'),
                entry.get('group'),
                entry.get('icon'),
                entry.get('url'),
                entry.get('user-agent')
            ))
            inserted = inserted + 1
        else:
            cursor.execute('UPDATE playlist set name=?, group_name=?, icon=?, user_agent=? WHERE url=?', (
                entry.get('name'),
                entry.get('group'),
                entry.get('icon'),
                entry.get('user-agent'),
                entry.get('url'),
            ))
    conn.commit()
    conn.close()
    print(f"Inserted {inserted} new entries")

def get_external_playlist(url):
    """
    Get external playlist from HTTP server
    """
    try:
        response = requests.get(url)
        response.raise_for_status()  # HTTP error?
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error load external playlist: {e}")
    return ''

def get_snapshot(url, user_agent, fileName = 1):
    """
    Create snapshot from videosource
    """
    if user_agent is None or len(user_agent) < 5:
        user_agent = 'Mozilla/5.0 WINK/1.31.1 (AndroidTV/9) HlsWinkPlayer'
    command = [
        "ffmpeg",
        "-y",                   # Yes to all questions
        "-v", "0",              # Be quiet
        "-user_agent", user_agent,
        "-i", url,              # Path
        "-frames:v", "1",       # Snapshots (1 snapshot)
        "-q:v", "20",           # Quality
        f'/tmp/{fileName}.jpg'  # Path to snapshot
    ]
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    timer = threading.Timer(20, proc.kill)
    try:
        timer.start()
        stdout, stderr = proc.communicate()
    finally:
        timer.cancel()
    if proc.returncode == 0:
        return 1
    return 0

def check_thread(threadNum, rows):
    """
    Check source alive in thread
    """
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    for index, row in enumerate(rows):
        alive = get_snapshot(row[1] , row[2], threadNum)
        print(f'{threadNum}: [{index+1}/{len(rows)}] {alive} {row[1]}')
        try:
            cursor.execute('UPDATE playlist SET active=?,checktime=datetime(\'now\') WHERE id=?', (alive, row[0]))
            if alive == 1:
                cursor.execute('UPDATE playlist SET lastonline=datetime(\'now\') WHERE id=?', (row[0],))
            conn.commit()
        except:
            print('Database update error')
    conn.close()

def usage():
    print('''
        Usage: iptvd.py [comand] [argument]
          iptvd.py load [url]
            load external playlist from url in m3u format and save it to database
          iptvd.py save [filename]
            save current playlist to m3u file
          iptvd.py check [max count]
            check sources for availability
          iptvd.py remove
            remove outdated entries from database
    ''')
    exit(1)

def main():
    args = sys.argv[1:]
    if len(args) < 1:
        usage()
    create_database(database)
    # Get .m3u from external source
    if args[0] == 'load':
        text = get_external_playlist(args[1])
        if len(text) == 0:
            exit(1)
        pl = parse_m3u(text)
        insert_playlist_to_db(database, pl)
        exit(0)
    # Availability check
    if args[0] == 'check':
        if len(args) != 2:
            usage()
        conn = sqlite3.connect(database)
        cursor = conn.cursor()
        cursor.execute(f'''
            SELECT id, url, user_agent, active FROM playlist
            WHERE checktime is NULL or checktime < datetime('now', '-{check_period} hours') LIMIT ?
        ''', (args[1],))
        rows = cursor.fetchall()
        conn.close()
        threads = []
        tcount = max_threads
        if len(rows) <= tcount:
            tcount = 1
        rows_step = math.trunc(len(rows) / tcount)
        rows_begin = 0
        for tnum in range(0, tcount):
            trows = []
            rows_end = rows_begin + rows_step
            if tnum == tcount - 1:
                rows_end = len(rows)
            for i in range(rows_begin, rows_end):
                trows.append(rows[i])
            rows_begin = rows_begin + rows_step
            t = threading.Thread(target=check_thread, args=(tnum + 1, trows))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        exit(0)
    # Save playlist
    if args[0] == 'save':
        if len(args) != 2:
            usage()
        conn = sqlite3.connect(database)
        cursor = conn.cursor()
        # Read data from table
        cursor.execute('SELECT name, group_name, icon, url, user_agent FROM playlist WHERE active=1 ORDER BY group_name, name')
        rows = cursor.fetchall()
        # Write to file
        with open(args[1], 'w', encoding='utf-8') as f:
            for row in rows:
                line = f'#EXTINF:-1 group-title="{row[1]}" tvg-logo="{row[2]}",{row[0]}\n'
                f.write(line)
                if not row[4] is None and len(row[4]) > 4:
                    line = f'#EXTVLCOPT:http-user-agent={row[4]}\n'
                    f.write(line)
                line = f'{row[3]}\n'
                f.write(line)
        conn.close()
    # Remove dead entries
    if args[0] == 'remove':
        if len(args) != 1:
            usage()
        conn = sqlite3.connect(database)
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM playlist WHERE active=0 AND NOT checktime IS NULL AND (lastonline IS NULL OR lastonline < datetime('now', '-10 days'))
        ''')
        conn.commit()
        conn.close()

if __name__ == '__main__':
    main()
