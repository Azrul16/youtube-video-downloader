import imageio_ffmpeg
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import os
import yt_dlp
import uuid
import threading

app = Flask(__name__)
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

downloads = {}  # Track download status


def download_file(url, option, file_id):
    try:
        if option == "video":
            ydl_opts = {
                "format": "bestvideo[height<=1080]+bestaudio/best",
                "merge_output_format": "mp4",
                "outtmpl": f"{DOWNLOAD_DIR}/{file_id}.%(ext)s",
            }
            output_file = f"{file_id}.mp4"
        else:  # audio
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": f"{DOWNLOAD_DIR}/{file_id}.%(ext)s",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            output_file = f"{file_id}.mp3"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        downloads[file_id]["status"] = "ready"
        downloads[file_id]["path"] = os.path.join(DOWNLOAD_DIR, output_file)
    except Exception as e:
        downloads[file_id]["status"] = "error"
        downloads[file_id]["error"] = str(e)


@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


# Fetch video info (title, thumbnail, duration)
@app.route("/info", methods=["POST"])
def info():
    data = request.json
    url = data.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                "title": info.get("title"),
                "thumbnail": info.get("thumbnail"),
                "duration": info.get("duration"),
                "uploader": info.get("uploader")
            })
    except Exception:
        return jsonify({"error": "Invalid YouTube link or video unavailable"}), 400


@app.route("/start_download", methods=["POST"])
def start_download():
    url = request.form.get("url")
    option = request.form.get("option")
    if not url:
        return jsonify({"error": "Please enter a YouTube URL."}), 400

    file_id = str(uuid.uuid4())
    downloads[file_id] = {"status": "downloading"}

    # Start async download
    thread = threading.Thread(target=download_file, args=(url, option, file_id))
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
