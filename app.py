import os
import json
from flask import Flask, request, render_template, send_file
import whisper
import re
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import logging

# Initialize Flask app
app = Flask(__name__, template_folder="templates", static_folder="static")

# Download NLTK data
nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load Whisper model
try:
    model = whisper.load_model("base")
except Exception as e:
    logger.error(f"Failed to load Whisper model: {e}")
    raise Exception("Model loading failed")

# Define interior design categories and keywords
CATEGORIES = {
    "room_size": ["square feet", "dimensions", "size", "area", "large", "small", "medium"],
    "colors": ["color", "paint", "hue", "shade", "white", "blue", "red", "green", "yellow", "black", "gray"],
    "furniture": ["sofa", "chair", "table", "bed", "desk", "cabinet", "shelf"],
    "style": ["modern", "traditional", "minimalist", "rustic", "industrial", "bohemian"],
    "materials": ["wood", "metal", "glass", "fabric", "leather", "stone"],
    "lighting": ["lamp", "chandelier", "lighting", "light", "bright", "dim"]
}

# Function to extract categories from transcript
def extract_categories(transcript: str) -> dict:
    tokens = word_tokenize(transcript.lower())
    stop_words = set(stopwords.words('english'))
    filtered_tokens = [word for word in tokens if word not in stop_words]
    
    results = {category: [] for category in CATEGORIES}
    
    # Room size extraction with regex for numbers and units
    size_pattern = r'(\d+\.?\d*\s*(?:square\s*feet|sq\s*ft|feet\s*by\s*feet|meters))'
    sizes = re.findall(size_pattern, transcript.lower())
    results["room_size"].extend(sizes)
    
    # Extract other categories based on keywords
    for category, keywords in CATEGORIES.items():
        if category != "room_size":
            for word in filtered_tokens:
                if word in keywords and word not in results[category]:
                    results[category].append(word)
    
    return results

# Route for the main page
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            # Validate file upload
            if 'file' not in request.files:
                return render_template("index.html", error="No file uploaded")
            
            file = request.files['file']
            if file.filename == '':
                return render_template("index.html", error="No file selected")
            
            # Validate file type
            allowed_extensions = {'.mp3', '.wav', '.m4a', '.mp4', '.mpeg', '.ogg'}
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in allowed_extensions:
                return render_template("index.html", error="Unsupported file format")
            
            # Save uploaded file temporarily
            temp_file_path = f"temp_{file.filename}"
            file.save(temp_file_path)
            
            # Transcribe audio using Whisper
            result = model.transcribe(temp_file_path, language="en")
            transcript = result["text"]
            segments = result["segments"]
            
            # Extract categories
            categories = extract_categories(transcript)
            
            # Save transcript as text
            os.makedirs("transcripts", exist_ok=True)
            text_filename = f"transcripts/{file.filename}.txt"
            with open(text_filename, "w", encoding="utf-8") as f:
                f.write(transcript)
            
            # Save transcript as JSON
            json_filename = f"transcripts/{file.filename}.json"
            with open(json_filename, "w", encoding="utf-8") as f:
                json.dump({"transcript": transcript, "segments": segments, "categories": categories}, f, indent=4)
            
            # Clean up temporary file
            os.remove(temp_file_path)
            
            # Prepare table data
            table_data = [
                {"Category": category.title(), "Details": ", ".join(details) if details else "Not mentioned"}
                for category, details in categories.items()
            ]
            
            return render_template(
                "index.html",
                transcript=transcript,
                categories=table_data,
                text_file=text_filename,
                json_file=json_filename
            )
        
        except Exception as e:
            logger.error(f"Error processing file: {e}")
            return render_template("index.html", error=str(e))
    
    return render_template("index.html")

# Route to download text file
@app.route("/download/text/<path:filename>")
def download_text(filename):
    file_path = f"transcripts/{filename}"
    if not os.path.exists(file_path):
        return render_template("index.html", error="File not found")
    return send_file(file_path, as_attachment=True)

# Route to download JSON file
@app.route("/download/json/<path:filename>")
def download_json(filename):
    file_path = f"transcripts/{filename}"
    if not os.path.exists(file_path):
        return render_template("index.html", error="File not found")
    return send_file(file_path, as_attachment=True, mimetype='application/json')

if __name__ == "__main__":
    app.run(debug=True)