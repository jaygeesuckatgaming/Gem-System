from flask import Flask, request, jsonify


app = Flask(__name__)



@app.route('/tts', methods=['POST'])
def text_to_speech():
    """
    Handles POST requests with text to generate speech.
    Returns the audio as a response.  (Simplified, you'll need to handle audio format)
    """
    try:
        data = request.get_json()
        text_to_speak = data.get('text')

        if not text_to_speak:
            return jsonify({'error': 'No text provided in the request body'}), 400

        # Generate speech
        engine.say(text_to_speak)
        engine.runAndWait()

        # In a real application, you'd save the audio to a file,
        # then return the file as a response with appropriate headers.
        # This is a placeholder:
        return jsonify({'message': 'Speech generated successfully (audio not actually returned)'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)