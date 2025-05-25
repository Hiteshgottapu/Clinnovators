from flask import Flask, request, render_template, redirect, url_for, session, jsonify, send_file, send_from_directory
import io
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from utils import search_medicine_prices, extract_text_from_image, medical_chatbot
import os

app = Flask(__name__)  # Initialize the Flask application

# Route for the medicine search page
@app.route("/medicine", methods=["GET", "POST"])
def medicine_search():
    if request.method == "POST":
        medicine_name = request.form.get("medicine_name")
        if not medicine_name:
            return redirect(url_for("medicine_search"))
        results = search_medicine_prices(medicine_name)
        return render_template("medicine_search.html", results=results, medicine_name=medicine_name)
    return render_template("medicine_search.html")

# API route for fetching medicine prices
@app.route("/medicine-search", methods=["GET"])
def medicine_search_api():
    medicine_name = request.args.get("name")
    if not medicine_name:
        return jsonify({"error": "Medicine name is required"}), 400

    results = search_medicine_prices(medicine_name)
    return jsonify(results)

# Route for chat
@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")

    if not user_message:
        return jsonify({"response": "Invalid request. No message provided."}), 400

    reply = medical_chatbot(user_message)
    return jsonify({"response": reply})

# Route for the index page
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("image")
        if file:
            try:
                text = extract_text_from_image(file)
                return render_template("index.html", text=text)
            except Exception as e:
                logging.error(f"Image processing error: {str(e)}")
                return render_template("index.html", text=f"Error: {str(e)}")
    return render_template("index.html")

# Other Routes
@app.route('/features')
def features():
    return render_template('features.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/login.html')
def login():
    return render_template('login.html')

@app.route('/signup.html')
def signup():
    return render_template('signup.html')

@app.route('/forgot-password.html')
def forgot_password():
    return render_template('forgot-password.html')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if request.method == 'POST':
        session['profile'] = {
            'name': request.form.get('name'),
            'email': request.form.get('email'),
            'phone': request.form.get('phone')
        }
        return redirect(url_for('profile'))
    return render_template('profile.html', profile=session.get('profile', {
        'name': 'Gottapu Hitesh',
        'email': 'hiteshgottapu309@gmail.com',
        'phone': '+91 8143506309'
    }))

@app.route('/download')
def download_file():
    text = request.args.get('text', '')
    text_file = io.BytesIO(text.encode('utf-8'))
    return send_file(text_file, as_attachment=True, download_name='extracted_text.txt', mimetype='text/plain')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/send_message', methods=['POST'])
def send_message():
    # Get form data
    name = request.form.get('name')
    message = request.form.get('message')

    # Email configuration
    sender_email = "hiteshgottapu@gmail.com"  # Replace with your email
    receiver_email = "gottapuhitesh@gmail.com"  # Fixed recipient email
    password = os.getenv("EMAIL_PASSWORD")  # Replace with your email password

    # Create the email
    subject = f"New Message from {name}"
    body = f"""
    Name: {name}
    Message: {message}
    """

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    # Send the email
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        return jsonify({"success": True, "message": "Message sent successfully!"})
    except Exception as e:
        logging.error(f"Error: {e}")
        return jsonify({"success": False, "message": "Failed to send message."})

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/developers')
def developers():
    return render_template('developers.html')

@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')
