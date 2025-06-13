import os
import uuid
from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename
from PIL import Image, ImageFilter
import io
import base64

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  


os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upscale_image(image_path, scale_factor):
    """Upscale image using Pillow with high-quality resampling"""
    try:
        with Image.open(image_path) as img:
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            

            width, height = img.size
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            
 
            upscaled = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
         
            upscaled = upscaled.filter(ImageFilter.UnsharpMask(radius=0.5, percent=150, threshold=3))
            
            return upscaled
    except Exception as e:
        print(f"Error upscaling image: {e}")
        return None

@app.route('/')
def index():
    return redirect("https://vebnox.com/imgups.html")

# @app.route('/')
# def index():
#     return render_template('https://vebnox.com/imgups.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        scale_factor = float(request.form.get('scale_factor', 2))
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Please upload PNG, JPG, JPEG, or WebP files.'}), 400
        
     
        filename = secure_filename(file.filename)
        unique_id = str(uuid.uuid4())
        file_extension = filename.rsplit('.', 1)[1].lower()
        original_filename = f"{unique_id}_original.{file_extension}"
        upscaled_filename = f"{unique_id}_upscaled.{file_extension}"
        
     
        original_path = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
        file.save(original_path)
        
     
        upscaled_image = upscale_image(original_path, scale_factor)
        if upscaled_image is None:
            return jsonify({'error': 'Failed to process image'}), 500
        
 
        upscaled_path = os.path.join(app.config['UPLOAD_FOLDER'], upscaled_filename)
        upscaled_image.save(upscaled_path, quality=95, optimize=True)
        

        original_size = os.path.getsize(original_path)
        upscaled_size = os.path.getsize(upscaled_path)
        
        with Image.open(original_path) as orig_img:
            orig_dimensions = orig_img.size
        
        upscaled_dimensions = upscaled_image.size
        
        return jsonify({
            'success': True,
            'original_url': f'/static/uploads/{original_filename}',
            'upscaled_url': f'/static/uploads/{upscaled_filename}',
            'original_size': original_size,
            'upscaled_size': upscaled_size,
            'original_dimensions': orig_dimensions,
            'upscaled_dimensions': upscaled_dimensions,
            'scale_factor': scale_factor,
            'download_url': f'/download/{upscaled_filename}'
        })
        
    except Exception as e:
        print(f"Error processing upload: {e}")
        return jsonify({'error': 'An error occurred while processing your image'}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=f"upscaled_{filename}")
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Download failed'}), 500

# if __name__ == '__main__':
#     app.run(debug=True, port=5000)

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)    
