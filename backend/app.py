# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from datetime import datetime
import csv
import io

app = Flask(__name__)
CORS(app)

# 上传文件保存目录
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.route('/api/upload', methods=['POST'])
def upload_data():
    """接收上传的软件检测数据"""
    try:
        data = request.get_json()
        
        if not data or 'software_list' not in data:
            return jsonify({'success': False, 'message': '无效的数据'}), 400
        
        dept = data.get('dept', '未知部门')
        name = data.get('name', '未知姓名')
        software_list = data['software_list']
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{dept}_{name}_{timestamp}.csv"
        filepath = os.path.join(UPLOAD_DIR, filename)
        
        # 写入CSV
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            if software_list:
                writer = csv.DictWriter(f, fieldnames=software_list[0].keys())
                writer.writeheader()
                writer.writerows(software_list)
        
        return jsonify({
            'success': True,
            'message': '上传成功',
            'filename': filename,
            'count': len(software_list)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({'status': 'ok', 'message': '服务运行中'})

if __name__ == '__main__':
    print(f"上传目录: {UPLOAD_DIR}")
    print("服务启动在 http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
