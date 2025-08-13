from flask import Flask, render_template, request, jsonify, send_file
import os
import subprocess
import threading
import uuid
import imageio_ffmpeg

app = Flask(__name__)
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
downloads = {}  # {file_id: {"status": "downloading/ready/error", "progress": 0, "path": "", "error": ""}}


def clean_url(url):
    """Remove query parameters from YouTube URL."""
    return url.split("?")[0] if url else url


def run_yt_dlp(video_url, option, file_id):
    url = clean_url(video_url)
    file_path = ""
    try:
        if option == "video":
            output_file = f"{file_id}.mp4"
            cmd = [
                "yt-dlp",
                "--ffmpeg-location", imageio_ffmpeg.get_ffmpeg_exe(),
                "-f", "bestvideo[height<=1080]+bestaudio/best",
                "--merge-output-format", "mp4",
                "-o", os.path.join(DOWNLOAD_DIR, output_file),
                url
            ]
        else:  # audio
            output_file = f"{file_id}.mp3"
            cmd = [
                "yt-dlp",
                "--ffmpeg-location", imageio_ffmpeg.get_ffmpeg_exe(),
                "-f", "bestaudio/best",
                "--extract-audio",
                "--audio-format", "mp3",
                "-o", os.path.join(DOWNLOAD_DIR, output_file),
                url
            ]

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        for line in process.stdout:
            if "[download]" in line and "%" in line:
                try:
                    percent = float(line.split("%")[0].split()[-1])
                    downloads[file_id]["progress"] = int(percent)
                except:
                    pass

        process.wait()
        if process.returncode == 0:
            downloads[file_id]["status"] = "ready"
            downloads[file_id]["path"] = os.path.join(DOWNLOAD_DIR, output_file)
        else:
            downloads[file_id]["status"] = "error"
            downloads[file_id]["error"] = f"Download failed. Check URL."
    except Exception as e:
        downloads[file_id]["status"] = "error"
        if "Sign in to confirm" in str(e):
            downloads[file_id]["error"] = "Video requires login or is restricted."
        else:
            downloads[file_id]["error"] = str(e)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/info", methods=["POST"])
def info():
    data = request.json
    url = clean_url(data.get("url"))
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    try:
        cmd = ["yt-dlp", "--dump-json", "--no-warnings", "--skip-download", url]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 or not result.stdout.strip():
            return jsonify({"error": "Video unavailable or restricted"}), 400
        import json
        info = json.loads(result.stdout)
        return jsonify({
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "uploader": info.get("uploader"),
            "duration": info.get("duration")
        })
    except Exception as e:
        return jsonify({"error": "Cannot fetch video info. " + str(e)}), 400


@app.route("/start_download", methods=["POST"])
def start_download():
    url = request.form.get("url")
    option = request.form.get("option")
    if not url:
        return jsonify({"error": "Please enter a YouTube URL."}), 400

    file_id = str(uuid.uuid4())
    downloads[file_id] = {"status": "downloading", "progress": 0, "path": "", "error": ""}

    thread = threading.Thread(target=run_yt_dlp, args=(url, option, file_id))
    thread.start()

    return jsonify({"file_id": file_id})


@app.route("/status/<file_id>")
def status(file_id):
    info = downloads.get(file_id)
    if not info:
        return jsonify({"status": "invalid"}), 404
    return jsonify(info)


@app.route("/download/<file_id>")
def download(file_id):
    info = downloads.get(file_id)
    if not info or info.get("status") != "ready":
        return "File not ready", 404
    file_path = info["path"]
    response = send_file(file_path, as_attachment=True)
    try:
        os.remove(file_path)
        downloads.pop(file_id, None)
    except:
        pass
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
