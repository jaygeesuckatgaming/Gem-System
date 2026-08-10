from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/tts', methods=['POST'])
def text_to_speech():
    data = request.get_json()
    return jsonify(data)  # Just echo back the received JSON

if __name__ == '__main__':
    app.run(debug=True, port=8000)  # Change the port to 8000