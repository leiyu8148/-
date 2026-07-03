# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import os
import subprocess
import winreg
from datetime import datetime
import zipfile
import sys
import ctypes
import threading
from queue import Queue
import urllib.request
import json

# 尝试导入pyzipper用于加密，如果不可用则使用标准zipfile
try:
    import pyzipper
    HAS_PYZIPPER = True
except ImportError:
    HAS_PYZIPPER = False

# 全局配置
APP_TITLE = "已安装软件检测工具"
APP_VERSION = "v1.0"
ZIP_PASSWORD = "123456"
SYSTEM_ROOT = os.environ.get("SystemRoot", "C:\\Windows")

# 颜色配置
COLORS = {
    "primary": "#2563EB",
    "primary_hover": "#1D4ED8",
    "success": "#10B981",
    "success_hover": "#059669",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "bg": "#F8FAFC",
    "card_bg": "#FFFFFF",
    "text": "#1E293B",
    "text_secondary": "#64748B",
    "border": "#E2E8F0",
    "table_header": "#F1F5F9",
    "table_row": "#FFFFFF",
    "table_row_alt": "#F8FAFC"
}


class SoftwareDetector:
    """已安装软件检测器"""
    
    def __init__(self):
        self.software_list = []
        self.seen_names = set()
        self._progress_callback = None
        
    def set_progress_callback(self, callback):
        """设置进度回调"""
        self._progress_callback = callback
    
    def _report_progress(self, message):
        """报告进度"""
        if self._progress_callback:
            self._progress_callback(message)
    
    def detect_all(self):
        """执行所有检测方法"""
        self.software_list = []
        self.seen_names = set()
        
        self._report_progress("正在从注册表获取软件列表...")
        self._detect_from_registry()
        
        self._report_progress("正在通过WMI获取软件信息...")
        self._detect_from_wmi()
        
        self._report_progress("正在通过PowerShell获取...")
        self._detect_from_powershell()
        
        self._report_progress("正在通过WinGet获取...")
        self._detect_from_winget()
        
        self._report_progress("正在整理结果...")
        self.software_list.sort(key=lambda x: x['名称'].lower())
        
        # 更新序号
        for i, sw in enumerate(self.software_list):
            sw["序号"] = i + 1
        
        return self.software_list
    
    def _add_software(self, name, version="", publisher="", install_date="", source=""):
        """添加软件到列表（自动去重）"""
        if not name or len(name) < 2:
            return
        key = f"{name.lower()}_{version}"
        if key not in self.seen_names:
            self.seen_names.add(key)
            self.software_list.append({
                "序号": len(self.software_list) + 1,
                "名称": name,
                "版本": version,
                "发布者": publisher,
                "安装日期": install_date,
                "来源": source
            })
    
    def _detect_from_registry(self):
        """通过注册表检测已安装软件"""
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", "注册表"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", "注册表(32位)"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", "注册表(当前用户)"),
        ]
        
        for hive, path, source in reg_paths:
            try:
                key = winreg.OpenKey(hive, path)
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey = winreg.OpenKey(key, subkey_name)
                        
                        try:
                            name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        except FileNotFoundError:
                            i += 1
                            continue
                        
                        version = self._safe_query(subkey, "DisplayVersion")
                        publisher = self._safe_query(subkey, "Publisher")
                        install_date = self._safe_query(subkey, "InstallDate")
                        
                        self._add_software(name, version, publisher, install_date, source)
                        winreg.CloseKey(subkey)
                    except OSError:
                        break
                    i += 1
                winreg.CloseKey(key)
            except Exception:
                continue
    
    def _safe_query(self, key, value_name):
        """安全查询注册表值"""
        try:
            return winreg.QueryValueEx(key, value_name)[0]
        except (FileNotFoundError, OSError):
            return ""
    
    def _detect_from_wmi(self):
        """通过WMI检测已安装软件"""
        try:
            cmd = 'wmic product get Name,Version,Vendor,InstallDate /format:csv'
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, 
                timeout=30, encoding='gbk', errors='ignore'
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    for line in lines[1:]:
                        parts = line.strip().split(',')
                        if len(parts) >= 4 and parts[1]:
                            name = parts[1].strip()
                            version = parts[3].strip() if len(parts) > 3 else ""
                            publisher = parts[4].strip() if len(parts) > 4 else ""
                            install_date = parts[2].strip() if len(parts) > 2 else ""
                            self._add_software(name, version, publisher, install_date, "WMI")
        except Exception:
            pass
    
    def _detect_from_powershell(self):
        """通过PowerShell检测"""
        try:
            cmd = 'powershell -Command "Get-Package | Select-Object Name, Version, ProviderName | ConvertTo-Csv"'
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=30, encoding='utf-8', errors='ignore'
            )
            if result.returncode == 0 and result.stdout:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    reader = csv.DictReader(lines)
                    for row in reader:
                        name = row.get('Name', '').strip()
                        version = row.get('Version', '').strip()
                        self._add_software(name, version, source="PowerShell")
        except Exception:
            pass
    
    def _detect_from_winget(self):
        """通过WinGet检测"""
        try:
            cmd = 'winget list --disable-interactivity --accept-source-agreements'
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=60, encoding='utf-8', errors='ignore'
            )
            if result.returncode == 0 and result.stdout:
                lines = result.stdout.split('\n')
                header_found = False
                for line in lines:
                    if '---' in line:
                        header_found = True
                        continue
                    if header_found and line.strip():
                        parts = line.split()
                        if len(parts) >= 2:
                            name = parts[0]
                            version = parts[1]
                            self._add_software(name, version, source="WinGet")
        except Exception:
            pass


class ModernButton(tk.Canvas):
    """现代风格按钮"""
    
    def __init__(self, parent, text="", command=None, bg_color="#2563EB", 
                 hover_color="#1D4ED8", text_color="white", font=("Segoe UI", 11, "bold"),
                 width=140, height=42, radius=8, **kwargs):
        super().__init__(parent, width=width, height=height, 
                         highlightthickness=0, bg=parent.cget('bg'), **kwargs)
        
        self.command = command
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.normal_bg = bg_color
        self.text_color = text_color
        self.width = width
        self.height = height
        self.radius = radius
        self.text = text
        self.font = font
        self.enabled = True
        
        self._draw(bg_color)
        self._bind_events()
    
    def _draw(self, color):
        """绘制按钮"""
        self.delete("all")
        self.round_rectangle(2, 2, self.width-2, self.height-2, 
                           radius=self.radius, fill=color, outline="")
        self.create_text(self.width/2, self.height/2, text=self.text, 
                        fill=self.text_color, font=self.font)
    
    def _bind_events(self):
        """绑定事件"""
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.configure(cursor="hand2")
    
    def _on_enter(self, e):
        if self.enabled:
            self._draw(self.hover_color)
    
    def _on_leave(self, e):
        if self.enabled:
            self._draw(self.normal_bg)
    
    def _on_press(self, e):
        if self.enabled:
            self._draw(self.hover_color)
    
    def _on_release(self, e):
        if self.enabled and self.command:
            self.command()
        if self.enabled:
            self._draw(self.normal_bg)
    
    def round_rectangle(self, x1, y1, x2, y2, radius=25, **kwargs):
        """绘制圆角矩形"""
        points = [
            x1+radius, y1,
            x2-radius, y1,
            x2, y1, x2, y1+radius,
            x2, y2-radius,
            x2, y2, x2-radius, y2,
            x1+radius, y2,
            x1, y2, x1, y2-radius,
            x1, y1+radius,
            x1, y1, x1+radius, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)
    
    def configure_state(self, enabled=True):
        """配置按钮状态"""
        self.enabled = enabled
        if not enabled:
            self._draw("#94A3B8")
            self.configure(cursor="")
        else:
            self._draw(self.normal_bg)
            self.configure(cursor="hand2")


class CardFrame(tk.Frame):
    """卡片样式框架"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLORS["card_bg"], **kwargs)
        self.configure(
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            padx=20,
            pady=20
        )


class InputDialog(tk.Toplevel):
    """部门姓名输入对话框"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.result = None
        self.transient(parent)
        self.grab_set()
        
        self.title("导出信息")
        self.geometry("400x280")
        self.resizable(False, False)
        self.configure(bg=COLORS["border"])
        
        self._setup_ui()
        self._center_window(parent)
        
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
    
    def _setup_ui(self):
        """设置对话框UI"""
        # 外层卡片
        card = tk.Frame(self, bg=COLORS["card_bg"], padx=2, pady=2)
        card.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        # 内容容器
        container = tk.Frame(card, bg=COLORS["card_bg"], padx=28, pady=20)
        container.pack(fill=tk.BOTH, expand=True)
        
        # 部门输入
        dept_group = tk.Frame(container, bg=COLORS["card_bg"])
        dept_group.pack(fill=tk.X, pady=(0, 14))
        
        tk.Label(
            dept_group,
            text="部门",
            font=("Microsoft YaHei", 10),
            fg=COLORS["text"],
            bg=COLORS["card_bg"]
        ).pack(anchor=tk.W, pady=(0, 4))
        
        dept_border = tk.Frame(dept_group, bg=COLORS["border"], bd=0)
        dept_border.pack(fill=tk.X)
        
        self.dept_entry = tk.Entry(
            dept_border,
            font=("Microsoft YaHei", 11),
            relief=tk.FLAT,
            bg="white",
            fg=COLORS["text"],
            insertbackground=COLORS["primary"]
        )
        self.dept_entry.pack(fill=tk.X, padx=1, pady=1, ipady=6)
        self.dept_entry.focus_set()
        
        # 姓名输入
        name_group = tk.Frame(container, bg=COLORS["card_bg"])
        name_group.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(
            name_group,
            text="姓名",
            font=("Microsoft YaHei", 10),
            fg=COLORS["text"],
            bg=COLORS["card_bg"]
        ).pack(anchor=tk.W, pady=(0, 4))
        
        name_border = tk.Frame(name_group, bg=COLORS["border"], bd=0)
        name_border.pack(fill=tk.X)
        
        self.name_entry = tk.Entry(
            name_border,
            font=("Microsoft YaHei", 11),
            relief=tk.FLAT,
            bg="white",
            fg=COLORS["text"],
            insertbackground=COLORS["primary"]
        )
        self.name_entry.pack(fill=tk.X, padx=1, pady=1, ipady=6)
        
        # 按钮区域
        btn_frame = tk.Frame(container, bg=COLORS["card_bg"])
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 确定按钮
        ok_btn = ModernButton(
            btn_frame,
            text="确定",
            command=self._on_ok,
            bg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            width=100,
            height=38,
            radius=6
        )
        ok_btn.pack(side=tk.RIGHT, padx=(8, 0))
        
        # 取消按钮
        cancel_btn = ModernButton(
            btn_frame,
            text="取消",
            command=self._on_cancel,
            bg_color="#E5E7EB",
            hover_color="#D1D5DB",
            text_color=COLORS["text"],
            width=100,
            height=38,
            radius=6
        )
        cancel_btn.pack(side=tk.RIGHT)
        
        # 绑定回车和ESC
        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self._on_cancel())
    
    def _center_window(self, parent):
        """居中显示"""
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_x()
        py = parent.winfo_y()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")
    
    def _on_ok(self):
        """确定按钮"""
        dept = self.dept_entry.get().strip()
        name = self.name_entry.get().strip()
        
        if not dept:
            self.dept_entry.configure(bg="#FEE2E2")
            self.dept_entry.focus_set()
            self.after(500, lambda: self.dept_entry.configure(bg=COLORS["bg"]))
            return
        
        if not name:
            self.name_entry.configure(bg="#FEE2E2")
            self.name_entry.focus_set()
            self.after(500, lambda: self.name_entry.configure(bg=COLORS["bg"]))
            return
        
        self.result = (dept, name)
        self.destroy()
    
    def _on_cancel(self):
        """取消按钮"""
        self.result = None
        self.destroy()


class Application:
    """GUI应用程序"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_TITLE} {APP_VERSION}")
        self.root.geometry("950x650")
        self.root.minsize(800, 550)
        self.root.configure(bg=COLORS["bg"])
        
        self.detector = SoftwareDetector()
        self.software_data = []
        self.is_detecting = False
        
        # 用于线程通信
        self.queue = Queue()
        
        self._setup_ui()
        self._center_window()
        self._check_queue()
    
    def _setup_ui(self):
        """设置UI界面"""
        main_container = tk.Frame(self.root, bg=COLORS["bg"])
        main_container.pack(fill=tk.BOTH, expand=True, padx=24, pady=20)
        
        # === 顶部标题区域 ===
        header_frame = tk.Frame(main_container, bg=COLORS["bg"])
        header_frame.pack(fill=tk.X, pady=(0, 16))
        
        logo_frame = tk.Frame(header_frame, bg=COLORS["bg"])
        logo_frame.pack(side=tk.LEFT)
        
        icon_label = tk.Label(
            logo_frame,
            text="",
            font=("Segoe UI", 28),
            bg=COLORS["bg"]
        )
        icon_label.pack(side=tk.LEFT, padx=(0, 12))
        
        title_frame = tk.Frame(logo_frame, bg=COLORS["bg"])
        title_frame.pack(side=tk.LEFT)
        
        tk.Label(
            title_frame,
            text="已安装软件检测工具",
            font=("Microsoft YaHei", 22, "bold"),
            fg=COLORS["text"],
            bg=COLORS["bg"]
        ).pack(anchor=tk.W)
        
        tk.Label(
            title_frame,
            text="Installed Software Detector",
            font=("Segoe UI", 10),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg"]
        ).pack(anchor=tk.W)
        
        version_frame = tk.Frame(header_frame, bg=COLORS["bg"])
        version_frame.pack(side=tk.RIGHT, anchor=tk.NE)
        
        tk.Label(
            version_frame,
            text=APP_VERSION,
            font=("Segoe UI", 10),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg"]
        ).pack()
        
        # === 信息卡片区域 ===
        cards_frame = tk.Frame(main_container, bg=COLORS["bg"])
        cards_frame.pack(fill=tk.X, pady=(0, 16))
        
        card1 = CardFrame(cards_frame)
        card1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        
        tk.Label(
            card1,
            text="检测方式",
            font=("Microsoft YaHei", 11, "bold"),
            fg=COLORS["text"],
            bg=COLORS["card_bg"]
        ).pack(anchor=tk.W)
        
        tk.Label(
            card1,
            text="注册表 | WMI | PowerShell | WinGet",
            font=("Segoe UI", 9),
            fg=COLORS["text_secondary"],
            bg=COLORS["card_bg"]
        ).pack(anchor=tk.W, pady=(4, 0))
        
        card3 = CardFrame(cards_frame)
        card3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tk.Label(
            card3,
            text="检测状态",
            font=("Microsoft YaHei", 11, "bold"),
            fg=COLORS["text"],
            bg=COLORS["card_bg"]
        ).pack(anchor=tk.W)
        
        self.status_label = tk.Label(
            card3,
            text="准备就绪",
            font=("Segoe UI", 9),
            fg=COLORS["success"],
            bg=COLORS["card_bg"]
        )
        self.status_label.pack(anchor=tk.W, pady=(4, 0))
        
        # === 操作按钮区域 ===
        btn_frame = tk.Frame(main_container, bg=COLORS["bg"])
        btn_frame.pack(fill=tk.X, pady=(0, 16))
        
        self.detect_btn = ModernButton(
            btn_frame,
            text="开始检测",
            command=self.start_detection,
            bg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            width=180,
            height=48,
            radius=10
        )
        self.detect_btn.pack(side=tk.LEFT)
        
        right_btns = tk.Frame(btn_frame, bg=COLORS["bg"])
        right_btns.pack(side=tk.RIGHT)
        
        self.export_btn = ModernButton(
            right_btns,
            text="上传",
            command=self.upload_data,
            bg_color="#8B5CF6",
            hover_color="#7C3AED",
            width=80,
            height=42,
            radius=8
        )
        self.export_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.export_btn.configure_state(False)
        
        # 服务器地址输入框
        server_frame = tk.Frame(right_btns, bg=COLORS["bg"])
        server_frame.pack(side=tk.LEFT, padx=(0, 8))
        
        tk.Label(
            server_frame,
            text="服务器:",
            font=("Microsoft YaHei", 9),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg"]
        ).pack(side=tk.LEFT, padx=(0, 4))
        
        self.server_entry = tk.Entry(
            server_frame,
            font=("Microsoft YaHei", 10),
            width=18,
            relief=tk.SOLID,
            bd=1
        )
        self.server_entry.pack(side=tk.LEFT)
        self.server_entry.insert(0, "")
        
        self.export_zip_btn = ModernButton(
            right_btns,
            text="打包导出",
            command=self.export_encrypted_zip,
            bg_color=COLORS["success"],
            hover_color=COLORS["success_hover"],
            width=100,
            height=42,
            radius=8
        )
        self.export_zip_btn.pack(side=tk.LEFT)
        self.export_zip_btn.configure_state(False)
        
        # === 进度条区域 ===
        self.progress_frame = tk.Frame(main_container, bg=COLORS["bg"])
        self.progress_frame.pack(fill=tk.X, pady=(0, 12))
        
        self.progress = ttk.Progressbar(
            self.progress_frame,
            mode='indeterminate',
            length=300
        )
        self.progress.pack(side=tk.LEFT)
        
        self.progress_label = tk.Label(
            self.progress_frame,
            text="",
            font=("Segoe UI", 9),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg"]
        )
        self.progress_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # === 数据表格区域 ===
        table_card = CardFrame(main_container)
        table_card.pack(fill=tk.BOTH, expand=True)
        
        toolbar = tk.Frame(table_card, bg=COLORS["card_bg"])
        toolbar.pack(fill=tk.X, pady=(0, 12))
        
        tk.Label(
            toolbar,
            text="检测结果",
            font=("Microsoft YaHei", 12, "bold"),
            fg=COLORS["text"],
            bg=COLORS["card_bg"]
        ).pack(side=tk.LEFT)
        
        self.count_label = tk.Label(
            toolbar,
            text="共 0 个软件",
            font=("Segoe UI", 10),
            fg=COLORS["text_secondary"],
            bg=COLORS["card_bg"]
        )
        self.count_label.pack(side=tk.RIGHT)
        
        table_container = tk.Frame(table_card, bg=COLORS["card_bg"])
        table_container.pack(fill=tk.BOTH, expand=True)
        
        columns = ("序号", "名称", "版本", "发布者", "安装日期", "来源")
        self.tree = ttk.Treeview(
            table_container,
            columns=columns,
            show="headings",
            height=12
        )
        
        style = ttk.Style()
        style.theme_use("clam")
        
        style.configure("Custom.Treeview",
                        background=COLORS["table_row"],
                        foreground=COLORS["text"],
                        rowheight=35,
                        fieldbackground=COLORS["table_row"],
                        font=("Segoe UI", 10))
        
        style.configure("Custom.Treeview.Heading",
                        background=COLORS["table_header"],
                        foreground=COLORS["text"],
                        font=("Microsoft YaHei", 10, "bold"),
                        borderwidth=0,
                        relief="flat")
        
        style.map("Custom.Treeview.Heading",
                  background=[("active", COLORS["border"])])
        
        style.map("Custom.Treeview",
                  background=[("selected", "#DBEAFE")],
                  foreground=[("selected", COLORS["primary"])])
        
        self.tree.configure(style="Custom.Treeview")
        
        col_config = {
            "序号": {"width": 60, "anchor": "center"},
            "名称": {"width": 280, "anchor": "w"},
            "版本": {"width": 100, "anchor": "center"},
            "发布者": {"width": 200, "anchor": "w"},
            "安装日期": {"width": 100, "anchor": "center"},
            "来源": {"width": 100, "anchor": "center"}
        }
        
        for col, config in col_config.items():
            self.tree.column(col, width=config["width"], minwidth=config["width"]-20)
            self.tree.heading(col, text=col, anchor=config["anchor"])
        
        v_scrollbar = ttk.Scrollbar(table_container, orient=tk.VERTICAL, command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(table_container, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)
        
        # === 底部信息 ===
        footer_frame = tk.Frame(main_container, bg=COLORS["bg"])
        footer_frame.pack(fill=tk.X, pady=(16, 0))
        
        tk.Label(
            footer_frame,
            text="支持检测: 注册表、WMI、PowerShell、WinGet",
            font=("Segoe UI", 8),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg"]
        ).pack(side=tk.LEFT)
    
    def _center_window(self):
        """窗口居中"""
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"+{x}+{y}")
    
    def _check_queue(self):
        """检查队列中的消息（用于线程通信）"""
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                
                if msg_type == "progress":
                    self.progress_label.config(text=data)
                
                elif msg_type == "complete":
                    self._on_detection_complete(data)
                    return
                
                elif msg_type == "error":
                    self._on_detection_error(data)
                    return
                    
        except Exception:
            pass
        
        self.root.after(100, self._check_queue)
    
    def start_detection(self):
        """开始检测"""
        if self.is_detecting:
            return
        
        self.is_detecting = True
        
        self.detect_btn.configure_state(False)
        self.detect_btn.text = "检测中..."
        self.detect_btn._draw("#94A3B8")
        
        self.export_btn.configure_state(False)
        self.export_zip_btn.configure_state(False)
        
        self.progress.start(15)
        self.status_label.config(text="检测中...", fg=COLORS["warning"])
        
        # 清空表格
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        self.count_label.config(text="检测中...")
        
        # 在后台线程中执行检测
        self.detector.set_progress_callback(self._report_progress)
        thread = threading.Thread(target=self._run_detection_thread, daemon=True)
        thread.start()
    
    def _report_progress(self, message):
        """从后台线程报告进度"""
        self.queue.put(("progress", message))
    
    def _run_detection_thread(self):
        """后台线程执行检测"""
        try:
            data = self.detector.detect_all()
            self.queue.put(("complete", data))
        except Exception as e:
            self.queue.put(("error", str(e)))
    
    def _on_detection_complete(self, data):
        """检测完成回调（主线程）"""
        self.software_data = data
        
        # 填充表格
        for i, sw in enumerate(self.software_data):
            tag = "odd" if i % 2 == 0 else "even"
            self.tree.insert("", tk.END, values=(
                sw["序号"],
                sw["名称"],
                sw["版本"],
                sw["发布者"],
                sw["安装日期"],
                sw["来源"]
            ), tags=(tag,))
        
        self.tree.tag_configure("odd", background=COLORS["table_row"])
        self.tree.tag_configure("even", background=COLORS["table_row_alt"])
        
        count = len(self.software_data)
        self.status_label.config(text="检测完成", fg=COLORS["success"])
        self.count_label.config(text=f"共 {count} 个软件")
        self.progress_label.config(text=f"检测完成，共发现 {count} 个软件")
        
        self.detect_btn.configure_state(True)
        self.detect_btn.text = "重新检测"
        self.detect_btn._draw(COLORS["primary"])
        
        self.export_btn.configure_state(True)
        self.export_zip_btn.configure_state(True)
        
        self.progress.stop()
        self.is_detecting = False
    
    def _on_detection_error(self, error_msg):
        """检测失败回调（主线程）"""
        messagebox.showerror("检测错误", f"检测过程中发生错误:\n{error_msg}")
        self.status_label.config(text="检测失败", fg=COLORS["danger"])
        self.progress_label.config(text="")
        
        self.detect_btn.configure_state(True)
        self.detect_btn.text = "开始检测"
        self.detect_btn._draw(COLORS["primary"])
        
        self.progress.stop()
        self.is_detecting = False
    
    def upload_data(self):
        """上传数据到服务器"""
        if not self.software_data:
            messagebox.showwarning("提示", "请先进行检测")
            return
        
        # 弹出输入对话框
        dialog = InputDialog(self.root)
        self.root.wait_window(dialog)
        
        if dialog.result is None:
            return
        
        dept, name = dialog.result
        
        # 在后台线程中上传
        self.detect_btn.configure_state(False)
        self.progress.start(15)
        self.progress_label.config(text="正在上传...")
        
        # 获取服务器地址
        server_addr = self.server_entry.get().strip()
        if not server_addr:
            server_addr = "localhost"
        # 去掉可能带的端口号和协议前缀
        server_addr = server_addr.replace("http://", "").replace("https://", "")
        server_addr = server_addr.split(":")[0]  # 去掉端口
        
        thread = threading.Thread(
            target=self._upload_thread,
            args=(dept, name, server_addr),
            daemon=True
        )
        thread.start()
    
    def _upload_thread(self, dept, name, server_addr):
        """后台线程执行上传"""
        try:
            # 准备上传数据
            upload_data = {
                'dept': dept,
                'name': name,
                'software_list': self.software_data
            }
            
            # 发送请求
            url = f'http://{server_addr}:5000/api/upload'
            data = json.dumps(upload_data).encode('utf-8')
            
            req = urllib.request.Request(
                url,
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
            
            self.root.after(0, self._upload_complete, result)
        
        except urllib.error.URLError as e:
            self.root.after(0, self._upload_error, f"无法连接服务器: {str(e)}")
        except Exception as e:
            self.root.after(0, self._upload_error, str(e))
    
    def _upload_complete(self, result):
        """上传完成回调"""
        self.progress.stop()
        self.detect_btn.configure_state(True)
        
        if result.get('success'):
            msg = (
                f"上传成功!\n\n"
                f"文件: {result.get('filename')}\n"
                f"软件数量: {result.get('count')} 个"
            )
            messagebox.showinfo("上传完成", msg)
            self.status_label.config(text="上传完成", fg=COLORS["success"])
            self.progress_label.config(text=f"已上传 {result.get('count')} 个软件")
        else:
            messagebox.showerror("上传失败", result.get('message', '未知错误'))
            self.status_label.config(text="上传失败", fg=COLORS["danger"])
            self.progress_label.config(text="")
    
    def _upload_error(self, error_msg):
        """上传失败回调"""
        self.progress.stop()
        self.detect_btn.configure_state(True)
        messagebox.showerror("上传错误", f"上传失败:\n{error_msg}")
        self.status_label.config(text="上传失败", fg=COLORS["danger"])
        self.progress_label.config(text="")
    
    def export_csv(self):
        """导出CSV"""
        if not self.software_data:
            messagebox.showwarning("提示", "请先进行检测")
            return
        
        # 弹出输入对话框
        dialog = InputDialog(self.root)
        self.root.wait_window(dialog)
        
        if dialog.result is None:
            return
        
        dept, name = dialog.result
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv")],
            initialfile=f"{dept}_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        if filepath:
            self._write_csv(filepath)
            messagebox.showinfo("导出成功", f"CSV文件已保存到:\n{filepath}")
    
    def _write_csv(self, filepath):
        """写入CSV"""
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=["序号", "名称", "版本", "发布者", "安装日期", "来源"])
            writer.writeheader()
            writer.writerows(self.software_data)
    
    def export_encrypted_zip(self):
        """导出ZIP到系统根目录"""
        if not self.software_data:
            messagebox.showwarning("提示", "请先进行检测")
            return
        
        # 弹出输入对话框
        dialog = InputDialog(self.root)
        self.root.wait_window(dialog)
        
        if dialog.result is None:
            return
        
        dept, name = dialog.result
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f"{dept}_{name}_{timestamp}.csv"
        zip_filename = f"{dept}_{name}_{timestamp}.zip"
        
        # 选择保存位置
        zip_path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP文件", "*.zip")],
            initialfile=zip_filename
        )
        
        if not zip_path:
            return
        
        temp_csv = os.path.join(os.environ.get("TEMP", "."), csv_filename)
        
        try:
            self._write_csv(temp_csv)
            
            # 使用pyzipper创建加密ZIP
            if HAS_PYZIPPER:
                with pyzipper.AESZipFile(zip_path, 'w', compression=pyzipper.ZIP_DEFLATED) as zf:
                    zf.setpassword(ZIP_PASSWORD.encode())
                    zf.setencryption(pyzipper.WZ_AES)
                    zf.write(temp_csv, csv_filename)
            else:
                # 回退到标准zipfile（无加密）
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    zf.write(temp_csv, csv_filename)
            
            os.remove(temp_csv)
            
            msg = (
                f"导出成功!\n\n"
                f"文件路径: {zip_path}\n\n"
                f"共检测到 {len(self.software_data)} 个软件"
            )
            messagebox.showinfo("导出完成", msg)
            self.status_label.config(text="导出完成", fg=COLORS["success"])
            self.progress_label.config(text=f"已导出到 {zip_path}")
            
        except Exception as e:
            messagebox.showerror("导出错误", f"导出失败:\n{str(e)}")
    
    def run(self):
        """运行应用"""
        self.root.mainloop()


def is_admin():
    """检查是否为管理员"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


if __name__ == "__main__":
    app = Application()
    
    if not is_admin():
        app.progress_label.config(text="提示: 建议以管理员身份运行以获取完整信息")
    
    app.run()
