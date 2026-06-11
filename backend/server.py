from flask import Flask
from learn_api import learn_bp
from playback_api import playback_bp

app = Flask(__name__)
app.register_blueprint(learn_bp, url_prefix='/learn')
app.register_blueprint(playback_bp, url_prefix='/playback')

if __name__ == '__main__':
    app.run(debug=True)

