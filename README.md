# iptvd
This simple program loads external playlists (you must specify url to playlist in m3u format), ckecks sources for availability and creates new playlist.

## Usage
iptvd.py [comand] [argument]

iptvd.py load [url]
    load external playlist from url in m3u format and save it to database
iptvd.py save [filename]
    save current playlist to m3u file
iptvd.py check [max count]
    check sources for availability
iptvd.py remove
    remove outdated entries from database
