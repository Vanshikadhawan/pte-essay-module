from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import requests
import re
import os

app = Flask(__name__)
CORS(app)

# Load environment variables
load_dotenv()
api_key = os.getenv("OPENROUTER_API_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY")

MODEL_NAME = "deepseek/deepseek-r1"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

@app.route("/evaluate_essay", methods=["POST"])
def evaluate_essay():
    try:
        data = request.json
        student_essay = data.get("content", "").strip()

        if not student_essay:
            return jsonify({"error": "No essay provided"}), 400

        # Count words in the essay
        word_count = len(student_essay.split())

        # Word limit conditions
        min_words = 200
        max_words = 300

        # Calculate score penalty dynamically
        if word_count < min_words:
            missing_words = min_words - word_count
            score_penalty = round(missing_words / 20, 1)  # Deduct 0.5 per 10 words missing
            score_penalty = min(score_penalty, 3)  # Max deduction is 3 points
            length_feedback = (
                f"Your essay is too short ({word_count} words). You must write at least {min_words} words. "
                f"A penalty of {score_penalty} points has been applied."
            )
        elif word_count > max_words:
            score_penalty = 1  # Small penalty for exceeding limit
            length_feedback = (
                f"Your essay exceeds the {max_words}-word limit ({word_count} words). "
                f"A minor penalty of {score_penalty} points has been applied."
            )
        else:
            score_penalty = 0
            length_feedback = ""

        # Stronger prompt to enforce strict word limit feedback
        prompt = (
            f"Evaluate the student's essay based on coherence, structure, grammar, vocabulary, and argument strength. "
            f"The essay should strictly be between {min_words}-{max_words} words. "
            f"If the essay is shorter, deduct points and clearly mention that it does not meet the requirement. "
            f"Provide feedback in exactly five lines, ensuring clear feedback on all aspects. "
            f"At the end, state: 'Overall Score: X/10' where X is the calculated score. "
            f"Do NOT omit the score under any circumstances.\n\n"
            f"Student's Essay ({word_count} words): \"{student_essay}\"\n\n"
            f"Feedback:"
        )

        headers = {
            "Authorization": f"Bearer {SECRET_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,
            "max_tokens": 300
        }

        response = requests.post(API_URL, json=payload, headers=headers)

        if response.status_code != 200:
            return jsonify({"error": "API request failed", "details": response.text}), 500

        response_json = response.json()

        if "choices" not in response_json or not response_json["choices"]:
            return jsonify({"error": "Invalid AI response format", "details": response_json}), 500

        ai_feedback = response_json["choices"][0].get("message", {}).get("content", "").strip()

        if ai_feedback:
            # Extract AI-generated score
            match = re.search(r'Overall Score:\s*([\d.]+)/10', ai_feedback)
            if match:
                ai_score = float(match.group(1))
            else:
                ai_score = 5  # Default to 5 if AI fails to provide a score

            # Apply penalty dynamically
            final_score = max(1, ai_score - score_penalty)  # Ensure score is at least 1

            # Append word count feedback to AI's response
            final_feedback = ai_feedback
            if length_feedback:
                final_feedback += f" {length_feedback}"

            # Debugging log
            print("AI Feedback:", ai_feedback)
            print("Extracted Score:", ai_score)
            print("Final Score after Penalty:", final_score)

            return jsonify({
                "feedback": final_feedback,
                "score": final_score,
                "word_count": word_count
            })

        return jsonify({"error": "Empty response from AI", "details": response_json}), 500

    except Exception as e:
        return jsonify({"error": "Server error", "details": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
