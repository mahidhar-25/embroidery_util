import shutil
from flask import Flask, render_template, request, redirect, flash,url_for,jsonify
import os
from pyembroidery import read_dst, COLOR_CHANGE
from PIL import Image, ImageDraw

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads/'  # Directory for uploaded files
app.secret_key = 'supersecretkey'
user_selected_colors = ["#FF5733", "#33FF57","#cf2fd0", "#3357FF", "#FFD700" , "#000000" , "#30D02F" ,"#36C9B3" , "#946B87" ]


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

def convert_dst_to_image_color(dst_file_path,colors_count, selected_colors=user_selected_colors, output_format='PNG'):
    selected_colors = selected_colors[:colors_count]
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

def convert_dst_to_image(dst_file_path, output_format='PNG'):
    try:
        design = read_dst(dst_file_path)
        estimated_colors = 1  # Start with one color
        for stitch in design.stitches:
            if stitch[2] == COLOR_CHANGE:
                estimated_colors += 1
        
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
        
        # Create output file path with _black.png
        
        output_file_path_color = os.path.splitext(dst_file_path)[0] + '_color.png'
        image_color = convert_dst_to_image_color(dst_file_path , estimated_colors)
        image_color.save(output_file_path_color , output_format.upper())
        return len(design.stitches), estimated_colors, output_file_path , output_file_path_color
    except Exception as e:
        print(f"Error processing file {dst_file_path}: {e}")
        return None, None, None

@app.route('/')
def index():
    """Render the index page with the upload form."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    
    files = request.files.getlist('file')
    
    uploaded_files = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Get stitch count and estimated colors
            stitch_count, estimated_colors, output_image , output_color_image= convert_dst_to_image(filepath)

            # Ensure the output image is correctly referenced
            output_image_path = f'uploads/{os.path.basename(output_image)}'
            output_color_image_path = f'uploads/{os.path.basename(output_color_image)}'
            stich_hours = stitch_count / 20000 # type: ignore
            if stitch_count is not None:
                uploaded_files.append({
                'filename': filename,
                'stitch_count': stitch_count,
                'colors': estimated_colors,
                'image': output_image_path,
                "hours": stich_hours,
                'color_image': output_color_image_path  # Ensure this line correctly references the color image path
            })
        else:
            flash(f'{file.filename} is not a valid DST file.')
    
    return render_template('index.html', uploaded_files=uploaded_files)


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
            flash('An error occurred while clearing history.')
            return redirect(url_for('index'))

    flash('History cleared successfully.')
    return redirect(url_for('index'))

@app.route('/upload_single', methods=['POST'])
def upload_single_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})

    file = request.files['file']
    
    if file and allowed_file(file.filename):
        filename = file.filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        stitch_count, estimated_colors, output_image, output_color_image = convert_dst_to_image(filepath)

        if stitch_count is not None:
            stich_hours = stitch_count / 20000  # type: ignore
            uploaded_file_info = {
                'filename': filename,
                'stitch_count': stitch_count,
                'colors': estimated_colors,
                'image': f'uploads/{os.path.basename(output_image)}',
                "hours": stich_hours,
                'color_image': f'uploads/{os.path.basename(output_color_image)}'
            }
            return jsonify(uploaded_file_info)
        else:
            return jsonify({'error': 'Error processing file'})
    else:
        return jsonify({'error': f'{file.filename} is not a valid DST file.'})

if __name__ == "__main__":
    app.run(debug=True)
