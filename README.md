# iptvd
This simple program downloads external playlists (you need to specify the URL of the playlist in m3u format), checks the sources for availability and creates a new playlist.

## Usage
iptvd.py [comand] [argument]
```
iptvd.py load [url]
    load external playlist from url in m3u format and save it to database
iptvd.py save [filename]
    save current playlist to m3u file
iptvd.py check [max count]
    check sources for availability
iptvd.py remove
    remove outdated entries from database
```
