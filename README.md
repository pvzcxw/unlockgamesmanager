# Steam入库文件管理器
![Python 3.7+](https://img.shields.io/badge/Python-3.7+-blue)

![License](https://img.shields.io/badge/License-MLP-green)

![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

Steam入库文件管理器是一个专为管理Steam解锁游戏设计的工具，支持SteamTools和GreenLuma两种入库方式。它提供了直观的界面来管理、编辑和配置您的入库文件，简化了入库游戏的管理流程。
功能亮点
🗂️ 多平台支持
SteamTools：管理.lua脚本文件

GreenLuma：管理.txt应用列表

入库助手：管理.o文件

🔍 智能管理
自动检测Steam安装路径

实时显示游戏状态（已入库/仅解锁）

游戏名称自动获取（支持中英文显示）

✨ 高级功能
语法高亮编辑器（支持Lua脚本）

批量删除入库文件及相关清单

强制添加/删除AppID解锁

清单版本管理（固定版/自动更新）

⚙️ 便捷操作
一键安装/运行游戏

在Steam库中查看游戏

文件浏览器中定位文件

刷新所有列表

安装与使用
前提条件
Python 3.7+

Windows系统（支持Steam）

安装依赖

pip install ttkbootstrap pygments tklinenums httpx

运行程序

python file_manager_gui.py

使用说明
主界面：

三个标签页分别显示SteamTools、GreenLuma和入库助手的文件

状态列显示文件状态：已入库/仅解锁/核心文件

支持按文件名、AppID或游戏名搜索

文件操作：

双击文件：安装/运行游戏

右键菜单：提供编辑、删除、定位等操作

顶部工具栏：刷新、查看/编辑、删除

高级功能：

设置：自定义Steam路径

强制解锁：手动添加/删除AppID

清单管理：切换固定版和自动更新模式

注意事项
首次运行时，程序会尝试自动检测Steam安装路径

如果自动检测失败，请在设置中手动指定Steam路径

编辑.o文件时需谨慎，可能导致文件损坏

删除操作不可逆，请确认后再执行

技术细节
前端：基于ttkbootstrap的现代化GUI界面

后端：异步获取游戏名称，提高响应速度

编辑器：支持Lua语法高亮和行号显示

智能缓存：减少Steam API请求次数

作者
pvzcxw
From Cai Install

许可证
本项目采用 MLP 许可证

提示：使用前请确保Steam客户端已关闭，部分操作需要以管理员权限运行程序以获得最佳体验。
