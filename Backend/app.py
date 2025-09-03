import os
import uuid
import time
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory, redirect
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from PIL import Image, ImageFilter, UnidentifiedImageError
from flask_cors import CORS

# ---------------------------
# Configuration (env-driven)
# ---------------------------
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", BASE_DIR / "static" / "uploads"))
MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))  # default 16 MB
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://frontendimageupscaler.netlify.app/")  # e.g. https://your-frontend.netlify.app
FILE_RETENTION_HOURS = int(os.environ.get("FILE_RETENTION_HOURS", 6))  # delete after 6 hours by default

# ---------------------------
# App & Logging
# ---------------------------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)

# Configure CORS: allow only your frontend origin if provided, else allow none (safe default)
if FRONTEND_URL:
    CORS(app, origins=[FRONTEND_URL])
else:
    # If FRONTEND_URL not set, still allow all origins for quick testing — but set FRONTEND_URL in production!
    CORS(app)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("image-upscaler")

# Ensure upload directory exists
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------
# Helpers
# ---------------------------
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_image_file(path: Path) -> bool:
    """Use pillow verify to ensure the file is a valid image."""
    try:
        with Image.open(path) as im:
            im.verify()  # verify does not load full image but checks format
        return True
    except (UnidentifiedImageError, Exception) as e:
        logger.warning("Image validation failed for %s: %s", path, e)
        return False

def upscale_image(image_path: Path, scale_factor: float) -> Image.Image | None:
    try:
        with Image.open(image_path) as img:
            # convert to RGB for consistent processing
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            width, height = img.size
            new_width = max(1, int(width * scale_factor))
            new_height = max(1, int(height * scale_factor))
            # high-quality resampling
            upscaled = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            upscaled = upscaled.filter(ImageFilter.UnsharpMask(radius=0.5, percent=150, threshold=3))
            return upscaled
    except Exception as e:
        logger.exception("Upscale failed for %s", image_path)
        return None

def schedule_cleanup():
    """Background cleanup thread that removes old files."""
    def cleanup():
        while True:
            try:
                now = datetime.utcnow()
                cutoff = now - timedelta(hours=FILE_RETENTION_HOURS)
                deleted = 0
                for f in UPLOAD_DIR.iterdir():
                    try:
                        mtime = datetime.utcfromtimestamp(f.stat().st_mtime)
                        if mtime < cutoff:
                            f.unlink(missing_ok=True)
                            deleted += 1
                    except Exception as e:
                        logger.debug("Failed to check/delete %s: %s", f, e)
                if deleted:
                    logger.info("Cleanup removed %d files older than %d hours", deleted, FILE_RETENTION_HOURS)
            except Exception:
                logger.exception("Error during cleanup loop")
            # Sleep for one hour between cleanups
            time.sleep(3600)
    t = threading.Thread(target=cleanup, daemon=True)
    t.start()

# Start cleanup thread
schedule_cleanup()

# ---------------------------
# Error handlers
# ---------------------------
@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    return jsonify({"error": "File too large", "max_bytes": app.config["MAX_CONTENT_LENGTH"]}), 413

# ---------------------------
# Routes
# ---------------------------
@app.route("/", methods=["GET"])
def root():
    """Optional redirect to frontend or simple status."""
    if FRONTEND_URL:
        return redirect(FRONTEND_URL)
    return jsonify({"status": "ok", "message": "Image Upscaler backend running"})

@app.route("/upload", methods=["POST"])
def upload():
    try:
        # Validate file presence
        if "file" not in request.files:
            return jsonify({"error": "Missing file field (name must be 'file')"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400
        if not allowed_file(file.filename):
            return jsonify({"error": "Invalid file type", "allowed": list(ALLOWED_EXTENSIONS)}), 400

        # Parse scale factor
        scale_raw = request.form.get("scale_factor", "2")
        try:
            scale = float(scale_raw)
            if scale <= 0 or scale > 10:
                return jsonify({"error": "scale_factor must be >0 and <=10"}), 400
        except ValueError:
            return jsonify({"error": "scale_factor must be numeric"}), 400

        # Save to disk securely
        safe_name = secure_filename(file.filename)
        ext = safe_name.rsplit(".", 1)[1].lower()
        uid = uuid.uuid4().hex
        original_name = f"{uid}_original.{ext}"
        upscaled_name = f"{uid}_upscaled.{ext}"
        original_path = UPLOAD_DIR / original_name
        upscaled_path = UPLOAD_DIR / upscaled_name

        file.save(original_path)
        logger.info("Saved upload: %s", original_path)

        # Validate actual image content to avoid invalid files
        if not validate_image_file(original_path):
            original_path.unlink(missing_ok=True)
            return jsonify({"error": "Uploaded file is not a valid image"}), 400

        # Perform upscale
        upscaled_img = upscale_image(original_path, scale)
        if upscaled_img is None:
            return jsonify({"error": "Image processing failed"}), 500

        # Save upscaled image
        try:
            upscaled_img.save(upscaled_path, quality=95, optimize=True)
        except Exception:
            logger.exception("Failed saving upscaled image")
            return jsonify({"error": "Failed to save processed image"}), 500

        # Build response
        original_size = original_path.stat().st_size
        upscaled_size = upscaled_path.stat().st_size
        with Image.open(original_path) as oi:
            orig_dims = oi.size
        up_dims = upscaled_img.size

        response = {
            "success": True,
            "original_url": f"/static/uploads/{original_name}",
            "upscaled_url": f"/static/uploads/{upscaled_name}",
            "original_size": original_size,
            "upscaled_size": upscaled_size,
            "original_dimensions": orig_dims,
            "upscaled_dimensions": up_dims,
            "scale_factor": scale,
            "download_url": f"/download/{upscaled_name}",
        }
        logger.info("Processed %s -> %s", original_name, upscaled_name)
        return jsonify(response), 200

    except Exception:
        logger.exception("Unexpected error in upload")
        return jsonify({"error": "Server error occurred"}), 500

@app.route("/download/<path:filename>", methods=["GET"])
def download(filename):
    # Restrict to upload directory
    try:
        # Avoid directory traversal by only allowing filenames in UPLOAD_DIR
        file_path = UPLOAD_DIR / filename
        if not file_path.exists():
            return jsonify({"error": "File not found"}), 404
        # send_from_directory ensures safe send
        return send_from_directory(directory=str(UPLOAD_DIR), path=filename, as_attachment=True, download_name=f"upscaled_{filename}")
    except Exception:
        logger.exception("Download error")
        return jsonify({"error": "Download failed"}), 500

# ---------------------------
# Run (production should use gunicorn)
# ---------------------------
if __name__ == "__main__":
    # Local dev fallback (not for production)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
