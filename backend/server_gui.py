# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox
import threading
import sys
import os
import socket
from datetime import datetime
import csv

# Flask相关
from flask import Flask, request, jsonify
from flask_cors import CORS

# 全局配置
APP_TITLE = "软件检测系统 - 后端服务"
APP_VERSION = "v1.0"
PORT = 5000

# 颜色配置
COLORS = {
    "primary": "#2563EB",
    "success": "#10B981",
    "danger": "#EF4444",
    "bg": "#F8FAFC",
    "card_bg": "#FFFFFF",
    "text": "#1E293B",
    "text_secondary": "#64748B",
    "border": "#E2E8F0"
}

# 上传文件保存目录
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def create_flask_app():
    """创建Flask应用"""
    app = Flask(__name__)
    CORS(app)
    
    @app.route('/api/upload', methods=['POST'])
    def upload_data():
        try:
            data = request.get_json()
            
            if not data or 'software_list' not in data:
                return jsonify({'success': False, 'message': '无效的数据'}), 400
            
            dept = data.get('dept', '未知部门')
            name = data.get('name', '未知姓名')
            software_list = data['software_list']
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{dept}_{name}_{timestamp}.csv"
            filepath = os.path.join(UPLOAD_DIR, filename)
            
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
        return jsonify({'status': 'ok', 'message': '服务运行中'})
    
    return app


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


class BackendServer:
    """后端服务器管理"""
    
    def __init__(self):
        self.thread = None
        self.is_running = False
        self.on_status_change = None
        self.flask_app = create_flask_app()
    
    def start(self):
        if self.is_running:
            return
        
        def run_server():
            self.flask_app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
        
        self.thread = threading.Thread(target=run_server, daemon=True)
        self.thread.start()
        self.is_running = True
        
        if self.on_status_change:
            self.on_status_change(True)
    
    def stop(self):
        self.is_running = False
        if self.on_status_change:
            self.on_status_change(False)


class RoundButton(tk.Canvas):
    """圆形按钮"""
    
    def __init__(self, parent, command=None, size=50, bg_color="#10B981", **kwargs):
        super().__init__(parent, width=size, height=size, 
                         highlightthickness=0, bg=parent.cget('bg'), **kwargs)
        
        self.command = command
        self.size = size
        self.bg_color = bg_color
        self.normal_bg = bg_color
        self.hover_color = self._darken(bg_color)
        self.is_running = False
        
        self._draw_play()
        self._bind_events()
    
    def _darken(self, color, factor=0.8):
        color = color.lstrip('#')
        r, g, b = int(color[:2], 16), int(color[2:4], 16), int(color[4:], 16)
        r, g, b = int(r * factor), int(g * factor), int(b * factor)
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def _draw_play(self):
        self.delete("all")
        self.create_oval(2, 2, self.size-2, self.size-2, fill=self.bg_color, outline="")
        cx, cy = self.size // 2, self.size // 2
        offset = self.size // 6
        points = [cx - offset + 2, cy - offset, cx - offset + 2, cy + offset, cx + offset, cy]
        self.create_polygon(points, fill="white", outline="")
    
    def _draw_stop(self):
        self.delete("all")
        self.create_oval(2, 2, self.size-2, self.size-2, fill=self.bg_color, outline="")
        cx, cy = self.size // 2, self.size // 2
        offset = self.size // 5
        self.create_rectangle(cx - offset, cy - offset, cx + offset, cy + offset, fill="white", outline="")
    
    def _bind_events(self):
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.configure(cursor="hand2")
    
    def _on_enter(self, e):
        self.configure(bg=self.hover_color)
        self.create_oval(2, 2, self.size-2, self.size-2, fill=self.hover_color, outline="", tags="hover")
    
    def _on_leave(self, e):
        self.configure(bg=self.normal_bg)
        self.delete("hover")
        if self.is_running:
            self._draw_stop()
        else:
            self._draw_play()
    
    def _on_release(self, e):
        if self.command:
            self.command()
    
    def set_state(self, running):
        self.is_running = running
        if running:
            self.bg_color = COLORS["danger"]
            self.normal_bg = COLORS["danger"]
            self.hover_color = self._darken(COLORS["danger"])
            self._draw_stop()
        else:
            self.bg_color = COLORS["success"]
            self.normal_bg = COLORS["success"]
            self.hover_color = self._darken(COLORS["success"])
            self._draw_play()


class Application:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_TITLE} {APP_VERSION}")
        self.root.geometry("400x280")
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS["bg"])
        
        self.server = BackendServer()
        self.server.on_status_change = self._on_status_change
        self.local_ip = get_local_ip()
        
        self._setup_ui()
        self._center_window()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _setup_ui(self):
        main = tk.Frame(self.root, bg=COLORS["bg"], padx=30, pady=20)
        main.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(main, text="后端服务控制台", font=("Microsoft YaHei", 18, "bold"),
                 fg=COLORS["text"], bg=COLORS["bg"]).pack(pady=(0, 6))
        
        tk.Label(main, text="软件检测系统 - 数据上传服务", font=("Microsoft YaHei", 10),
                 fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(pady=(0, 24))
        
        status_card = tk.Frame(main, bg=COLORS["card_bg"], highlightbackground=COLORS["border"],
                               highlightthickness=1, padx=20, pady=16)
        status_card.pack(fill=tk.X, pady=(0, 20))
        
        status_row = tk.Frame(status_card, bg=COLORS["card_bg"])
        status_row.pack(fill=tk.X)
        
        status_info = tk.Frame(status_row, bg=COLORS["card_bg"])
        status_info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Label(status_info, text="服务状态", font=("Microsoft YaHei", 11, "bold"),
                 fg=COLORS["text"], bg=COLORS["card_bg"]).pack(anchor=tk.W)
        
        self.status_label = tk.Label(status_info, text="● 已停止", font=("Microsoft YaHei", 14, "bold"),
                                     fg=COLORS["danger"], bg=COLORS["card_bg"])
        self.status_label.pack(anchor=tk.W, pady=(8, 0))
        
        self.ip_label = tk.Label(status_info, text=f"IP: {self.local_ip}  |  端口: {PORT}",
                                 font=("Microsoft YaHei", 9), fg=COLORS["text_secondary"], bg=COLORS["card_bg"])
        self.ip_label.pack(anchor=tk.W, pady=(4, 0))
        
        self.toggle_btn = RoundButton(status_row, command=self._toggle_server, size=50)
        self.toggle_btn.pack(side=tk.RIGHT)
        
        api_frame = tk.Frame(main, bg=COLORS["bg"])
        api_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(api_frame, text="API 地址", font=("Microsoft YaHei", 10, "bold"),
                 fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor=tk.W)
        
        self.api_label = tk.Label(api_frame, text=f"http://{self.local_ip}:{PORT}/api/upload",
                                  font=("Microsoft YaHei", 9), fg=COLORS["primary"], bg=COLORS["bg"])
        self.api_label.pack(anchor=tk.W, pady=(4, 0))
    
    def _center_window(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"+{x}+{y}")
    
    def _toggle_server(self):
        if self.server.is_running:
            self._stop_server()
        else:
            self._start_server()
    
    def _start_server(self):
        try:
            self.toggle_btn.configure(state=tk.DISABLED)
            self.status_label.config(text="● 启动中...", fg=COLORS["primary"])
            self.root.update()
            
            self.server.start()
            
            self.status_label.config(text="● 运行中", fg=COLORS["success"])
            self.toggle_btn.set_state(True)
            self.toggle_btn.configure(state=tk.NORMAL)
        except Exception as e:
            messagebox.showerror("启动失败", f"无法启动服务器:\n{str(e)}")
            self.status_label.config(text="● 已停止", fg=COLORS["danger"])
            self.toggle_btn.set_state(False)
            self.toggle_btn.configure(state=tk.NORMAL)
    
    def _stop_server(self):
        self.server.stop()
        self.status_label.config(text="● 已停止", fg=COLORS["danger"])
        self.toggle_btn.set_state(False)
    
    def _on_status_change(self, is_running):
        pass
    
    def _on_close(self):
        self.root.destroy()
    
    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = Application()
    app.run()
