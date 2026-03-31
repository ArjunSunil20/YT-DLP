import subprocess
import threading
import uuid
import sys
import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='static')
CORS(app)

jobs = {}

def find_ffmpeg():
    """Find ffmpeg on Windows even if not on PATH."""
    import shutil
    # Check PATH first
    path = shutil.which('ffmpeg')
    if path:
        return path
    # Common winget install location
    winget_base = os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\WinGet\Packages')
    if os.path.exists(winget_base):
        for root, dirs, files in os.walk(winget_base):
            for f in files:
                if f.lower() == 'ffmpeg.exe':
                    return os.path.join(root, f)
    # Common manual install locations
    common = [
        r'C:\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe',
        os.path.expandvars(r'%USERPROFILE%\ffmpeg\bin\ffmpeg.exe'),
    ]
    for p in common:
        if os.path.exists(p):
            return p
    return None

def run_download(job_id, url, options):
    jobs[job_id]['status'] = 'running'

    cmd = [sys.executable, '-m', 'yt_dlp', '--newline', '--progress']
    jobs[job_id]['logs'].append(f'Using: {sys.executable} -m yt_dlp')

    # Find and pass ffmpeg location
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        cmd += ['--ffmpeg-location', os.path.dirname(ffmpeg)]
        jobs[job_id]['logs'].append(f'ffmpeg found: {ffmpeg}')
    else:
        jobs[job_id]['logs'].append('WARNING: ffmpeg not found - video and audio may not merge')

    if options.get('audioOnly'):
        cmd += ['-x', '--audio-format', 'mp3']
    else:
        quality = options.get('quality', '1080')
        cmd += ['-f', f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]']
        cmd += ['--merge-output-format', 'mp4']

    if options.get('skipShorts'):
        cmd += ['--match-filter', 'original_url!*=/shorts/ & !is_live']

    output_dir = os.path.join(os.path.expanduser('~'), 'Downloads', 'ytdl')
    os.makedirs(output_dir, exist_ok=True)
    cmd += ['-o', os.path.join(output_dir, '%(channel)s', '%(upload_date>%Y-%m-%d)s - %(title)s.%(ext)s')]
    cmd += ['--download-archive', os.path.join(output_dir, 'archive.txt')]
    cmd += ['--limit-rate', '5M']
    cmd.append(url)

    jobs[job_id]['logs'].append(f'Output folder: {output_dir}')

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding='utf-8',
            errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        jobs[job_id]['pid'] = process.pid

        for line in process.stdout:
            line = line.strip()
            if line:
                jobs[job_id]['logs'].append(line)
                if len(jobs[job_id]['logs']) > 300:
                    jobs[job_id]['logs'] = jobs[job_id]['logs'][-300:]
                if '[download]' in line and '%' in line:
                    try:
                        pct = float(line.split('%')[0].split()[-1])
                        jobs[job_id]['progress'] = round(pct, 1)
                    except:
                        pass

        process.wait()
        if process.returncode == 0:
            jobs[job_id]['status'] = 'done'
        else:
            jobs[job_id]['status'] = 'error'
            jobs[job_id]['error'] = f'yt-dlp exited with code {process.returncode}'
            jobs[job_id]['logs'].append(f'EXIT CODE: {process.returncode}')
    except Exception as e:
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['error'] = str(e)
        jobs[job_id]['logs'].append(f'EXCEPTION: {str(e)}')


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/download', methods=['POST'])
def start_download():
    data = request.json
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    job_id = str(uuid.uuid4())
    jobs[job_id] = {'status': 'pending', 'logs': [], 'progress': 0, 'error': None}
    t = threading.Thread(target=run_download, args=(job_id, url, data.get('options', {})))
    t.daemon = True
    t.start()
    return jsonify({'jobId': job_id})

@app.route('/api/status/<job_id>')
def get_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(job)

@app.route('/api/cancel/<job_id>', methods=['POST'])
def cancel_job(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    pid = job.get('pid')
    if pid:
        try:
            os.kill(pid, 9)
        except:
            pass
    job['status'] = 'cancelled'
    return jsonify({'ok': True})

if __name__ == '__main__':
    app.run(debug=True, port=5050)
