import shutil
from flask import Flask, render_template, request, jsonify
import os
from pyembroidery import read_dst, COLOR_CHANGE
from PIL import Image, ImageDraw

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads/'  # Directory for uploaded files
app.secret_key = 'supersecretkey'
user_selected_colors = ["#FF5733", "#33FF57", "#cf2fd0", "#3357FF", "#FFD700", "#000000", "#30D02F", "#36C9B3", "#946B87"]

# Ensure the upload directory exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'dst'}

def get_stitch_count(dst_file_path):
    design = read_dst(dst_file_path)
    stitch_count = len(design.stitches)
    
    # Count estimated colors using COLOR_CHANGE commands
    estimated_colors = 1
    for stitch in design.stitches:
        if stitch[2] == COLOR_CHANGE:
            estimated_colors += 1
    
    return stitch_count, estimated_colors

def get_color_dst_images(dst_file_path, selected_colors=user_selected_colors, output_format='PNG'):
    design = read_dst(dst_file_path)
    
    # Calculate the design bounds
    min_x = min([stitch[0] for stitch in design.stitches])
    min_y = min([stitch[1] for stitch in design.stitches])
    max_x = max([stitch[0] for stitch in design.stitches])
    max_y = max([stitch[1] for stitch in design.stitches])

    width = max_x - min_x + 50
    height = max_y - min_y + 50

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    prev_x, prev_y = None, None
    stitch_color_index = 0

    for stitch in design.stitches:
        if stitch[2] == 1:  # Color change
            stitch_color_index += 1
            stitch_color_index %= len(selected_colors)  # Cycle through selected colors if fewer colors are provided

        x, y = stitch[0] - min_x + 25, stitch[1] - min_y + 25

        if prev_x is not None and prev_y is not None:
            draw.line((prev_x, prev_y, x, y), fill=selected_colors[stitch_color_index], width=1)

        prev_x, prev_y = x, y

    return image

def get_black_dst_images(dst_file_path, output_format='PNG'):
    try:
        design = read_dst(dst_file_path)
        
        # Determine size based on stitch coordinates
        min_x = min([stitch[0] for stitch in design.stitches])
        min_y = min([stitch[1] for stitch in design.stitches])
        max_x = max([stitch[0] for stitch in design.stitches])
        max_y = max([stitch[1] for stitch in design.stitches])

        width = max_x - min_x + 50
        height = max_y - min_y + 50

        # Create an image with a white background
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)

        # Draw stitches
        prev_x, prev_y = None, None
        for stitch in design.stitches:
            x, y = stitch[0] - min_x + 25, stitch[1] - min_y + 25
            if prev_x is not None and prev_y is not None:
                draw.line((prev_x, prev_y, x, y), fill="black", width=1)
            prev_x, prev_y = x, y
            
        output_file_path = os.path.splitext(dst_file_path)[0] + '_black.png'
        image.save(output_file_path, output_format.upper())
        
        return output_file_path 
    except Exception as e:
        print(f"Error processing file {dst_file_path}: {e}")
        return None

@app.route('/')
def index():
    """Render the index page with the upload form."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    files = request.files.getlist('file')
    
    uploaded_files = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = file.filename
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            stitch_count, color_count = get_stitch_count(file_path)
            
            if stitch_count is not None:
                file_data = {
                    'filename': filename,
                    'stitch_count': stitch_count,
                    'colors': color_count,
                    'hours': round(stitch_count / 20000, 3),
                }
                uploaded_files.append(file_data)
    
    if uploaded_files:
        return jsonify(uploaded_files[0]), 200
    else:
        return jsonify({'error': 'No files uploaded or processing error'}), 400

@app.route('/generate_black_image/<filename>', methods=['GET'])
def generate_black_image(filename):
    if allowed_file(filename):
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        if os.path.exists(filepath):
            output_image_path = get_black_dst_images(filepath)
            
            if output_image_path:
                return jsonify({'image_path': f'uploads/{os.path.basename(output_image_path)}'}), 200
            else:
                return jsonify({'error': 'Error generating black and white image'}), 500
        else:
            return jsonify({'error': 'File not found'}), 404
    else:
        return jsonify({'error': f'{filename} is not a valid DST file.'}), 400

@app.route('/generate_color_image/<filename>', methods=['GET'])
def generate_color_image(filename):
    if allowed_file(filename):
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        if os.path.exists(filepath):
            image = get_color_dst_images(filepath)
            
            if image:
                output_image_path = os.path.splitext(filepath)[0] + '_color.png'
                image.save(output_image_path)
                return jsonify({'image_path': output_image_path}), 200
            else:
                return jsonify({'error': 'Error generating color image'}), 500
        else:
            return jsonify({'error': 'File not found'}), 404
    else:
        return jsonify({'error': f'{filename} is not a valid DST file.'}), 400

@app.route('/clear_history', methods=['POST'])
def clear_history():
    upload_folder = app.config['UPLOAD_FOLDER']

    # Remove all files in the upload folder
    for filename in os.listdir(upload_folder):
        file_path = os.path.join(upload_folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')
            return jsonify({'error': 'An error occurred while clearing history.'}), 500

    return jsonify({'message': 'History cleared successfully.'}), 200

if __name__ == "__main__":
    app.run(debug=True)
