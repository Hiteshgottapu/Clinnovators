# Clinnovators

MedScript is an AI-powered healthcare platform that digitizes medical prescriptions, predicts diseases from symptoms, compares medicine prices, and provides a smart medical chatbot for instant health advice.

## Features

- **Prescription Digitization:** Upload handwritten or printed prescriptions and extract text using AI-powered OCR.
- **AI Consultant:** Enter symptoms and get disease predictions, medication, precautions, diets, and workout recommendations.
- **Medicine Search:** Compare medicine prices across popular Indian pharmacies (Truemeds, PharmEasy, Tata 1mg, Netmeds).
- **Medical Chatbot:** Ask health-related questions and get instant, AI-generated answers.
- **Doctor Consultation:** Get matched with suggested doctors based on your symptoms.
- **Emergency Alert:** Find nearby hospitals and send emergency alerts.

## Tech Stack

- **Backend:** Python, Flask, Firebase, Google Gemini API, Google Vision API
- **Frontend:** HTML, CSS, JavaScript, React (for some components)
- **Database:** Firebase Realtime Database, Firestore
- **Other:** ReportLab (PDF generation), TextBlob (spelling correction), FuzzyWuzzy (fuzzy matching)

## Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/medscript.git
   cd medscript/medscript
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   - Create a `.env` file with your API keys:
     ```
     GOOGLE_API_KEY=your_google_api_key
     GEMINI_API_KEY=your_gemini_api_key
     FIREBASE_API_KEY=your_firebase_api_key
     SENDER_EMAIL=your_email@gmail.com
     SENDER_EMAIL_PASSWORD=your_email_password
     ```

4. **Add Firebase credentials:**
   - Place your Firebase Admin SDK JSON file in the project directory.

5. **Run the Flask app:**
   ```bash
   python app.py
   ```

6. **Access the app:**
   - Open [http://localhost:5000](http://localhost:5000) in your browser.

## Folder Structure

- `app.py` - Main Flask backend
- `templates/` - HTML templates (Jinja2)
- `static/` - CSS, JS, images
- `model/` - ML models (e.g., `svc.pkl`)
- `dataset/` - CSV datasets for symptoms, medications, etc.

## License

This project is for educational purposes.

---

**Developed by:**  
- Hitesh Gottapu  
- Jaswanth Kollipara  
See [developers page](developers.html) for more info.
