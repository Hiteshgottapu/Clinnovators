import re

def format_response(response_text, section_headers=None):
    """
    Formats the AI response to resemble a professional doctor's recommendation and prescription format.
    Adds new lines before bullet points and bold section headers for clarity.

    :param response_text: The text to format.
    :param section_headers: Optional dictionary to customize section headers.
    :return: Formatted text.
    """
    if not response_text:
        return "I'm sorry, but I couldn't generate a response."

    # Default section headers
    default_headers = {
        "diagnosis": "🩺 Diagnosis",
        "symptoms": "✅ Symptoms",
        "treatment": "💊 Treatment Plan",
        "prescription": "📜 Prescription",
        "lifestyle": "🏃‍♂️ Lifestyle Advice",
        "see_doctor": "🏥 When to See a Doctor"
    }

    # Use custom headers if provided
    if section_headers:
        default_headers.update(section_headers)

    # Remove unwanted characters and extra spaces
    formatted_text = response_text.replace("*", "").strip()
    
    # Add new line before each bolded section title (**Title**) for better spacing
    formatted_text = re.sub(r'(\*\*.+?\*\*)', r'\n\1', formatted_text)

    # Add new line before each bullet point (- Item)
    formatted_text = re.sub(r'(\n?)(- )', r'\n\2', formatted_text)

    # Split text into structured sections
    sections = {header: [] for header in default_headers.values()}

    # Split text into lines for processing
    lines = [line.strip() for line in formatted_text.split('\n') if line.strip()]

    current_section = default_headers["diagnosis"]
    sub_points = []

    for line in lines:
        # Detect section headers based on keywords
        if any(keyword in line.lower() for keyword in ["cause", "diagnose", "reason"]):
            current_section = default_headers["diagnosis"]
        elif any(keyword in line.lower() for keyword in ["symptom", "sign"]):
            current_section = default_headers["symptoms"]
        elif any(keyword in line.lower() for keyword in ["treat", "manage", "therapy", "cure"]):
            current_section = default_headers["treatment"]
        elif any(keyword in line.lower() for keyword in ["medication", "drug", "prescription"]):
            current_section = default_headers["prescription"]
        elif any(keyword in line.lower() for keyword in ["prevent", "lifestyle", "habit"]):
            current_section = default_headers["lifestyle"]
        elif any(keyword in line.lower() for keyword in ["doctor", "consult", "emergency", "serious"]):
            current_section = default_headers["see_doctor"]

        # Handle bullet points
        if line.startswith("-"):
            sub_points.append(line)
        else:
            if sub_points:
                sections[current_section].extend(sub_points)
                sub_points = []
            sections[current_section].append(line)

    if sub_points:
        sections[current_section].extend(sub_points)

    # Construct final formatted response with correct spacing
    result = []

    for section, content in sections.items():
        if content:
            result.append(f"\n**{section}**\n")  # Add newline before section title
            if isinstance(content, list):
                for item in content:
                    # Bold important medical details
                    if section == default_headers["prescription"] and any(word in item.lower() for word in ["mg", "tablet", "dose", "injection"]):
                        item = f"**{item}**"  # Highlight medication details
                    result.append(f"{item}\n")
            else:
                result.append(f"{content}\n")

    return ''.join(result).strip()

# Example usage
response_text = """
**🩺 Diagnosis** Neck Pain: Causes, Symptoms, and Treatment Causes of Neck Pain: Muscle strain or sprains Poor posture Degenerative conditions (e.g., osteoarthritis, herniated disc) Nerve compression Injuries (e.g., whiplash) Medical conditions (e.g., fibromyalgia, rheumatoid arthritis) **✅ Symptoms** Symptoms of Neck Pain: Sharp or dull pain in the neck Stiffness or decreased range of motion Headaches Numbness or tingling in the arms or hands Muscle weakness If you have a fever or other symptoms that suggest an infection If neck pain affects your daily activities or sleep **💊 Treatment Plan** Treatment Options: Heat or cold therapy: Applying heat or cold to the affected area can provide temporary relief. Physical therapy: Exercises and stretches can help strengthen neck muscles and improve posture. Massage therapy: Massage can relax tense muscles and improve circulation. Acupuncture: Acupuncture may help reduce pain and inflammation. Manage stress: Stress can contribute to neck pain. Find healthy ways to manage stress, such as exercise or meditation. **📜 Prescription** Over-the-counter pain relievers: Nonsteroidal anti-inflammatory drugs (NSAIDs) or acetaminophen can help reduce pain. Prescription medications: Muscle relaxants or stronger pain relievers may be necessary in severe cases. **Cortisone injections: Injections of cortisone can reduce inflammation and relieve pain.** Surgery: Surgery may be considered in rare cases of severe nerve damage or spinal instability. Self-Care Tips: Maintain good posture: Avoid slouching or hunching over. Stretch your neck: Perform regular neck stretches to improve flexibility and reduce tension. Strengthen neck muscles: Engage in exercises that strengthen neck muscles, such as neck rotations and side bends. Use a neck support: Consider using a neck brace or pillow to support the neck and reduce strain. Avoid smoking: Smoking can worsen neck pain. **🏥 When to See a Doctor** When to See a Doctor: If neck pain is severe or persistent If you experience any numbness or weakness in your arms or hands
"""

print(format_response(response_text))