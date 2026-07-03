# -
本工具用于检测Windows系统中已安装的软件，支持多种检测方式，确保结果全面准确。
# 已安装软件检测工具

## 项目结构

```
G:\CODE\
├── installed_software_detector.py  # 前端主程序
├── build.bat                       # 前端打包脚本
└── backend/
    ├── server_gui.py               # 后端服务程序
    ├── app.py                      # Flask API（备用）
    ├── build.bat                   # 后端打包脚本
    ├── start.bat                   # 直接运行脚本
    └── uploads/                    # 上传文件目录
```

## 功能说明

本工具用于检测Windows系统中已安装的软件，支持多种检测方式，确保结果全面准确。

### 检测方式

| 方式 | 说明 |
|------|------|
| 注册表 | 读取系统注册表中的卸载信息（支持32位/64位程序） |
| WMI | 通过Windows管理规范获取软件信息 |
| PowerShell | 使用Get-Package命令获取 |
| WinGet | 通过winget list获取已安装程序 |

### 界面功能

| 按钮 | 功能 |
|------|------|
| 开始检测 | 执行软件检测 |
| 上传 | 将检测结果上传到服务器 |
| 打包导出 | 生成加密ZIP文件保存到指定位置 |

## 使用方法

### 方法一：直接运行Python脚本

```bash
python installed_software_detector.py
```

### 方法二：打包成EXE（推荐）

1. 确保已安装Python 3.8+
2. 双击运行 `build.bat`
3. 等待打包完成
4. 在 `dist` 文件夹中找到 `SoftwareDetector.exe`

## 上传功能

### 启动后端服务

1. 进入 `backend` 目录
2. 双击 `BackendServer.exe` 或运行 `python server_gui.py`
3. 点击播放按钮启动服务
4. 记录显示的IP地址

### 使用前端上传

1. 运行前端程序
2. 在"服务器"输入框填入后端IP地址（如 `192.168.1.100`）
3. 点击"开始检测"
4. 检测完成后点击"上传"
5. 输入部门和姓名，确认上传

### API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/upload` | POST | 上传软件检测数据 |
| `/api/health` | GET | 健康检查 |

## 导出说明

### 导出流程

1. 点击"上传"或"打包导出"按钮
2. 弹出输入框，填写**部门**和**姓名**
3. 上传到服务器或选择保存位置

### 文件命名格式

- CSV文件：`部门_姓名_时间戳.csv`
- ZIP文件：`部门_姓名_时间戳.zip`

### ZIP加密

- 密码：`123456`

## 系统要求

- Windows 10/11
- Python 3.8+（如需打包）
- 管理员权限（推荐）

## 依赖安装

```bash
pip install pyzipper flask flask-cors
```
