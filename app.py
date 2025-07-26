import os
import json
from flask import Flask, request, render_template, send_file
import whisper
import re
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import logging

app = Flask(__name__, template_folder="templates", static_folder="static")


nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    model = whisper.load_model("tiny")
except Exception as e:
    logger.error(f"Failed to load Whisper model: {e}")
    raise Exception("Model loading failed")


CATEGORIES = {
    "room_size": ["square feet", "dimensions", "size", "area", "large", "small", "medium"],
    "colors": ["color", "paint", "hue", "shade", "white", "blue", "red", "green", "yellow", "black", "gray"],
    "furniture": ["sofa", "chair", "table", "bed", "desk", "cabinet", "shelf"],
    "style": ["modern", "traditional", "minimalist", "rustic", "industrial", "bohemian"],
    "materials": ["wood", "metal", "glass", "fabric", "leather", "stone"],
    "lighting": ["lamp", "chandelier", "lighting", "light", "bright", "dim"]
}


def extract_categories(transcript: str) -> dict:
    tokens = word_tokenize(transcript.lower())
    stop_words = set(stopwords.words('english'))
    filtered_tokens = [word for word in tokens if word not in stop_words]
    
    results = {category: [] for category in CATEGORIES}
    
    size_pattern = r'(\d+\.?\d*\s*(?:square\s*feet|sq\s*ft|feet\s*by\s*feet|meters))'
    sizes = re.findall(size_pattern, transcript.lower())
    results["room_size"].extend(sizes)
    
  
    for category, keywords in CATEGORIES.items():
        if category != "room_size":
            for word in filtered_tokens:
                if word in keywords and word not in results[category]:
                    results[category].append(word)
    
    return results


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
          
            if 'file' not in request.files:
                return render_template("index.html", error="No file uploaded")
            
            file = request.files['file']
            if file.filename == '':
                return render_template("index.html", error="No file selected")
            
  
            allowed_extensions = {'.mp3', '.wav', '.m4a', '.mp4', '.mpeg', '.ogg'}
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in allowed_extensions:
                return render_template("index.html", error="Unsupported file format")
            

            temp_file_path = f"temp_{file.filename}"
            file.save(temp_file_path)
            
            result = model.transcribe(temp_file_path, language="en")
            transcript = result["text"]
            segments = result["segments"]
            

            categories = extract_categories(transcript)
            
     
            os.makedirs("transcripts", exist_ok=True)
            text_filename = f"transcripts/{file.filename}.txt"
            with open(text_filename, "w", encoding="utf-8") as f:
                f.write(transcript)
            

            json_filename = f"transcripts/{file.filename}.json"
            with open(json_filename, "w", encoding="utf-8") as f:
                json.dump({"transcript": transcript, "segments": segments, "categories": categories}, f, indent=4)
            
 
            os.remove(temp_file_path)
            
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

@app.route("/download/text/<path:filename>")
def download_text(filename):
    file_path = f"transcripts/{filename}"
    if not os.path.exists(file_path):
        return render_template("index.html", error="File not found")
    return send_file(file_path, as_attachment=True)

@app.route("/download/json/<path:filename>")
def download_json(filename):
    file_path = f"transcripts/{filename}"
    if not os.path.exists(file_path):
        return render_template("index.html", error="File not found")
    return send_file(file_path, as_attachment=True, mimetype='application/json')


if __name__ == "__main__":
    app.run(debug=True)