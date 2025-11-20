from flask import Flask, jsonify
from tkinter import Tk, filedialog
import sys

app = Flask(__name__)

@app.route('/select-folder', methods=['GET'])
def select_folder():
    try:
        root = Tk()
        root.withdraw()
        root.attributes('-topmost', True)  # Поверх всех окон
        folder = filedialog.askdirectory()
        root.destroy()
        
        if folder:
            return jsonify({"path": folder, "success": True})
        else:
            return jsonify({"path": "", "success": False, "error": "Папка не выбрана"})
    except Exception as e:
        return jsonify({"path": "", "success": False, "error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host="127.0.0.1", port=5678, debug=False)
