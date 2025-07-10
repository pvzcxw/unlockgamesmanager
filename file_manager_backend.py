# file_manager_backend.py

import os
import json
import winreg
import traceback
from pathlib import Path
import asyncio
import httpx
from typing import Dict

# 默认配置，确保即使没有config.json也能运行
DEFAULT_CONFIG = {
    "Github_Personal_Token": "",
    "Custom_Steam_Path": "",
    "steamtools_only_lua": False,
}

class FileManagerBackend:
    """
    一个精简的后端，为文件管理器服务。
    包含配置、路径、以及异步获取游戏名称的功能。
    """
    def __init__(self):
        self.app_config = {}
        self.steam_path = Path()
        self.name_cache: Dict[str, str] = {}  # 游戏名称缓存
        self.client = httpx.AsyncClient(timeout=10) # 复用HTTP客户端
        self.load_config()

    async def close_client(self):
        """安全关闭HTTP客户端。"""
        await self.client.aclose()
        self._log_info("HTTP客户端已关闭。")

    def _log_error(self, message: str):
        print(f"[ERROR] {message}")
        print(''.join(traceback.format_exc()))

    def _log_info(self, message: str):
        print(f"[INFO] {message}")
    
    def get_config_path(self) -> Path:
        return Path('./config.json')

    def load_config(self):
        config_path = self.get_config_path()
        if not config_path.exists():
            self._log_info('未找到 config.json，将使用默认设置和注册表检测。')
            self.app_config = DEFAULT_CONFIG.copy()
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded_config = json.load(f)
            self.app_config = DEFAULT_CONFIG.copy()
            self.app_config.update(loaded_config)
            self._log_info('成功加载 config.json。')
        except Exception as e:
            self._log_error(f"配置文件加载失败，将使用默认值: {e}")
            self.app_config = DEFAULT_CONFIG.copy()

    def save_config(self):
        try:
            with open(self.get_config_path(), "w", encoding="utf-8") as f:
                json.dump(self.app_config, f, indent=2, ensure_ascii=False)
            self._log_info("配置已成功保存。")
        except Exception as e:
            self._log_error(f"保存配置失败: {e}")
            raise

    async def fetch_game_name(self, appid: str) -> str:
        """异步获取游戏名称，并使用缓存。"""
        if not appid or not appid.isdigit():
            return "Invalid AppID"
        
        # 1. 检查缓存
        if appid in self.name_cache:
            return self.name_cache[appid]

        # 2. 如果缓存中没有，则请求API
        url = f"https://steamui.com/api/loadGames.php?page=1&search={appid}&sort=update"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            
            # 3. 解析JSON并找到匹配的游戏
            games = data.get('games', [])
            game_data = next((game for game in games if str(game.get('appid')) == appid), None)
            
            if game_data:
                eng_name = game_data.get('name')
                cn_name = game_data.get('schinese_name')
                
                if eng_name and cn_name:
                    formatted_name = f"{eng_name} | {cn_name}"
                elif eng_name:
                    formatted_name = eng_name
                elif cn_name:
                    formatted_name = cn_name
                else:
                    formatted_name = "Name N/A"
            else:
                formatted_name = "Name Not Found"
                
            # 4. 存入缓存并返回
            self.name_cache[appid] = formatted_name
            return formatted_name

        except Exception as e:
            self._log_error(f"获取AppID {appid} 的名称失败: {e}")
            # 缓存错误信息，避免重复请求失败的ID
            error_msg = "Fetch Error"
            self.name_cache[appid] = error_msg
            return error_msg

    def detect_steam_path(self) -> Path:
        try:
            custom_path = self.app_config.get("Custom_Steam_Path", "").strip()
            if custom_path and Path(custom_path).exists() and Path(custom_path, 'steam.exe').exists():
                self.steam_path = Path(custom_path)
                self._log_info(f"使用自定义Steam路径: {self.steam_path}")
                return self.steam_path
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam')
            steam_path_str, _ = winreg.QueryValueEx(key, 'SteamPath')
            self.steam_path = Path(steam_path_str)
            self._log_info(f"自动检测到Steam路径: {self.steam_path}")
            return self.steam_path
        except Exception:
            self._log_error('Steam路径获取失败。')
            self.steam_path = Path()
            return self.steam_path

    def get_steamtools_plugin_path(self) -> Path | None:
        return self.steam_path / "config" / "stplug-in" if self.steam_path.exists() else None

    def get_greenluma_applist_path(self) -> Path | None:
        return self.steam_path / "AppList" if self.steam_path.exists() else None