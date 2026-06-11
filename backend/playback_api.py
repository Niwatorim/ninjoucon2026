from flask import Blueprint

playback_bp = Blueprint('playback', __name__)

@playback_bp.route('/teacher_only', methods=['GET'])
def vid():
    pass

@playback_bp.route('/unity_3dmocap', methods=['GET'])
def vid():
    pass
