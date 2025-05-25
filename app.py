from flask import Flask, request, render_template, send_file, redirect, url_for, session, send_from_directory, jsonify, flash
import io
import os
import requests
import base64
import json
import re
import logging
import openai
from dotenv import load_dotenv
from flask_session import Session
from fuzzywuzzy import fuzz, process
import time
import asyncio
import aiohttp
from bs4 import BeautifulSoup  # Add this import for web scraping
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from reportlab.pdfgen import canvas
import sqlite3
import datetime
import firebase_admin
from firebase_admin import credentials, initialize_app, auth, firestore, db
from functools import wraps
from flask import g
from PIL import Image
import tempfile
try:
    from pdf2image import convert_from_bytes
except ImportError:
    convert_from_bytes = None
import jwt
from datetime import datetime, timedelta
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.backends import default_backend

# Define the login_required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First check Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split('Bearer ')[1]
            decoded_token = verify_firebase_token(token)
            if decoded_token:
                g.user = decoded_token
                # Update session if not exists
                if 'user' not in session:
                    session['user'] = {
                        'uid': decoded_token.get('uid', ''),
                        'email': decoded_token.get('email', ''),
                        'token': token
                    }
                return f(*args, **kwargs)
        
        # Then check session
        if 'user' in session:
            # Try session token
            session_token = session['user'].get('token')
            if session_token:
                decoded_token = verify_firebase_token(session_token)
                if decoded_token:
                    g.user = decoded_token
                    return f(*args, **kwargs)
            
            # If session token fails, try Firebase token
            firebase_token = session['user'].get('firebase_token')
            if firebase_token:
                decoded_token = verify_firebase_token(firebase_token)
                if decoded_token:
                    g.user = decoded_token
                    # Update session token
                    session['user']['token'] = firebase_token
                    return f(*args, **kwargs)

        # If no valid authentication found
        logging.warning("No valid authentication found")
        session.clear()
        
        # Check if it's an API request
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Authentication required'}), 401
        
        # For regular requests, redirect to login
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('login'))

    return decorated_function

# ------------------ Additional Imports for AI Consultant ------------------
import numpy as np
import pandas as pd
import pickle
from collections import defaultdict
from textblob import TextBlob

# ------------------ Load Environment Variables ------------------
load_dotenv()

# ------------------ Initialize Flask App ------------------
app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

# ------------------ API Keys & Configurations ------------------
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
gemini_api_key = os.getenv("GEMINI_API_KEY")
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
INFERMEDICA_APP_ID = os.getenv("INFERMEDICA_APP_ID", "")
INFERMEDICA_APP_KEY = os.getenv("INFERMEDICA_APP_KEY", "")

if not gemini_api_key or not GOOGLE_API_KEY or not FIREBASE_API_KEY:
    logging.error("⚠️ Missing API Keys! Ensure they are set correctly.")
    exit(1)

# ------------------ Configure Secure Flask Session ------------------
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Use timedelta directly
app.config['SESSION_USE_SIGNER'] = True
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "supersecretkey")
Session(app)

# Initialize Firebase Admin SDK
try:
    # Check if Firebase Admin is already initialized
    if not firebase_admin._apps:
        cred = credentials.Certificate("sample-fe05e-firebase-adminsdk-fbsvc-530bbf15e5.json")
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://sample-fe05e-default-rtdb.asia-southeast1.firebasedatabase.app/',
            'projectId': 'sample-fe05e'
        })
        logging.info("Firebase Admin SDK initialized successfully.")
        logging.info(f"Service account email: {cred.service_account_email}")
    else:
        logging.info("Firebase Admin SDK already initialized.")
except Exception as e:
    logging.error(f"Error initializing Firebase Admin SDK: {str(e)}")
    raise e

def load_firebase_certificates():
    """Load Firebase certificates from file"""
    try:
        with open('firebase_certs.json', 'r') as f:
            certs_data = json.load(f)
            certs = {}
            for kid, cert_pem in certs_data.items():
                cert = load_pem_x509_certificate(cert_pem.encode(), default_backend())
                certs[kid] = cert.public_key()
            return certs
    except Exception as e:
        logging.error(f"Error loading Firebase certificates: {e}")
        return {}

def verify_firebase_token(token):
    """Verify either a Firebase token or a session token"""
    if not token:
        return None
        
    try:
        # First try to verify with Firebase Admin SDK
        try:
            decoded_token = auth.verify_id_token(token)
            return decoded_token
        except Exception as firebase_error:
            logging.debug(f"Firebase Admin verification failed, trying session token: {firebase_error}")
            
            # If Firebase Admin fails, try session token
            try:
                # Get the unverified header to get the key ID
                unverified_header = jwt.get_unverified_header(token)
                kid = unverified_header.get('kid')
                
                if kid:
                    # Load certificates
                    certs = load_firebase_certificates()
                    if kid in certs:
                        # Verify the token with the correct public key
                        decoded_token = jwt.decode(
                            token,
                            certs[kid],
                            algorithms=['RS256'],
                            audience='sample-fe05e',  # Your Firebase project ID
                            options={"verify_exp": True}
                        )
                        return decoded_token
                    else:
                        logging.error(f"Certificate not found for kid: {kid}")
                        return None
                else:
                    # If no kid in header, try to verify as a session token
                    with open('sample-fe05e-firebase-adminsdk-fbsvc-530bbf15e5.json', 'r') as f:
                        service_account = json.load(f)
                        private_key = service_account['private_key']
                    
                    decoded_token = jwt.decode(
                        token,
                        private_key,
                        algorithms=['RS256'],
                        options={"verify_exp": True}
                    )
                    return decoded_token
                    
            except jwt.ExpiredSignatureError:
                logging.error("Token has expired")
                return None
            except jwt.InvalidTokenError as e:
                logging.error(f"Invalid token: {e}")
                return None
            except Exception as e:
                logging.error(f"Error verifying token: {e}")
                return None
                
    except Exception as e:
        logging.error(f"Error in token verification: {str(e)}")
        return None

def create_session_token(user_data):
    """Create a session token with user data"""
    try:
        # Read the service account file
        with open('sample-fe05e-firebase-adminsdk-fbsvc-530bbf15e5.json', 'r') as f:
            service_account = json.load(f)
            private_key = service_account['private_key']
            client_email = service_account['client_email']
            project_id = service_account['project_id']

        # Create token payload
        payload = {
            'uid': user_data['localId'],
            'email': user_data.get('email', ''),
            'iss': client_email,
            'sub': client_email,
            'aud': project_id,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=1)
        }

        # Create token using RS256 algorithm
        token = jwt.encode(payload, private_key, algorithm='RS256')
        return token
    except Exception as e:
        logging.error(f"Error creating session token: {e}")
        return None

# --- Medicine Price Scraping Function with Database Integration ---
def search_medicine_prices(medicine_name):
    results = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    platforms = {
        "Truemeds": {
            "url": f"https://www.truemeds.in/search/{medicine_name}",
            "name_class": "sc-a39eeb4f-12 daYLth",
            "price_class": "sc-a39eeb4f-17 iwZSqt"
        },
        "PharmEasy": {
            "url": f"https://pharmeasy.in/search/all?name={medicine_name}",
            "name_class": "ProductCard_medicineName__Uzjm7",
            "price_class": "ProductCard_unitPriceDecimal__Ur26V"
        },
        "Tata 1mg": {
            "url": f"https://www.1mg.com/search/all?filter=true&name={medicine_name}",
            "name_class": "style__pro-title___3G3rr",
            "price_class": "style__price-tag___KzOkY"
        },
        "Netmeds": {
            "url": f"https://www.netmeds.com/catalogsearch/result/{medicine_name}/all",
            "name_class": "clsgetname",
            "price_class": "final-price"
        }
    }

    def scrape_platform(platform, config):
        try:
            logging.info(f"Scraping {platform} for medicine: {medicine_name}")
            response = requests.get(config['url'], headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            names = soup.find_all(class_=config['name_class'])
            prices = soup.find_all(class_=config['price_class'])

            if not names or not prices:
                logging.warning(f"No data found on {platform} for '{medicine_name}'")
                return []

            platform_results = []
            for name, price in zip(names, prices):
                scraped_name = name.text.strip().lower()
                search_term = medicine_name.lower()

                # Allow partial matches using substring search or fuzzy matching
                if search_term in scraped_name or fuzz.partial_ratio(search_term, scraped_name) > 80:
                    platform_results.append({
                        "pharmacy": platform,
                        "name": name.text.strip(),
                        "price": price.text.strip()
                    })

            return platform_results

        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to scrape {platform}: {str(e)}")
            return []

    for platform, config in platforms.items():
        results.extend(scrape_platform(platform, config))

    return results


# --- Route: Medicine Search Page ---
@app.route("/medicine", methods=["GET", "POST"])
def medicine_search():
    if request.method == "POST":
        medicine_name = request.form.get("medicine_name")
        if not medicine_name:
            return redirect(url_for("medicine_search"))

        # Fetch results directly without saving to the database
        results = search_medicine_prices(medicine_name)

        return render_template("medicine_search.html", results=results, medicine_name=medicine_name)

    return render_template("medicine_search.html")

# --- API Route: Medicine Search JSON Response ---
@app.route("/medicine-search", methods=["GET"])
def medicine_search_api():
    medicine_name = request.args.get("name")
    if not medicine_name:
        return jsonify({"error": "Medicine name is required"}), 400

    try:
        results = search_medicine_prices(medicine_name)
        if not results:
            logging.info(f"No results found for '{medicine_name}'")
            return jsonify({"message": f"No results found for '{medicine_name}'"}), 404

        return jsonify(results)
    except RuntimeError as e:
        logging.error(f"Runtime error: {str(e)}")
        return jsonify({"error": "WebDriver initialization failed. Please check the server logs."}), 500
    except Exception as e:
        logging.error(f"Error fetching data for '{medicine_name}': {str(e)}")
        return jsonify({"error": "An error occurred while fetching data. Please try again later."}), 500

# --- Function: Extract Text from Image using Google Vision API ---
def extract_text_from_image(image_file):
    # Determine file type
    filename = image_file.filename.lower()
    image_bytes = image_file.read()
    image = None

    if filename.endswith('.pdf'):
        if not convert_from_bytes:
            return 'PDF support not available. Please install pdf2image.'
        try:
            images = convert_from_bytes(image_bytes, first_page=1, last_page=1)
            if not images:
                return 'No pages found in PDF.'
            img = images[0].convert('L')  # Convert to grayscale
            with io.BytesIO() as output:
                img.save(output, format='PNG')
                image = output.getvalue()
        except Exception as e:
            logging.error(f"PDF to image conversion error: {e}")
            return 'Failed to process PDF file.'
    else:
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert('L')  # Convert to grayscale
            with io.BytesIO() as output:
                img.save(output, format='PNG')
                image = output.getvalue()
        except Exception as e:
            logging.error(f"Image open error: {e}")
            return 'Unsupported image format or corrupted file.'

    if not image:
        return 'Failed to process the uploaded file.'

    base64_image = base64.b64encode(image).decode('utf-8')
    payload = {
        "requests": [
            {
                "image": {"content": base64_image},
                "features": [{"type": "TEXT_DETECTION"}]
            }
        ]
    }
    url = f'https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_API_KEY}'

    # Check for missing API key
    # Always fetch the API key from environment variables at runtime
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key == "your_google_api_key_here":
        logging.error("Google Vision API key is missing or not set correctly in the environment.")
        return 'Google Vision API key is missing. Please contact the administrator.'

    # Example known medicine names (replace with your actual list or load from a file)
    known_medicines = [
        "paracetamol", "amoxicillin", "azithromycin", "ibuprofen", "cetirizine", "metformin", "atorvastatin",
        "omeprazole", "pantoprazole", "amoxiclav", "dolo", "crocin", "augmentin", "zincovit", "calpol",
        "aspirin", "losartan", "amlodipine", "clopidogrel", "atorva", "rosuvastatin", "simvastatin",
        "telmisartan", "ramipril", "enalapril", "lisinopril", "metoprolol", "bisoprolol", "propranolol",
        "atenolol", "furosemide", "spironolactone", "hydrochlorothiazide", "glimepiride", "gliclazide",
        "glipizide", "sitagliptin", "vildagliptin", "linagliptin", "dapagliflozin", "empagliflozin",
        "pioglitazone", "insulin", "human mixtard", "novorapid", "lantus", "thyronorm", "eltroxin",
        "levothyroxine", "pantocid", "rabeprazole", "esomeprazole", "lansoprazole", "ranitidine",
        "famotidine", "domperidone", "ondansetron", "granisetron", "cyclopam", "meftal", "mefenamic acid",
        "nimesulide", "diclofenac", "aceclofenac", "etoricoxib", "tramadol", "tapentadol", "morphine",
        "codeine", "chlorpheniramine", "phenylephrine", "montelukast", "levocetirizine", "desloratadine",
        "loratadine", "fexofenadine", "salbutamol", "budesonide", "formoterol", "fluticasone", "beclomethasone",
        "ipratropium", "tiotropium", "aztreonam", "ceftriaxone", "cefixime", "cefpodoxime", "cefuroxime",
        "cephalexin", "clindamycin", "doxycycline", "minocycline", "linezolid", "vancomycin", "meropenem",
        "imipenem", "ertapenem", "piperacillin", "tazobactam", "amphotericin", "fluconazole", "itraconazole",
        "voriconazole", "acyclovir", "valacyclovir", "oseltamivir", "favipiravir", "remdesivir", "hydroxychloroquine",
        "chloroquine", "prednisolone", "methylprednisolone", "dexamethasone", "betamethasone", "hydrocortisone",
        "deflazacort", "azathioprine", "mycophenolate", "cyclosporine", "tacrolimus", "methotrexate",
        "leflunomide", "sulfasalazine", "mesalamine", "adalimumab", "infliximab", "etanercept", "rituximab",
        "adalat", "nifedipine", "verapamil", "diltiazem", "digoxin", "amiodarone", "sotalol", "flecainide",
        "propafenone", "warfarin", "dabigatran", "apixaban", "rivaroxaban", "heparin", "enoxaparin",
        "fondaparinux", "streptokinase", "alteplase", "tenecteplase", "urokinase", "tamsulosin", "alfuzosin",
        "finasteride", "dutasteride", "silodosin", "tolterodine", "oxybutynin", "mirabegron", "solifenacin",
        "fesoterodine", "desmopressin", "terazosin", "prazosin", "doxazosin", "minoxidil", "finpecia",
        "propecia", "dutagen", "dutagen", "sildenafil", "tadalafil", "vardenafil", "avanafil", "dapoxetine",
        "cabergoline", "bromocriptine", "letrozole", "anastrozole", "tamoxifen", "raloxifene", "clomiphene",
        "gonadotropin", "hcg", "fsh", "lh", "testosterone", "estradiol", "progesterone", "medroxyprogesterone",
        "norethisterone", "levonorgestrel", "desogestrel", "drospirenone", "cyproterone", "spironolactone",
        "finasteride", "dutasteride", "minoxidil", "biotin", "zinc", "iron", "folic acid", "vitamin d",
        "vitamin b12", "calcium", "magnesium", "potassium", "sodium", "chloride", "phosphate", "multivitamin"
        # ...add more as needed...
    ]

    # Build a lowercase set for fast lookup
    medicine_set = set(med.lower() for med in known_medicines)

    try:
        response = requests.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps(payload), timeout=20)
        response.raise_for_status()
        # Fix: handle possible JSONDecodeError due to incomplete/invalid JSON
        try:
            response_json = response.json()
        except Exception as e:
            logging.error(f"Google Vision API returned invalid JSON: {e}")
            return 'Error processing image (invalid response from Vision API). Please try again.'

        text_annotations = response_json.get('responses', [])[0].get('textAnnotations', [])
        extracted_text = text_annotations[0].get('description', '') if text_annotations else 'No text found in the image.'

        # --- Improved medicine name extraction and correction ---
        def extract_medicine_candidates(text):
            # Extract words and also lines that look like dosages or instructions
            candidates = set()
            for word in re.findall(r'\b[a-zA-Z][a-zA-Z0-9\-]{3,}\b', text):
                candidates.add(word)
            # Add lines that contain dosage patterns (e.g., "5ml tid a.c.")
            for line in text.split('\n'):
                if re.search(r'\b\d+\s*(mg|ml|gm|mcg)\b', line, re.IGNORECASE):
                    candidates.add(line.strip())
            return list(candidates)

        def best_medicine_match(word, medicine_list, medicine_set):
            # Exact match
            if word.lower() in medicine_set:
                return word.title(), 100
            # Fuzzy match (use process.extractOne)
            match, score = process.extractOne(word.lower(), medicine_list)
            return match.title(), score

        # Extract all candidate words and lines from the text
        candidates = extract_medicine_candidates(extracted_text)
        medicine_matches = {}
        for cand in candidates:
            # Try to match only the medicine name part if the candidate is a line
            med_name = cand
            # If line contains dosage, split and try to match the first word(s)
            if re.search(r'\b\d+\s*(mg|ml|gm|mcg)\b', cand, re.IGNORECASE):
                med_name = cand.split()[0]
            match, score = best_medicine_match(med_name, known_medicines, medicine_set)
            if score > 85:
                medicine_matches[cand] = match
            elif score > 70 and len(med_name) > 5:
                medicine_matches[cand] = match + " (?)"
            # else: skip low-confidence matches

        # Replace candidate words/lines in the text with their best matches
        def replace_candidates(text, matches):
            # Sort by length descending to avoid partial replacements
            for orig in sorted(matches, key=len, reverse=True):
                text = re.sub(rf'\b{re.escape(orig)}\b', matches[orig], text, flags=re.IGNORECASE)
            return text

        extracted_text = replace_candidates(extracted_text, medicine_matches)

        # Filter for medical-related lines and dosage/instruction lines
        medical_keywords = [
            "tablet", "capsule", "mg", "ml", "gm", "mcg", "prescription", "dose", "medication", "medicine", "pharmacy", "drug",
            "antibiotic", "painkiller", "ointment", "syrup", "injection", "vaccine", "diagnosis", "treatment"
        ]
        lines = extracted_text.split('\n')
        filtered_lines = []
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in medical_keywords):
                filtered_lines.append(line)
            elif any(med.lower() in line_lower for med in medicine_matches.values()):
                filtered_lines.append(line)
            # Also keep lines that look like dosage/instructions
            elif re.search(r'\b\d+\s*(mg|ml|gm|mcg)\b', line_lower):
                filtered_lines.append(line)
            elif re.search(r'\bseg:?\s*\d+\s*ml\b', line_lower):  # e.g., "Seg: 5ml"
                filtered_lines.append(line)
        medical_text = "\n".join(filtered_lines)

        # If nothing found, fallback to all matched medicine names
        if not medical_text.strip() and medicine_matches:
            medical_text = "Medicines identified:\n" + ", ".join(sorted(set(medicine_matches.values())))

        return medical_text if medical_text else 'No medical text found in the image.'
    except requests.exceptions.RequestException as e:
        logging.error(f"Google Vision API Error: {e}")
        return 'Error processing image. Please try again.'

# --- Route: MedScript Page ---
@app.route("/medscript", methods=["GET", "POST"])
def medscript():
    if request.method == "POST":
        file = request.files.get("image")
        if file:
            try:
                text = extract_text_from_image(file)
                return render_template("medscript.html", text=text)
            except Exception as e:
                logging.error(f"Image processing error: {str(e)}")
                return render_template("medscript.html", text=f"Error: {str(e)}")
    return render_template("medscript.html")

# --- Function: Format Chatbot Response ---
def format_response(response_text, max_words=120):
    if not response_text or len(response_text.strip()) == 0:
        return "I'm sorry, but I couldn't generate a response."

    response_text = response_text.replace("*", "").strip()
    sections = ["Dosage", "Diet", "Precautions", "Usage"]
    formatted_response = []

    # Extract sections and format them
    for section in sections:
        regex = re.compile(f"{section}:([\\s\\S]*?)(?=\\n[A-Z][a-z]+:|$)", re.IGNORECASE)
        match = regex.search(response_text)
        if match:
            content = match.group(1).strip().replace("\n", "<br>")
            formatted_response.append(f"<div class='response-section'><h4>{section}</h4><p>{content}</p></div>")

    if formatted_response:
        response_text = "".join(formatted_response)
    else:
        # Fallback to plain text if no sections are found
        words = response_text.split()
        if len(words) > max_words:
            truncated_text = " ".join(words[:max_words])
            last_sentence_end = max(truncated_text.rfind("."), truncated_text.rfind("!"), truncated_text.rfind("?"))
            response_text = truncated_text[: last_sentence_end + 1] if last_sentence_end != -1 else truncated_text + "..."
        response_text = f"<p>{response_text}</p>"

    return response_text

# --- Function: Identify Medical Problems ---
def identify_problem(prompt):
    problems = [
        "fever", "cold", "cough", "headache", "stomachache", "flu", "diarrhea", "vomiting", "rash", "sore throat", 
        "fatigue", "dizziness", "chest pain", "shortness of breath", "back pain", "joint pain", "muscle pain",
        "allergies", "infection", "nausea", "hypertension", "diabetes", "asthma", "bronchitis", "pneumonia", 
        "sinusitis", "migraine", "arthritis", "eczema", "psoriasis", "anemia", "depression", "anxiety", 
        "insomnia", "constipation", "ulcer", "acid reflux", "gastroenteritis", "hepatitis", 
        "urinary tract infection", "kidney stones", "gallstones", "menstrual cramps", "pregnancy", "obesity"
    ]
    identified_problems = [problem for problem in problems if problem in prompt.lower()]
    return identified_problems

# --- Function: Medical Chatbot using Gemini API ---
def medical_chatbot(prompt):
    # Split the input into lines, treating each line as a separate medicine
    lines = prompt.strip().split("\n")
    structured_responses = []

    for line in lines:
        # Try to match prescription pattern first
        prescription_pattern = re.compile(
            r'\b(syp|tab|cap|inj|cream|ointment|drop|spray)\s+([A-Za-z0-9\-]+)(?:\s*\(([^)]+)\))?\s*(\d+)\s*ML\s*(Q\d+H|TDS|SOS|TOS)\s*x\s*(\d+d)\b',
            re.IGNORECASE
        )
        matches = prescription_pattern.findall(line)
        if matches:
            for match in matches:
                form, name, concentration, dosage, frequency, duration = match
                ai_prompt = (
                    f"Provide simplified usage instructions, precautions, and related symptoms for the following medicine:\n"
                    f"Medicine: {form} {name} ({concentration or 'N/A'}), Dosage: {dosage} ML, Frequency: {frequency}, Duration: {duration}."
                )
                try:
                    api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
                    params = {"key": gemini_api_key}
                    headers = {"Content-Type": "application/json"}
                    payload = {"contents": [{"parts": [{"text": ai_prompt}]}]}

                    ai_response = requests.post(
                        api_url,
                        params=params,
                        headers=headers,
                        json=payload
                    )
                    ai_response.raise_for_status()
                    ai_data = ai_response.json()
                    if ('candidates' in ai_data and ai_data['candidates'] and
                        'content' in ai_data['candidates'][0] and 
                        'parts' in ai_data['candidates'][0]['content'] and 
                        ai_data['candidates'][0]['content']['parts']):
                        ai_text = ai_data['candidates'][0]['content']['parts'][0]['text'].strip()
                        # Extract only relevant sections
                        if "Precautions:" in ai_text and "Related Symptoms:" in ai_text:
                            usage, rest = ai_text.split("Precautions:", 1)
                            precautions, symptoms = rest.split("Related Symptoms:", 1)
                        elif "Precautions:" in ai_text:
                            usage, precautions = ai_text.split("Precautions:", 1)
                            symptoms = "Related symptoms not specified."
                        else:
                            usage, precautions, symptoms = ai_text, "Precautions not specified.", "Related symptoms not specified."
                        
                        usage = re.sub(r"[^a-zA-Z0-9\s.,:;!?]", "", usage).strip().replace("\n", "<br>")
                        precautions = re.sub(r"[^a-zA-Z0-9\s.,:;!?]", "", precautions).strip().replace("\n", "<br>")
                        symptoms = re.sub(r"[^a-zA-Z0-9\s.,:;!?]", "", symptoms).strip().replace("\n", "<br>")
                        
                        usage = f"<div><strong>Usage Instructions:</strong><br>{usage}</div>"
                        precautions = f"<div><strong>Precautions:</strong><br>{precautions}</div>"
                        symptoms = f"<div><strong>Related Symptoms:</strong><br>{symptoms}</div>"
                    else:
                        usage, precautions, symptoms = (
                            "<div><strong>Usage Instructions:</strong><br>Detailed usage information is not available at the moment. Please consult your doctor or pharmacist for accurate guidance.</div>",
                            "<div><strong>Precautions:</strong><br>Ensure to follow medical advice and read the medicine leaflet for precautions.</div>",
                            "<div><strong>Related Symptoms:</strong><br>Information about related symptoms is not available at the moment.</div>"
                        )
                except Exception as e:
                    logging.error(f"Error generating response for {name}: {e}")
                    usage, precautions, symptoms = (
                        "<div><strong>Usage Instructions:</strong><br>Sorry, we couldn't retrieve detailed usage information for this medicine. Please consult your healthcare provider for accurate instructions.</div>",
                        "<div><strong>Precautions:</strong><br>Consult your doctor or pharmacist for specific precautions related to this medicine.</div>",
                        "<div><strong>Related Symptoms:</strong><br>Unable to retrieve related symptoms at the moment. Please consult your healthcare provider.</div>"
                    )
                structured_responses.append(
                    f"<div><strong>Medicine:</strong> {form} {name} ({concentration})</div>"
                    f"<div><strong>Dosage:</strong> {dosage} ML</div>"
                    f"<div><strong>Frequency:</strong> {frequency}</div>"
                    f"<div><strong>Duration:</strong> {duration}</div>"
                    f"{usage}"
                    f"{precautions}"
                    f"{symptoms}"
                )
        else:
            # If not a prescription, try to explain the medicine name using Gemini API
            medicine_name = line.strip()
            if medicine_name:
                ai_prompt = (
                    f"Explain in simple terms what the medicine '{medicine_name}' is, its common uses, precautions, and related symptoms. "
                    f"Limit the answer to 120 words. If the medicine is not recognized, say so."
                )
                try:
                    api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
                    params = {"key": gemini_api_key}
                    headers = {"Content-Type": "application/json"}
                    payload = {"contents": [{"parts": [{"text": ai_prompt}]}]}

                    ai_response = requests.post(
                        api_url,
                        params=params,
                        headers=headers,
                        json=payload
                    )
                    ai_response.raise_for_status()
                    ai_data = ai_response.json()
                    if ('candidates' in ai_data and ai_data['candidates'] and
                        'content' in ai_data['candidates'][0] and 
                        'parts' in ai_data['candidates'][0]['content'] and 
                        ai_data['candidates'][0]['content']['parts']):
                        ai_text = ai_data['candidates'][0]['content']['parts'][0]['text'].strip()
                        structured_responses.append(
                            f"<div><strong>{medicine_name.title()}:</strong> {ai_text}</div>"
                        )
                    else:
                        structured_responses.append(
                            f"<div><strong>{medicine_name.title()}:</strong> Sorry, I couldn't find information about this medicine.</div>"
                        )
                except Exception as e:
                    logging.error(f"Error generating explanation for {medicine_name}: {e}")
                    structured_responses.append(
                        f"<div><strong>{medicine_name.title()}:</strong> Sorry, I couldn't retrieve information about this medicine at the moment.</div>"
                    )
            else:
                structured_responses.append(f"<div><strong>Unrecognized Input:</strong> {line}</div>")

    return "<br><br>".join(structured_responses)

# --- Route: Chat (Medical Chatbot) ---
@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    if not user_message:
        return jsonify({"response": "Invalid request. No message provided."}), 400

    reply = medical_chatbot(user_message)

    # Save to chat history in Firebase Realtime Database with timestamp
    try:
        chat_ref = db.reference('chat_history')
        chat_entry = {
            'user_message': user_message,
            'bot_response': reply,
            'timestamp': datetime.now().isoformat()
        }
        # --- Prevent duplicate chat history entries ---
        chat_data = chat_ref.order_by_child('timestamp').limit_to_last(1).get()
        is_duplicate = False
        if chat_data:
            for k, v in chat_data.items():
                if v.get('user_message', '') == user_message and v.get('bot_response', '') == reply:
                    is_duplicate = True
                    break
        if not is_duplicate:
            chat_ref.push(chat_entry)
        return jsonify({
            "response": reply,
            "timestamp": chat_entry["timestamp"],
            "user_message": user_message
        })
    except Exception as e:
        logging.error(f"Error saving chat to Firebase Realtime Database: {e}")
        return jsonify({
            "response": reply,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_message": user_message
        })

@app.route('/chatbot')
def chatbot():
    text = request.args.get('text', '')
    chat_history = []
    try:
        # Fetch all chat history from Firebase Realtime Database
        chat_ref = db.reference('chat_history')
        chat_data = chat_ref.get()
        if chat_data:
            chat_list = []
            for k, v in chat_data.items():
                user_message = v.get('user_message', '')
                bot_response = v.get('bot_response', '')
                timestamp = v.get('timestamp', '')
                chat_list.append({
                    'user_message': user_message,
                    'bot_response': bot_response,
                    'timestamp': timestamp
                })
            # Sort by timestamp ascending (oldest first)
            chat_history = sorted(
                chat_list,
                key=lambda x: x['timestamp'] if x['timestamp'] else ''
            )
    except Exception as e:
        logging.error(f"Error fetching chat history from Firebase Realtime Database: {e}")
        chat_history = []

    return render_template('chatbot.html', text=text, chat_history=chat_history)

# --- Route: Index (Home) ---
@app.route("/", methods=["GET"])
def index():
    # If user is logged in, show index, else redirect to login
    if 'user' in session:
        return render_template("index.html", profile=session.get('profile'))
    return redirect(url_for('login'))

# --- Other Routes ---
@app.route('/features')
def features():
    return render_template('features.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to index
    if 'user' in session and session.get('user', {}).get('uid'):
        return redirect(url_for('index'))

    # Handle GET request with email/username parameters
    if request.method == 'GET':
        email = request.args.get('email') or request.args.get('username')
        password = request.args.get('password')
        if not email or not password:
            return render_template('login.html')
    # Handle POST request from form
    elif request.method == 'POST':
        email = request.form.get('username')
        password = request.form.get('password')
    
    try:
        # Firebase Authentication
        firebase_auth_url = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }
        params = {"key": FIREBASE_API_KEY}
        response = requests.post(firebase_auth_url, params=params, json=payload)
        
        if response.status_code == 200:
            user_data = response.json()
            
            # Clear any existing session
            session.clear()
            
            # Create session token
            session_token = create_session_token(user_data)
            if not session_token:
                flash("Error creating session. Please try again.", "danger")
                return redirect(url_for('login'))
            
            # Initialize session data
            session['user'] = {
                'email': user_data['email'],
                'uid': user_data['localId'],
                'token': session_token,
                'firebase_token': user_data['idToken']  # Store original Firebase token
            }
            
            # Get additional user data from Firebase
            try:
                user_record = auth.get_user(user_data['localId'])
                session['profile'] = {
                    'name': user_record.display_name or "",
                    'email': user_record.email or "",
                    'phone': user_record.phone_number or ""
                }
            except Exception as e:
                logging.error(f"Error fetching user profile: {str(e)}")
                session['profile'] = {
                    'name': "",
                    'email': user_data['email'],
                    'phone': ""
                }
            
            # Ensure session is saved
            session.modified = True
            logging.info(f"Login successful for user: {user_data['email']}")
            
            return redirect(url_for('index'))
        
        # If login failed, show error message
        logging.warning(f"Login failed for email: {email}")
        flash("Invalid email or password", "danger")
        return redirect(url_for('login'))

    except Exception as e:
        logging.error(f"Login error: {str(e)}")
        flash("An error occurred during login. Please try again.", "danger")
        return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            # Check if the user already exists
            firebase_auth_url = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
            payload = {
                "email": email,
                "password": password,
                "returnSecureToken": True
            }
            params = {"key": GOOGLE_API_KEY}  # Use from .env
            response = requests.post(firebase_auth_url, params=params, json=payload)

            if response.status_code == 200:
                # User exists, log them in
                user_data = response.json()
                logging.info(f"User logged in successfully: Email={user_data['email']}, UID={user_data['localId']}")
                flash(f"Welcome back, {user_data['email']}!", "success")
                return redirect(url_for('index'))
            else:
                # If user does not exist, create a new account
                raise requests.exceptions.HTTPError

        except requests.exceptions.HTTPError:
            try:
                # Create a new user in Firebase
                user = auth.create_user(
                    email=email,
                    password=password,
                    display_name=username
                )
                logging.info(f"User created in Firebase: UID={user.uid}, Email={user.email}")
                flash(f"Account created successfully for {user.display_name}!", "success")
                return redirect(url_for('index'))
            except firebase_admin.exceptions.FirebaseError as e:
                logging.error(f"Firebase error: {str(e)}")
                flash(f"Error creating account: {str(e)}", "danger")
            except ValueError as e:
                logging.error(f"Value error: {str(e)}")
                flash(f"Invalid input: {str(e)}", "danger")
            except Exception as e:
                logging.error(f"Unexpected error: {str(e)}")
                flash(f"Unexpected error occurred: {str(e)}", "danger")
        return redirect(url_for('signup'))

    return render_template('signup.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        # ...handle password reset logic here...
        flash("If your email is registered, you will receive password reset instructions.", "info")
        return redirect(url_for('login'))
    return render_template('forgot-password.html')

def format_phone_number(phone):
    """Format phone number to E.164 format"""
    if not phone:
        return None
    # Remove all non-digit characters except +
    phone = ''.join(c for c in phone if c.isdigit() or c == '+')
    # Ensure it starts with +
    if not phone.startswith('+'):
        phone = '+' + phone
    return phone

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    try:
        user_uid = g.user.get('uid')
        if not user_uid:
            logging.error("No user_uid found in session")
            return redirect(url_for('login'))

        logging.info(f"Processing profile request for user: {user_uid}")
        
        # Initialize Firestore
        db = firestore.client()
        
        try:
            # Get user record from Firebase Auth
            user_record = auth.get_user(user_uid)
            logging.info(f"Got user record from Firebase Auth: {user_record.uid}")
            profile_data = {
                'name': user_record.display_name or "",
                'email': user_record.email or "",
                'phone': user_record.phone_number or "",
                'photo_url': user_record.photo_url or ""
            }
            
            # Get additional data from Firestore
            user_doc = db.collection('users').document(user_uid).get()
            if user_doc.exists:
                firestore_data = user_doc.to_dict()
                profile_data.update(firestore_data)
            logging.info(f"Initial profile data: {profile_data}")
            
        except Exception as e:
            logging.error(f"Error getting user data: {e}")
            profile_data = session.get('profile', {})

        if request.method == 'POST':
            try:
                data = request.get_json() if request.is_json else request.form.to_dict()
                logging.info(f"Received profile update data: {data}")
                
                # Prepare data for Firestore
                firestore_data = {
                    'name': data.get('name', ''),
                    'phone': data.get('phone', ''),
                    'photo_url': data.get('photo_url', ''),
                    'dob': data.get('dob', ''),
                    'gender': data.get('gender', ''),
                    'language': data.get('language', ''),
                    'timezone': data.get('timezone', ''),
                    'street': data.get('street', ''),
                    'city': data.get('city', ''),
                    'state': data.get('state', ''),
                    'zipcode': data.get('zipcode', ''),
                    'country': data.get('country', ''),
                    'emergency_contact_name': data.get('emergency_contact_name', ''),
                    'emergency_contact_number': data.get('emergency_contact_number', ''),
                    'emergency_contact_relation': data.get('emergency_contact_relation', ''),
                    'height': data.get('height', ''),
                    'weight': data.get('weight', ''),
                    'blood_group': data.get('blood_group', ''),
                    'allergies': data.get('allergies', ''),
                    'medical_conditions': data.get('medical_conditions', ''),
                    'family_medical_history': data.get('family_medical_history', ''),
                    'notification_alerts': data.get('notification_alerts') == 'on',
                    'medication_reminder': data.get('medication_reminder') == 'on',
                    'lab_results': data.get('lab_results') == 'on',
                    'system_updates': data.get('system_updates') == 'on',
                    'app_theme': data.get('app_theme', 'light'),
                    'text_size': data.get('text_size', 'normal'),
                    'show_profile_doctor': data.get('show_profile_doctor') == 'on',
                    'sync_for_research': data.get('sync_for_research') == 'on',
                    'last_updated': datetime.now().isoformat()
                }

                # Handle phone number specially for Firebase Auth
                if data.get('phone'):
                    phone = data['phone'].strip()
                    if phone and not phone.startswith('+'):
                        phone = '+' + phone
                    try:
                        auth.update_user(user_uid, phone_number=phone)
                        logging.info(f"Updated phone in Firebase Auth: {phone}")
                    except Exception as e:
                        logging.error(f"Error updating phone in Firebase Auth: {str(e)}")
                        if 'PHONE_NUMBER_ALREADY_EXISTS' in str(e):
                            return jsonify({
                                'success': False,
                                'error': 'Phone number already in use'
                            }), 400
                        elif 'INVALID_PHONE_NUMBER' in str(e):
                            return jsonify({
                                'success': False,
                                'error': 'Invalid phone number format'
                            }), 400

                # Handle name update in Firebase Auth
                if data.get('name'):
                    try:
                        auth.update_user(user_uid, display_name=data['name'])
                        logging.info(f"Updated name in Firebase Auth: {data['name']}")
                    except Exception as e:
                        logging.error(f"Error updating name in Firebase Auth: {str(e)}")

                # Handle photo URL update in Firebase Auth
                if data.get('photo_url'):
                    try:
                        auth.update_user(user_uid, photo_url=data['photo_url'])
                        logging.info(f"Updated photo URL in Firebase Auth: {data['photo_url']}")
                    except Exception as e:
                        logging.error(f"Error updating photo URL in Firebase Auth: {str(e)}")

                # Remove empty values
                firestore_data = {k: v for k, v in firestore_data.items() if v not in [None, '', []]}

                try:
                    # Store data in Firestore
                    db.collection('users').document(user_uid).set(firestore_data, merge=True)
                    logging.info("Updated profile in Firestore")
                    
                    # Update profile_data with new values
                    profile_data.update(firestore_data)
                    
                    # Update session
                    session['profile'] = profile_data
                    session.modified = True
                    logging.info("Updated session with new profile data")

                    if request.is_json:
                        return jsonify({
                            'success': True,
                            'profile': profile_data
                        })
                    return redirect(url_for('profile'))

                except Exception as e:
                    logging.error(f"Error updating Firestore: {e}")
                    return jsonify({
                        'success': False,
                        'error': 'Failed to save to database'
                    }), 500

            except Exception as e:
                logging.error(f"Error in profile update: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        # For GET requests
        return render_template('profile.html', profile=profile_data)

    except Exception as e:
        logging.error(f"Profile error: {e}")
        return redirect(url_for('login'))

@app.route('/download_pdf')
def download_pdf():
    text = request.args.get('text', '')
    # Clean up the text for better PDF formatting
    # 1. Remove brackets from lists
    import ast
    def clean_list_lines(lines):
        cleaned = []
        for line in lines:
            # Detect lines like: - ['item1', 'item2', ...]
            if line.strip().startswith("- [") and line.strip().endswith("]"):
                try:
                    items = ast.literal_eval(line.strip()[2:].strip())
                    if isinstance(items, list):
                        for item in items:
                            cleaned.append(f"- {item}")
                        continue
                except Exception:
                    pass
            cleaned.append(line)
        return cleaned

    # 2. Remove lines that are just "---" or empty (but keep section breaks)
    lines = text.split('\n')
    lines = [line.rstrip() for line in lines]
    lines = clean_list_lines(lines)
    # Remove lines that are only whitespace or only contain "---" (but keep one blank line between sections)
    final_lines = []
    prev_blank = False
    for line in lines:
        if line.strip() == "---":
            final_lines.append("-" * 40)
            prev_blank = False
        elif line.strip() == "":
            if not prev_blank:
                final_lines.append("")
                prev_blank = True
        else:
            final_lines.append(line)
            prev_blank = False

    # 3. Remove stray '■' or similar unicode chars if present
    final_lines = [line.replace("■", "") for line in final_lines]

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setFont("Helvetica", 12)
    y_position = 800
    for line in final_lines:
        pdf.drawString(50, y_position, line)
        y_position -= 20
        if y_position < 50:
            pdf.showPage()
            pdf.setFont("Helvetica", 12)
            y_position = 800
    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="extracted_text.pdf", mimetype="application/pdf")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/send_message', methods=['POST'])
def send_message():
    name = request.form.get('name')
    message = request.form.get('message')
    sender_email = "hiteshgottapu@gmail.com"
    receiver_email = "gottapuhitesh@gmail.com"
    password = "your_email_password"
    subject = f"New Message from {name}"
    body = f"Name: {name}\nMessage: {message}\n"
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        return jsonify({"success": True, "message": "Message sent successfully!"})
    except Exception as e:
        logging.error(f"Email sending error: {e}")
        return jsonify({"success": False, "message": "Failed to send message."})

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/developers')
def developers():
    # Example developer data
    developers = [
        {"name": "Gottapu Hitesh", "role": "Lead Developer", "email": "hiteshgottapu309@gmail.com"},
        {"name": "Jane Doe", "role": "Backend Developer", "email": "jane.doe@example.com"},
        {"name": "John Smith", "role": "Frontend Developer", "email": "john.smith@example.com"}
    ]
    return render_template('developers.html', developers=developers)

@app.route("/doctor_consultation", methods=["GET", "POST"])
def doctor_consultation():
    if request.method == "POST":
        name = request.form.get("name")
        age = request.form.get("age")
        email = request.form.get("email")
        symptoms = request.form.get("symptoms").lower()

        # Example doctor database
        doctors = [
            {"name": "Dr. John Doe", "hospital": "City Hospital", "hospital_email": "cityhospital@example.com", "specialization": "General Physician", "keywords": ["fever", "cold", "cough"], "rating": 4.5},
            {"name": "Dr. Alice Johnson", "hospital": "HealthCare Clinic", "hospital_email": "healthcareclinic@example.com", "specialization": "General Physician", "keywords": ["fever", "cold", "cough", "headache", "fatigue", "dizziness"], "rating": 4.7},
            {"name": "Dr. Jane Smith", "hospital": "HealthCare Clinic", "hospital_email": "healthcareclinic@example.com", "specialization": "Pediatrician", "keywords": ["child", "pediatric", "flu", "diarrhea", "vomiting", "rash"], "rating": 4.8},
            {"name": "Dr. Emily Davis", "hospital": "Wellness Center", "hospital_email": "wellnesscenter@example.com", "specialization": "Dermatologist", "keywords": ["rash", "skin", "itching", "acne", "eczema", "psoriasis"], "rating": 4.6},
            {"name": "Dr. Michael Brown", "hospital": "Metro Hospital", "hospital_email": "metrohospital@example.com", "specialization": "Cardiologist", "keywords": ["chest pain", "heart", "shortness of breath", "hypertension", "palpitations"], "rating": 4.9},
            {"name": "Dr. Sarah Wilson", "hospital": "Care Hospital", "hospital_email": "carehospital@example.com", "specialization": "Gastroenterologist", "keywords": ["stomach pain", "indigestion", "ulcer", "acid reflux", "constipation", "diarrhea"], "rating": 4.7},
            {"name": "Dr. Robert Taylor", "hospital": "Prime Clinic", "hospital_email": "primeclinic@example.com", "specialization": "Neurologist", "keywords": ["migraine", "headache", "dizziness", "seizures", "numbness", "weakness", "neck pain"], "rating": 4.8},
            {"name": "Dr. Laura Martinez", "hospital": "Sunrise Hospital", "hospital_email": "sunrisehospital@example.com", "specialization": "Endocrinologist", "keywords": ["diabetes", "thyroid", "hormonal imbalance", "weight gain", "weight loss"], "rating": 4.6},
            {"name": "Dr. Angela White", "hospital": "Healing Hands Clinic", "hospital_email": "healinghandsclinic@example.com", "specialization": "Psychiatrist", "keywords": ["depression", "anxiety", "insomnia", "mood swings", "stress"], "rating": 4.9},
            {"name": "Dr. Kevin Harris", "hospital": "LifeCare Hospital", "hospital_email": "lifecarehospital@example.com", "specialization": "Pulmonologist", "keywords": ["cough", "breathlessness", "asthma", "bronchitis", "pneumonia"], "rating": 4.7},
            {"name": "Dr. Sophia Green", "hospital": "Harmony Clinic", "hospital_email": "harmonyclinic@example.com", "specialization": "Ophthalmologist", "keywords": ["blurred vision", "eye pain", "redness of eyes", "dry eyes", "vision loss"], "rating": 4.5},
            {"name": "Dr. William Carter", "hospital": "Hope Hospital", "hospital_email": "hopehospital@example.com", "specialization": "Oncologist", "keywords": ["cancer", "tumor", "chemotherapy", "radiation", "lump"], "rating": 4.8},
            {"name": "Dr. Olivia Adams", "hospital": "Bright Smile Dental", "hospital_email": "brightsmiledental@example.com", "specialization": "Dentist", "keywords": ["toothache", "cavity", "gum bleeding", "oral hygiene", "braces"], "rating": 4.6},
            {"name": "Dr. Ethan Walker", "hospital": "Sunrise Hospital", "hospital_email": "sunrisehospital@example.com", "specialization": "Urologist", "keywords": ["urinary tract infection", "kidney stones", "bladder discomfort", "prostate"], "rating": 4.7},
            {"name": "Dr. Isabella Scott", "hospital": "CarePlus Clinic", "hospital_email": "careplusclinic@example.com", "specialization": "Rheumatologist", "keywords": ["arthritis", "joint swelling", "autoimmune diseases", "stiffness"], "rating": 4.8},
            {"name": "Dr. Benjamin Moore", "hospital": "Wellness Center", "hospital_email": "wellnesscenter@example.com", "specialization": "Hematologist", "keywords": ["anemia", "blood disorders", "clotting issues", "leukemia"], "rating": 4.6},
            {"name": "Dr. Charlotte Evans", "hospital": "Prime Clinic", "hospital_email": "primeclinic@example.com", "specialization": "Allergist", "keywords": ["allergies", "asthma", "skin rash", "hay fever", "food allergies"], "rating": 4.7},
            {"name": "Dr. Daniel Turner", "hospital": "LifeCare Hospital", "hospital_email": "lifecarehospital@example.com", "specialization": "Infectious Disease Specialist", "keywords": ["infection", "fever", "HIV", "tuberculosis", "hepatitis"], "rating": 4.8},
            {"name": "Dr. Mia Brooks", "hospital": "Green Valley Clinic", "hospital_email": "greenvalleyclinic@example.com", "specialization": "Nephrologist", "keywords": ["kidney failure", "dialysis", "proteinuria", "swelling"], "rating": 4.7},
            {"name": "Dr. Lucas Bennett", "hospital": "City Hospital", "hospital_email": "cityhospital@example.com", "specialization": "Surgeon", "keywords": ["surgery", "appendicitis", "hernia", "trauma", "wound care"], "rating": 4.6},
            {"name": "Dr. Grace Parker", "hospital": "Metro Hospital", "hospital_email": "metrohospital@example.com", "specialization": "Cardiologist", "keywords": ["chest pain", "heart", "shortness of breath", "hypertension", "palpitations"], "rating": 4.9},
            {"name": "Dr. Henry Collins", "hospital": "Care Hospital", "hospital_email": "carehospital@example.com", "specialization": "Gastroenterologist", "keywords": ["stomach pain", "indigestion", "ulcer", "acid reflux", "constipation", "diarrhea"], "rating": 4.7},
            {"name": "Dr. Natalie Cooper", "hospital": "Harmony Clinic", "hospital_email": "harmonyclinic@example.com", "specialization": "Dermatologist", "keywords": ["rash", "skin", "itching", "acne", "eczema", "psoriasis"], "rating": 4.6},
            {"name": "Dr. Ryan Foster", "hospital": "LifeCare Hospital", "hospital_email": "lifecarehospital@example.com", "specialization": "Pulmonologist", "keywords": ["cough", "breathlessness", "asthma", "bronchitis", "pneumonia"], "rating": 4.7}
        ]

        # Filter doctors based on symptoms
        suggested_doctors = [
            doctor for doctor in doctors if any(keyword in symptoms for keyword in doctor["keywords"])
        ]

        return render_template("doctor_consultation.html", doctors=suggested_doctors, name=name, age=age, email=email, symptoms=symptoms)

    # Pre-fill form with data from GET request
    name = request.args.get("name", "")
    age = request.args.get("age", "")
    email = request.args.get("email", "")
    symptoms = request.args.get("symptoms", "")

    return render_template("doctor_consultation.html", name=name, age=name, email=email, symptoms=symptoms)

@app.route("/schedule_appointment", methods=["POST"])
def schedule_appointment():
    patient_name = request.form.get("patient_name")
    doctor_name = request.form.get("doctor_name")
    doctor_email = request.form.get("doctor_email")
    hospital_email = request.form.get("hospital_email")  # Added hospital email
    appointment_date = request.form.get("appointment_date")
    appointment_time = request.form.get("appointment_time")
    additional_details = request.form.get("additional_details")

    # Email content
    subject = f"Appointment Request with {doctor_name}"
    patient_email = "user@example.com"  # Replace with the user's email from the session or form
    email_body = f"""
    Dear {doctor_name},

    You have a new appointment request from {patient_name}.

    Appointment Details:
    - Date: {appointment_date}
    - Time: {appointment_time}
    - Additional Details: {additional_details}

    Please confirm the appointment at your earliest convenience.

    Regards,
    MedScript
    """

    # Send email to doctor
    send_email(doctor_email, subject, email_body)

    # Send email to hospital
    send_email(hospital_email, subject, email_body)

    # Send confirmation email to patient
    confirmation_subject = "Appointment Request Confirmation"
    confirmation_body = f"""
    Dear {patient_name},

    Your appointment request with Dr. {doctor_name} has been sent successfully.

    Appointment Details:
    - Date: {appointment_date}
    - Time: {appointment_time}
    - Additional Details: {additional_details}

    You will receive a confirmation from the doctor soon.

    Regards,
    MedScript
    """
    send_email(patient_email, confirmation_subject, confirmation_body)

    flash("Appointment request sent successfully!", "success")
    return redirect(url_for("doctor_consultation"))

def send_email(to_email, subject, body):
    sender_email = os.getenv("SENDER_EMAIL")  # Use from .env
    sender_password = os.getenv("SENDER_EMAIL_PASSWORD")  # Use from .env

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
    except Exception as e:
        print(f"Error sending email: {e}")

# --- Twilio Integration ---
# --- Route: Emergency ---
@app.route("/emergency")
def emergency():
    return render_template("emergency.html")

# --- Function: Send Emergency Email to Hospital (fixed: always send to hiteshsimhagottpu@gmail.com from user email) ---
def send_emergency_email_to_hospital(user_email, subject, message_body):
    import ssl
    port = 465
    smtp_server = "smtp.gmail.com"
    receiver_email = "hiteshsimhagottapu@gmail.com"
    context = ssl.create_default_context()
    # Improved HTML and plain text email format
    html_body = f"""
    <html>
    <body>
        <h2 style="color:#d32f2f;">🚨 Emergency Alert Notification</h2>
        <p>
            <b>Alert triggered by:</b> {user_email}<br>
            <b>Time:</b> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
        </p>
        <p>
            <b>Symptoms:</b><br>
            <span style="color:#333;">{message_body.get('symptoms', '')}</span>
        </p>
        <p>
            <b>Location:</b><br>
            <a href="{message_body.get('location_url', '')}">{message_body.get('location_url', '')}</a>
        </p>
        <p>
            <b>Additional Info:</b><br>
            {message_body.get('additional', '')}
        </p>
        <hr>
        <p style="color:#888;">This is an automated emergency notification from MedScript.</p>
    </body>
    </html>
    """
    plain_body = (
        f"EMERGENCY ALERT\n"
        f"Alert triggered by: {user_email}\n"
        f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Symptoms: {message_body.get('symptoms', '')}\n"
        f"Location: {message_body.get('location_url', '')}\n"
        f"Additional Info: {message_body.get('additional', '')}\n"
        f"\nThis is an automated emergency notification from MedScript."
    )
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user_email
    msg["To"] = receiver_email
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    user_password = os.getenv("USER_EMAIL_PASSWORD")
    if not user_password:
        logging.error("USER_EMAIL_PASSWORD environment variable not set.")
        return False
    try:
        with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
            server.login(user_email, user_password)
            server.sendmail(user_email, receiver_email, msg.as_string())
        return True
    except Exception as e:
        logging.error(f"Failed to send emergency email to hospital: {e}")
        return False

# --- Route: Handle Firebase Authentication Action Links ---
@app.route('/auth/action', methods=['GET'])
def handle_auth_action():
    mode = request.args.get('mode')
    oob_code = request.args.get('oobCode')

    if not mode or not oob_code:
        flash("Invalid or missing parameters in the action link.", "danger")
        return redirect(url_for('index'))

    try:
        if mode == 'verifyEmail':
            # Handle email verification
            auth.verify_id_token(oob_code)
            flash("Email verified successfully!", "success")
        elif mode == 'resetPassword':
            # Redirect to a password reset page
            return redirect(url_for('reset_password', oobCode=oob_code))
        else:
            flash("Unsupported action mode.", "danger")
    except Exception as e:
        logging.error(f"Error handling auth action: {str(e)}")
        flash("An error occurred while processing the action link.", "danger")

    return redirect(url_for('index'))

# --- Route to serve static files like firebase.js ---
@app.route('/firebase.js')
def serve_firebase_js():
    return send_from_directory('static', 'firebase.js')

# --- Error Handler for 404 ---
@app.errorhandler(404)
def page_not_found(e):
    return "Page not found", 404

# ================== SECOND PART: AI CONSULTANT ==================
# --- Infermedica API Credentials (optional, for /api/symptom-check) ---
INFERMEDICA_APP_ID = os.getenv("INFERMEDICA_APP_ID", "")
INFERMEDICA_APP_KEY = os.getenv("INFERMEDICA_APP_KEY", "")

# --- Load Datasets & Model ---
sym_des = pd.read_csv("dataset/symtoms_df.csv")
precautions = pd.read_csv("dataset/precautions_df.csv")
workout = pd.read_csv("dataset/workout_df.csv")
description = pd.read_csv("dataset/description.csv")
medications = pd.read_csv("dataset/medications.csv")
diets = pd.read_csv("dataset/diets.csv")
svc = pickle.load(open('model/svc.pkl','rb'))

# --- Helper Function to Retrieve Disease Details ---
def helper(dis):
    desc = description[description['Disease'] == dis]['Description']
    desc = " ".join([w for w in desc])
    pre = precautions[precautions['Disease'] == dis][['Precaution_1', 'Precaution_2', 'Precaution_3', 'Precaution_4']]
    pre = [col for col in pre.values]
    med = medications[medications['Disease'] == dis]['Medication']
    med = [m for m in med.values]
    die = diets[diets['Disease'] == dis]['Diet']
    die = [d for d in die.values]
    wrkout = workout[workout['disease'] == dis]['workout']
    return desc, pre, med, die, wrkout

# --- Dictionaries for Symptom Mapping & Disease List ---
symptoms_dict = {
    'itching': 0, 'skin_rash': 1, 'nodal_skin_eruptions': 2, 'continuous_sneezing': 3,
    'shivering': 4, 'chills': 5, 'joint_pain': 6, 'stomach_pain': 7, 'acidity': 8,
    'ulcers_on_tongue': 9, 'muscle_wasting': 10, 'vomiting': 11, 'burning_micturition': 12,
    'spotting_urination': 13, 'fatigue': 14, 'weight_gain': 15, 'anxiety': 16,
    'cold_hands_and_feets': 17, 'mood_swings': 18, 'weight_loss': 19, 'restlessness': 20,
    'lethargy': 21, 'patches_in_throat': 22, 'irregular_sugar_level': 23, 'cough': 24,
    'high_fever': 25, 'sunken_eyes': 26, 'breathlessness': 27, 'sweating': 28,
    'dehydration': 29, 'indigestion': 30, 'headache': 31, 'yellowish_skin': 32,
    'dark_urine': 33, 'nausea': 34, 'loss_of_appetite': 35, 'pain_behind_the_eyes': 36,
    'back_pain': 37, 'constipation': 38, 'abdominal_pain': 39, 'diarrhoea': 40,
    'mild_fever': 41, 'yellow_urine': 42, 'yellowing_of_eyes': 43, 'acute_liver_failure': 44,
    'fluid_overload': 45, 'swelling_of_stomach': 46, 'swelled_lymph_nodes': 47, 'malaise': 48,
    'blurred_and_distorted_vision': 49, 'phlegm': 50, 'throat_irritation': 51, 'redness_of_eyes': 52,
    'sinus_pressure': 53, 'runny_nose': 54, 'congestion': 55, 'chest_pain': 56,
    'weakness_in_limbs': 57, 'fast_heart_rate': 58, 'pain_during_bowel_movements': 59,
    'pain_in_anal_region': 60, 'bloody_stool': 61, 'irritation_in_anus': 62, 'neck_pain': 63,
    'dizziness': 64, 'cramps': 65, 'bruising': 66, 'obesity': 67, 'swollen_legs': 68,
    'swollen_blood_vessels': 69, 'puffy_face_and_eyes': 70, 'enlarged_thyroid': 71,
    'brittle_nails': 72, 'swollen_extremeties': 73, 'excessive_hunger': 74, 'extra_marital_contacts': 75,
    'drying_and_tingling_lips': 76, 'slurred_speech': 77, 'knee_pain': 78, 'hip_joint_pain': 79,
    'muscle_weakness': 80, 'stiff_neck': 81, 'swelling_joints': 82, 'movement_stiffness': 83,
    'spinning_movements': 84, 'loss_of_balance': 85, 'unsteadiness': 86, 'weakness_of_one_body_side': 87,
    'loss_of_smell': 88, 'bladder_discomfort': 89, 'foul_smell_of urine': 90, 'continuous_feel_of_urine': 91,
    'passage_of_gases': 92, 'internal_itching': 93, 'toxic_look_(typhos)': 94, 'depression': 95,
    'irritability': 96, 'muscle_pain': 97, 'altered_sensorium': 98, 'red_spots_over_body': 99,
    'belly_pain': 100, 'abnormal_menstruation': 101, 'dischromic _patches': 102, 'watering_from_eyes': 103,
    'increased_appetite': 104, 'polyuria': 105, 'family_history': 106, 'mucoid_sputum': 107,
    'rusty_sputum': 108, 'lack_of_concentration': 109, 'visual_disturbances': 110,
    'receiving_blood_transfusion': 111, 'receiving_unsterile_injections': 112, 'coma': 113,
    'stomach_bleeding': 114, 'distention_of_abdomen': 115, 'history_of_alcohol_consumption': 116,
    'fluid_overload.1': 117, 'blood_in_sputum': 118, 'prominent_veins_on_calf': 119,
    'palpitations': 120, 'painful_walking': 121, 'pus_filled_pimples': 122, 'blackheads': 123,
    'scurring': 124, 'skin_peeling': 125, 'silver_like_dusting': 126, 'small_dents_in_nails': 127,
    'inflammatory_nails': 128, 'blister': 129, 'red_sore_around_nose': 130, 'yellow_crust_ooze': 131
}


diseases_list = {
    15: 'Fungal infection', 4: 'Allergy', 16: 'GERD', 9: 'Chronic cholestasis',
    14: 'Drug Reaction', 33: 'Peptic ulcer diseae', 1: 'AIDS', 12: 'Diabetes',
    17: 'Gastroenteritis', 6: 'Bronchial Asthma', 23: 'Hypertension', 30: 'Migraine',
    7: 'Cervical spondylosis', 32: 'Paralysis (brain hemorrhage)', 28: 'Jaundice',
    29: 'Malaria', 8: 'Chicken pox', 11: 'Dengue', 37: 'Typhoid', 40: 'hepatitis A',
    19: 'Hepatitis B', 20: 'Hepatitis C', 21: 'Hepatitis D', 22: 'Hepatitis E',
    3: 'Alcoholic hepatitis', 36: 'Tuberculosis', 10: 'Common Cold', 34: 'Pneumonia',
    13: 'Dimorphic hemmorhoids(piles)', 18: 'Heart attack', 39: 'Varicose veins',
    26: 'Hypothyroidism', 24: 'Hyperthyroidism', 25: 'Hypoglycemia', 31: 'Osteoarthristis',
    5: 'Arthritis', 0: '(vertigo) Paroymsal Positional Vertigo', 2: 'Acne',
    38: 'Urinary tract infection', 35: 'Psoriasis', 27: 'Impetigo'
}

# --- Function: Correct Spelling using TextBlob ---
def correct_spelling(symptom):
    blob = TextBlob(symptom)
    return str(blob.correct())

# --- Symptom Mapping for Synonyms ---
symptom_mapping = defaultdict(lambda: "unknown", {
    "itching": ["itching"],
    "skin_rash": ["skin rash", "rash", "dermatitis", "rashes"],
    "nodal_skin_eruptions": ["nodal skin eruptions", "skin eruptions", "bumps"],
    "continuous_sneezing": ["continuous sneezing", "sneezing"],
    "shivering": ["shivering", "trembling"],
    "chills": ["chills", "cold sensation", "cold"],
    "joint_pain": ["joint pain", "arthralgia", "aching joints"],
    "stomach_pain": ["stomach pain", "abdominal pain", "belly ache"],
    "acidity": ["acidity", "heartburn", "acid reflux"],
    "ulcers_on_tongue": ["ulcers on tongue", "tongue ulcers", "mouth sores"],
    "muscle_wasting": ["muscle wasting", "muscle loss"],
    "vomiting": ["vomiting", "emesis", "throwing up"],
    "burning_micturition": ["burning micturition", "burning urination", "painful urination"],
    "spotting_urination": ["spotting urination", "blood in urine", "hematuria"],
    "fatigue": ["fatigue", "tiredness", "exhaustion"],
    "weight_gain": ["weight gain", "increased weight"],
    "anxiety": ["anxiety", "nervousness", "worry", "sleeping"],
    "cold_hands_and_feets": ["cold hands and feet", "cold extremities"],
    "mood_swings": ["mood swings", "emotional changes"],
    "weight_loss": ["weight loss", "decreased weight"],
    "restlessness": ["restlessness", "agitation"],
    "lethargy": ["lethargy", "sluggishness"],
    "patches_in_throat": ["patches in throat", "throat patches", "throat lesions"],
    "irregular_sugar_level": ["irregular sugar level", "unstable glucose", "blood sugar fluctuations"],
    "cough": ["cough", "coughing"],
    "high_fever": ["high fever", "elevated temperature"],
    "sunken_eyes": ["sunken eyes", "hollow eyes"],
    "breathlessness": ["breathlessness", "shortness of breath", "dyspnea"],
    "sweating": ["sweating", "perspiration"],
    "dehydration": ["dehydration", "fluid loss"],
    "indigestion": ["indigestion", "upset stomach"],
    "headache": ["headache", "head pain", "migraine"],
    "yellowish_skin": ["yellowish skin", "jaundice"],
    "dark_urine": ["dark urine"],
    "swelled_lymph_nodes": ["swelled lymph nodes", "enlarged lymph nodes"],
    "malaise": ["malaise", "general discomfort"],
    "blurred_and_distorted_vision": ["blurred and distorted vision", "blurry vision"],
    "phlegm": ["phlegm", "mucus"],
    "throat_irritation": ["throat irritation", "sore throat"],
    "redness_of_eyes": ["redness of eyes", "bloodshot eyes"],
    "sinus_pressure": ["sinus pressure", "sinus congestion"],
    "runny_nose": ["runny nose", "rhinorrhea"],
    "congestion": ["congestion", "nasal blockage"],
    "chest_pain": ["chest pain", "angina"],
    "weakness_in_limbs": ["weakness in limbs", "limb weakness"],
    "fast_heart_rate": ["fast heart rate", "tachycardia"],
    "pain_during_bowel_movements": ["pain during bowel movements", "painful defecation"],
    "pain_in_anal_region": ["pain in anal region", "anal pain"],
    "bloody_stool": ["bloody stool", "rectal bleeding"],
    "irritation_in_anus": ["irritation in anus", "anal itching"],
    "neck_pain": ["neck pain", "cervical pain"],
    "dizziness": ["dizziness", "lightheadedness"],
    "cramps": ["cramps", "muscle cramps", "spasms"],
    "bruising": ["bruising", "hematoma"],
    "obesity": ["obesity", "overweight"],
    "swollen_legs": ["swollen legs", "leg edema"],
    "swollen_blood_vessels": ["swollen blood vessels", "varicose veins"],
    "puffy_face_and_eyes": ["puffy face and eyes", "facial swelling"],
    "enlarged_thyroid": ["enlarged thyroid", "goiter"],
    "brittle_nails": ["brittle nails", "weak nails"],
    "swollen_extremeties": ["swollen extremities", "swollen arms and legs"],
    "excessive_hunger": ["excessive hunger", "polyphagia"],
    "extra_marital_contacts": ["extra marital contacts", "multiple sexual partners"],
    "drying_and_tingling_lips": ["drying and tingling lips", "lip dryness"],
    "slurred_speech": ["slurred speech", "dysarthria"],
    "knee_pain": ["knee pain", "pain in the knees"],
    "hip_joint_pain": ["hip joint pain", "hip pain"],
    "muscle_weakness": ["muscle weakness", "muscle fatigue"],
    "stiff_neck": ["stiff neck", "neck stiffness"],
    "swelling_joints": ["swelling joints", "joint swelling"],
    "movement_stiffness": ["movement stiffness", "rigidity"],
    "spinning_movements": ["spinning movements", "vertigo"],
    "loss_of_balance": ["loss of balance", "balance problems"],
    "unsteadiness": ["unsteadiness", "lack of balance"],
    "weakness_of_one_body_side": ["weakness of one body side", "hemiparesis"],
    "loss_of_smell": ["loss of smell", "anosmia"],
    "bladder_discomfort": ["bladder discomfort", "bladder pain"],
    "foul_smell_of urine": ["foul smell of urine", "smelly urine"],
    "continuous_feel_of_urine": ["continuous feel of urine", "urgency to urinate"],
    "passage_of_gases": ["passage of gases", "flatulence"],
    "internal_itching": ["internal itching"],
    "toxic_look_(typhos)": ["toxic look (typhos)", "septic appearance"],
    "depression": ["depression", "low mood"],
    "irritability": ["irritability", "easily annoyed"],
    "muscle_pain": ["muscle pain", "myalgia"],
    "altered_sensorium": ["altered sensorium", "confusion"],
    "red_spots_over_body": ["red spots over body", "rash with red spots"],
    "belly_pain": ["belly pain", "abdominal pain"],
    "abnormal_menstruation": ["abnormal menstruation", "irregular periods"],
    "dischromic_patches": ["dischromic patches", "skin discoloration"],
    "watering_from_eyes": ["watering from eyes", "teary eyes"],
    "increased_appetite": ["increased appetite", "hyperphagia"],
    "polyuria": ["polyuria", "excessive urination"],
    "family_history": ["family history", "genetic predisposition"],
    "mucoid_sputum": ["mucoid sputum", "mucus in sputum"],
    "rusty_sputum": ["rusty sputum", "blood-tinged sputum"],
    "lack_of_concentration": ["lack of concentration", "difficulty focusing"],
    "visual_disturbances": ["visual disturbances", "vision problems"],
    "receiving_blood_transfusion": ["receiving blood transfusion"],
    "receiving_unsterile_injections": ["receiving unsterile injections"]
})

# --- Function: Get Top N Predicted Diseases based on Symptoms ---
def get_top_predicted_values(patient_symptoms, top_n=3):
    input_vector = np.zeros(len(symptoms_dict))
    for item in patient_symptoms:
        corrected_item = item
        index = symptoms_dict.get(corrected_item, -1)
        if index != -1:
            input_vector[index] = 1
        else:
            found = False
            for key, synonyms in symptom_mapping.items():
                if item in synonyms:
                    index = symptoms_dict.get(key, -1)
                    if index != -1:
                        input_vector[index] = 1
                        found = True
                        break
            if not found:
                corrected_item = correct_spelling(item)
                index = symptoms_dict.get(corrected_item, -1)
                if index != -1:
                    input_vector[index] = 1
                else:
                    for key, synonyms in symptom_mapping.items():
                        if corrected_item in synonyms:
                            index = symptoms_dict.get(key, -1)
                            if index != -1:
                                input_vector[index] = 1
                                break
    # Get probabilities for all classes
    if hasattr(svc, "predict_proba"):
        probs = svc.predict_proba([input_vector])[0]
        top_indices = np.argsort(probs)[::-1][:top_n]
    else:
        # fallback: use decision_function or just predict one
        pred = svc.predict([input_vector])[0]
        top_indices = [pred]
    top_diseases = []
    for idx in top_indices:
        disease = diseases_list.get(idx, "Unknown Disease")
        top_diseases.append((idx, disease))
    return top_diseases

# --- Route: AI Consultant Page (GET) ---
@app.route("/ai_consultant")
def ai_consultant():
    return render_template("ai_consultant.html")

# --- Route: Disease Prediction from Symptoms (POST) ---
@app.route("/predict", methods=['POST'])
def predict():
    name = request.form.get('name')
    age = request.form.get('age')
    location = request.form.get('location')
    symptoms = request.form.get('symptoms')
    
    if symptoms == "Symptoms":
        message = "Please either write symptoms or check for misspellings."
        return render_template('ai_consultant.html', message=message)
    if not symptoms:
        message = "Please enter symptoms."
        return render_template('ai_consultant.html', message=message)
    else:
        user_symptoms = [s.strip() for s in symptoms.split(',')]
        user_symptoms = [symptom.strip("[]' ") for symptom in user_symptoms]
        disease_set = set()
        predictions = []
        if len([s for s in user_symptoms if s]) == 1:
            # Only one symptom: predict only the top disease for that symptom
            symptom = user_symptoms[0]
            top_diseases = get_top_predicted_values([symptom], top_n=1)
            for idx, predicted_disease in top_diseases:
                if predicted_disease not in disease_set:
                    disease_set.add(predicted_disease)
                    dis_des, pre, med, rec_diet, wrkout = helper(predicted_disease)
                    my_precautions = pre[0] if pre and len(pre) > 0 else []
                    predictions.append({
                        'predicted_disease': predicted_disease,
                        'dis_des': dis_des,
                        'my_precautions': my_precautions,
                        'medications': med,
                        'my_diet': rec_diet,
                        'workout': wrkout
                    })
        else:
            # Multiple symptoms: show top 3 predicted diseases for all symptoms together
            top_diseases_all = get_top_predicted_values(user_symptoms, top_n=3)
            for idx, predicted_disease in top_diseases_all:
                if predicted_disease not in disease_set:
                    disease_set.add(predicted_disease)
                    dis_des, pre, med, rec_diet, wrkout = helper(predicted_disease)
                    my_precautions = pre[0] if pre and len(pre) > 0 else []
                    predictions.append({
                        'predicted_disease': predicted_disease,
                        'dis_des': dis_des,
                        'my_precautions': my_precautions,
                        'medications': med,
                        'my_diet': rec_diet,
                        'workout': wrkout
                    })
        return render_template('ai_consultant.html',
                               name=name,
                               age=age,
                               location=location,
                               symptoms=symptoms,
                               predictions=predictions)

# ================== SYMPTOM CHECKER & EMERGENCY ALERT API ==================
# 1. Symptom Input & Diagnosis (Core)
#    - POST /api/symptom-check
#      Input: JSON {symptoms: "...", age: int, sex: "male"/"female"}
#      Output: { conditions: [ { name, confidence }, ... ] } (Infermedica) or { predictions: [...] } (local)

def infermedica_symptom_check(symptoms, age, sex):
    """
    Calls the Infermedica API to check symptoms and return possible conditions.
    Tries to map user symptoms to Infermedica IDs using synonyms and fuzzy matching for better accuracy.
    """
    url = "https://api.infermedica.com/v3/diagnosis"
    headers = {
        "App-Id": INFERMEDICA_APP_ID,
        "App-Key": INFERMEDICA_APP_KEY,
        "Content-Type": "application/json"
    }
    # In production, you should map symptoms to Infermedica IDs.
    # Here, we try to improve mapping using synonyms and fuzzy matching.
    evidence = []
    # Optionally, cache Infermedica symptoms list for better mapping
    try:
        symptoms_list_url = "https://api.infermedica.com/v3/symptoms"
        symptoms_response = requests.get(symptoms_list_url, headers=headers, timeout=10)
        symptoms_response.raise_for_status()
        infermedica_symptoms = symptoms_response.json()
        infermedica_symptom_names = {s['name'].lower(): s['id'] for s in infermedica_symptoms}
    except Exception as e:
        logging.warning(f"Could not fetch Infermedica symptoms list: {e}")
        infermedica_symptom_names = {}

    from fuzzywuzzy import process as fuzzy_process

    for symptom in [s.strip() for s in symptoms.split(',') if s.strip()]:
        symptom_lower = symptom.lower()
        # Try direct match
        if symptom_lower in infermedica_symptom_names:
            evidence.append({"id": infermedica_symptom_names[symptom_lower], "choice_id": "present"})
        else:
            # Fuzzy match to Infermedica symptom names
            if infermedica_symptom_names:
                match, score = fuzzy_process.extractOne(symptom_lower, infermedica_symptom_names.keys())
                if score > 80:
                    evidence.append({"id": infermedica_symptom_names[match], "choice_id": "present"})
                else:
                    # fallback: use raw symptom as id (may fail)
                    evidence.append({"id": symptom_lower.replace(" ", "_"), "choice_id": "present"})
            else:
                evidence.append({"id": symptom_lower.replace(" ", "_"), "choice_id": "present"})
    payload = {
        "sex": sex,
        "age": age,
        "evidence": evidence
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Infermedica API error: {e}")
        return {"error": str(e)}

@app.route("/api/symptom-check", methods=["POST"])
def api_symptom_check():
    data = request.get_json(force=True)
    symptoms = data.get("symptoms", "")
    age = data.get("age", 30)
    sex = data.get("sex", "male")
    # Prefer Infermedica if credentials are set
    if INFERMEDICA_APP_ID and INFERMEDICA_APP_KEY:
        result = infermedica_symptom_check(symptoms, age, sex)
        # Format Infermedica output for frontend
        if "conditions" in result:
            # Already formatted
            pass
        elif "conditions" not in result and "conditions" not in result.get("result", {}):
            # Try to extract from diagnosis response
            if "conditions" in result:
                pass
            elif "conditions" in result.get("result", {}):
                result = result["result"]
            elif "conditions" not in result and "conditions" not in result.get("result", {}):
                # Try to extract from diagnosis API response
                if "conditions" in result:
                    pass
                else:
                    # fallback: wrap as error
                    result = {"error": "No conditions found in Infermedica response."}
        # Add top 3 conditions with confidence if available
        if "conditions" in result:
            result["top_conditions"] = [
                {"name": c.get("name"), "confidence": c.get("probability")}
                for c in result["conditions"][:3]
            ]
        return jsonify(result)
    else:
        # Fallback: use local symptom-to-disease lookup
        user_symptoms = [s.strip() for s in symptoms.split(',')]
        top_diseases = get_top_predicted_values(user_symptoms, top_n=3)
        result = {
            "predictions": [ {"name": disease, "confidence": None} for idx, disease in top_diseases ]
        }
        return jsonify(result)

# 2. Emergency Alert Trigger (New Feature)
#    - POST /api/emergency-alert
#      Input: JSON {symptoms: "...", lat: float, lng: float, phone: "...}
#      Output: {emergency: bool, hospitals: [...], sms_sent: bool}

def is_emergency(symptoms):
    # Define a list of keywords that indicate a medical emergency
    emergency_keywords = [
        "chest pain", "shortness of breath", "severe bleeding", "unconscious", "seizure", "stroke",
        "heart attack", "loss of consciousness", "difficulty breathing", "severe allergic reaction",
        "anaphylaxis", "severe pain", "not breathing", "blue lips", "no pulse", "severe burn",
        "major trauma", "confusion", "slurred speech", "weakness on one side", "sudden vision loss"
    ]
    symptoms_lower = symptoms.lower()
    # Improved: also check for synonyms and fuzzy matches
    from fuzzywuzzy import fuzz
    for keyword in emergency_keywords:
        if keyword in symptoms_lower or fuzz.partial_ratio(keyword, symptoms_lower) > 85:
            return True
    return False

def find_nearby_hospitals(lat, lng, api_key, radius=5000):
    """
    Uses Google Places API to find nearby hospitals given latitude and longitude.
    Returns a list of hospitals with name and address.
    """
    url = (
        "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        f"?location={lat},{lng}&radius={radius}&type=hospital&key={api_key}"
    )
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        hospitals = []
        for result in data.get("results", []):
            hospitals.append({
                "name": result.get("name"),
                "address": result.get("vicinity"),
                "location": result.get("geometry", {}).get("location", {}),
                "rating": result.get("rating"),
                "user_ratings_total": result.get("user_ratings_total"),
                "place_id": result.get("place_id"),
                "open_now": result.get("opening_hours", {}).get("open_now", None)
            })
        # Debug: log hospitals found
        logging.debug(f"Nearby hospitals found: {hospitals}")
        # Sort hospitals by open status (True > False/None) and rating (None as 0)
        hospitals = sorted(
            hospitals,
            key=lambda h: (
                bool(h.get("open_now")),  # True > False/None
                h.get("rating") if h.get("rating") is not None else 0
            ),
            reverse=True
        )
        return hospitals
    except Exception as e:
        logging.error(f"Error fetching nearby hospitals: {e}")
        return []

@app.route("/api/emergency-alert", methods=["POST"])
def api_emergency_alert():
    data = request.get_json(force=True)
    symptoms = data.get("symptoms", "")
    lat = data.get("lat")
    lng = data.get("lng")
    phone = data.get("phone")
    emergency = is_emergency(symptoms)
    hospitals = []
    sms_sent = False
    logging.debug(f"Received emergency alert: symptoms={symptoms}, lat={lat}, lng={lng}, phone={phone}, emergency={emergency}")
    if emergency:
        # Query Google Places API for nearby hospitals
        if lat and lng and GOOGLE_API_KEY:
            hospitals = find_nearby_hospitals(lat, lng, GOOGLE_API_KEY)
            logging.debug(f"Hospitals returned to frontend: {hospitals}")
        # Optionally send SMS alert to emergency contact
        if phone:
            def send_sms_alert(phone, message):
                # Placeholder: Implement SMS sending logic here (e.g., using Twilio or another SMS API)
                logging.info(f"SMS sent to {phone}: {message}")
            def sms_thread():
                send_sms_alert(phone, f"Emergency detected: {symptoms}. Please seek immediate help. Location: https://maps.google.com/?q={lat},{lng}")
            import threading
            threading.Thread(target=sms_thread).start()
            sms_sent = True
    else:
        # Even if not an emergency, still return hospitals for map display
        if lat and lng and GOOGLE_API_KEY:
            hospitals = find_nearby_hospitals(lat, lng, GOOGLE_API_KEY)
            logging.debug(f"(Non-emergency) Hospitals returned to frontend: {hospitals}")
    return jsonify({
        "emergency": emergency,
        "hospitals": hospitals,
        "sms_sent": sms_sent
    })

# Add this new route for session checking
@app.route('/check-session')
def check_session():
    is_authenticated = 'user' in session
    logging.info(f"Session check - authenticated: {is_authenticated}, session: {session}")
    return jsonify({'authenticated': is_authenticated})

# ================== Run the App ==================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
