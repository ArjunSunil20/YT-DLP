# ytdl — YouTube Channel Downloader

A minimalist web UI for downloading YouTube channels using yt-dlp.

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the server
python app.py
```

Then open **http://localhost:5050** in your browser.

## Usage

1. Paste a YouTube channel URL (e.g. `https://www.youtube.com/@mkbhd`)
2. Set options: audio only, skip shorts, quality
3. Click **Download**
4. Monitor progress — click **logs** to see live yt-dlp output

## Where files are saved

Downloads go to `~/Downloads/ytdl/<ChannelName>/`

An `archive.txt` is kept so re-running skips already downloaded videos.

## Notes

- Speed is capped at 5MB/s by default (edit `app.py` to change)
- Multiple downloads can run simultaneously
- Click **stop** to cancel a running download
