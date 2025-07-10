# file_manager_gui.py

import sys
import os
import re
import webbrowser
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog, simpledialog
from pathlib import Path
import subprocess
import threading
import asyncio
import queue
import shutil
import tempfile

try:
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *
except ImportError:
    print("错误: ttkbootstrap 库未安装。\n请使用 'pip install ttkbootstrap' 命令安装。")
    sys.exit(1)

try:
    from file_manager_backend import FileManagerBackend
except ImportError:
    print("错误: file_manager_backend.py 文件缺失。")
    sys.exit(1)

try:
    from pygments import lex
    from pygments.lexers.scripting import LuaLexer
    from tklinenums import TkLineNumbers
except ImportError:
    print("警告: pygments 或 tklinenums 库未安装。语法高亮功能将不可用。")
    print("请使用 'pip install pygments tklinenums' 命令安装。")
    lex = None

class CodeEditor(scrolledtext.ScrolledText):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lexer = LuaLexer()
        self.syntax_highlighting_tags = {
            'Token.Keyword': {'foreground': '#FF8800'},
            'Token.Keyword.Constant': {'foreground': '#FF8800'},
            'Token.Name.Function': {'foreground': '#56B6C2'},
            'Token.Operator': {'foreground': '#FF5555'},
            'Token.Comment': {'foreground': '#888888'},
            'Token.Literal.String': {'foreground': '#98C379'},
            'Token.Literal.Number': {'foreground': '#D19A66'},
            'Token.Punctuation': {'foreground': '#ABB2BF'},
            'Token.Name': {'foreground': '#ABB2BF'},
            'Token.Text': {'foreground': '#ABB2BF'},
        }
        self.config_tags()
        self.bind('<KeyRelease>', self.on_key_release)

    def config_tags(self):
        for token, style in self.syntax_highlighting_tags.items():
            self.tag_configure(str(token), **style)

    def on_key_release(self, event=None):
        self.highlight_syntax()
        
    def highlight_syntax(self, event=None):
        if not lex: return
        
        for tag in self.tag_names():
            if str(tag).startswith("Token"):
                self.tag_remove(tag, "1.0", "end")
        
        text_content = self.get('1.0', 'end-1c')
        # 使用一个简单的基于行的高亮策略，以提高性能
        # 每次只高亮当前行附近的几行
        current_line = int(self.index(tk.INSERT).split('.')[0])
        start_line = max(1, current_line - 10)
        end_line = current_line + 10

        start_index = f"{start_line}.0"
        end_index = f"{end_line}.0"

        # 获取需要高亮的文本块
        visible_text = self.get(start_index, end_index)
        
        # 为了正确计算偏移量，我们需要知道文本块的起始位置
        start_char_index = len(self.get("1.0", start_index))

        for token, content in lex(visible_text, self.lexer):
            # content 在 visible_text 中的起始位置
            token_start = visible_text.find(content)
            if token_start == -1: continue

            # 转换成整个文本框的索引
            start_tk_index_line = start_line + visible_text[:token_start].count('\n')
            start_tk_index_col = token_start - visible_text[:token_start].rfind('\n') -1

            # 如果没有换行符
            if visible_text[:token_start].rfind('\n') == -1:
                start_tk_index_col = token_start
            
            start = f"{start_tk_index_line}.{start_tk_index_col}"
            end = f"{start}+{len(content)}c"

            # 替换，防止下一次 find 找到同一个
            visible_text = visible_text.replace(content, ' ' * len(content), 1)

            self.tag_add(str(token), start, end)

class SimpleNotepad(tk.Toplevel):
    def __init__(self, parent, filename, content, file_path):
        super().__init__(parent)
        self.transient(parent); self.title(f"编辑文件 - {filename}"); self.file_path, self.filename = Path(file_path), filename
        self.geometry("800x600"); self.grab_set()
        
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=BOTH, expand=True)

        ttk.Label(main_frame, text=f"文件: {self.filename}", font=("", 11, 'bold')).pack(pady=(0, 10), anchor=W)
        
        editor_frame = ttk.Frame(main_frame)
        editor_frame.pack(fill=BOTH, expand=True)
        
        is_lua = filename.endswith(".lua") and lex is not None
        
        if is_lua:
            self.text_widget = CodeEditor(editor_frame, wrap=tk.WORD, font=("Consolas", 10),
                                          background="#282C34", insertbackground="white")
            linenumbers = TkLineNumbers(editor_frame, self.text_widget, justify='left', colors=("#6c757d", "#282c34"))
            linenumbers.pack(side='left', fill='y')
        else:
            self.text_widget = scrolledtext.ScrolledText(editor_frame, wrap=tk.WORD, font=("Consolas", 10))
        
        self.text_widget.pack(side='left', fill=BOTH, expand=True)
        self.text_widget.insert(tk.END, content)

        if is_lua:
            # 初始高亮整个文档
            self.after(100, self.initial_full_highlight)

        button_frame = ttk.Frame(main_frame, padding=(0, 15, 0, 0)); button_frame.pack(fill=X); button_frame.columnconfigure(0, weight=1)
        save_button = ttk.Button(button_frame, text="💾 保存", command=self.save_file, style='success.TButton'); save_button.grid(row=0, column=1, padx=(10, 0))
        close_button = ttk.Button(button_frame, text="❌ 关闭", command=self.destroy, style='danger.TButton'); close_button.grid(row=0, column=2, padx=10)
        self.protocol("WM_DELETE_WINDOW", self.destroy); self.wait_window(self)

    def initial_full_highlight(self):
        """为整个文档应用一次高亮"""
        self.text_widget.on_key_release = lambda e=None: None # 暂时禁用实时高亮以提高性能
        
        content = self.text_widget.get("1.0", "end-1c")
        start = "1.0"
        for token, text in lex(content, self.text_widget.lexer):
            end = self.text_widget.index(f"{start}+{len(text)}c")
            self.text_widget.tag_add(str(token), start, end)
            start = end
        
        self.text_widget.on_key_release = self.text_widget.highlight_syntax # 恢复实时高亮


    def save_file(self):
        try:
            with open(self.file_path, "w", encoding="utf-8", errors="ignore") as f: f.write(self.text_widget.get("1.0", tk.END))
            messagebox.showinfo("成功", f"文件 {self.filename} 已保存。", parent=self)
            self.master.refresh_file_lists()
        except Exception as e: messagebox.showerror("失败", f"保存文件失败: {e}", parent=self)


class DepotListDialog(tk.Toplevel):
    def __init__(self, parent, depot_data, filename):
        super().__init__(parent)
        self.transient(parent); self.title(f"Depot 列表 - {filename}"); self.geometry("800x400"); self.grab_set()
        main_frame = ttk.Frame(self, padding=15); main_frame.pack(fill=BOTH, expand=True)
        ttk.Label(main_frame, text=f"文件 '{filename}' 包含的 Depot 列表：", font=("", 11, 'bold')).pack(pady=(0, 10), anchor=W)
        text_widget = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=("Consolas", 10))
        text_widget.pack(fill=BOTH, expand=True)
        if not depot_data: text_widget.insert(tk.END, "未找到有效的 Depot 定义。")
        else:
            for depot_id, key in depot_data: text_widget.insert(tk.END, f"depot: {depot_id}\nkey:   {key}\n\n")
        text_widget.config(state='disabled')
        close_button = ttk.Button(main_frame, text="关闭", command=self.destroy, style='primary.TButton')
        close_button.pack(pady=(15, 0))
        self.protocol("WM_DELETE_WINDOW", self.destroy); self.wait_window(self)


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent; self.transient(parent); self.title("设置"); self.geometry("600x150"); self.grab_set()
        self.current_path = self.parent.backend.app_config.get("Custom_Steam_Path", "")
        self.path_var = tk.StringVar(value=self.current_path)
        self.create_widgets(); self.protocol("WM_DELETE_WINDOW", self.destroy); self.wait_window(self)

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=20); main_frame.pack(fill=BOTH, expand=True)
        path_frame = ttk.Frame(main_frame); path_frame.pack(fill=X, expand=True)
        ttk.Label(path_frame, text="自定义Steam路径:").pack(side=LEFT, padx=(0, 10))
        path_entry = ttk.Entry(path_frame, textvariable=self.path_var); path_entry.pack(side=LEFT, fill=X, expand=True)
        browse_button = ttk.Button(path_frame, text="浏览...", command=self.browse_path); browse_button.pack(side=LEFT, padx=(5, 0))
        ttk.Label(main_frame, text="留空则自动检测。需要选择Steam的根目录（包含steam.exe的文件夹）。", wraplength=550, justify=LEFT, style='secondary.TLabel').pack(pady=(5, 10), anchor=W)
        button_frame = ttk.Frame(main_frame); button_frame.pack(pady=(10, 0))
        save_button = ttk.Button(button_frame, text="保存并应用", command=self.save_and_close, style='success.TButton'); save_button.pack(side=LEFT, padx=10)
        cancel_button = ttk.Button(button_frame, text="取消", command=self.destroy); cancel_button.pack(side=LEFT, padx=10)

    def browse_path(self):
        directory = filedialog.askdirectory(title="选择Steam安装目录", initialdir=self.path_var.get() or "C:/")
        if directory: self.path_var.set(directory)

    def save_and_close(self):
        new_path = self.path_var.get().strip()
        if new_path and not (Path(new_path).exists() and Path(new_path, "steam.exe").exists()):
            messagebox.showerror("路径无效", "指定的路径不是一个有效的Steam安装目录。", parent=self); return
        self.parent.backend.app_config["Custom_Steam_Path"] = new_path
        try:
            self.parent.backend.save_config()
            messagebox.showinfo("成功", "设置已保存！将立即应用新路径。", parent=self)
            self.parent.initialize_app(); self.destroy()
        except Exception as e: messagebox.showerror("保存失败", f"无法保存配置文件：\n{e}", parent=self)


class FileManagerGUI(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly", title="cai入库文件管理器V2 1.3by pvzcxw")
        self.geometry("1100x700"); self.minsize(800, 450); self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.backend = FileManagerBackend()
        self.full_file_data = {"st": [], "gl": [], "assistant": []}
        self.list_view_data = {}; self.name_queue = queue.Queue(); self.fetcher_thread = None
        self.create_menu(); self.create_widgets()
        self.after(100, self.initialize_app); self.process_name_queue()

    def create_menu(self):
        menu_bar = ttk.Menu(self); self.config(menu=menu_bar)
        self.file_menu = ttk.Menu(menu_bar, tearoff=False); menu_bar.add_cascade(label="文件", menu=self.file_menu)
        self.file_menu.add_command(label="🔄 刷新所有列表", command=self.refresh_file_lists); self.file_menu.add_separator()
        self.file_menu.add_command(label="📂 打开插件目录 (ST/助手)", command=lambda: self.open_folder('st_assistant'))
        self.gl_folder_label = "📂 打开GreenLuma目录"; self.file_menu.add_command(label=self.gl_folder_label, command=lambda: self.open_folder('gl'), state="disabled")
        self.file_menu.add_separator(); self.file_menu.add_command(label="退出", command=self.on_closing)
        help_menu = ttk.Menu(menu_bar, tearoff=False); menu_bar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="关于", command=self.show_about_dialog)

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=15); main_frame.pack(fill=BOTH, expand=True)
        top_frame = ttk.Frame(main_frame); top_frame.pack(fill=X, pady=(0, 10))
        button_frame = ttk.Frame(top_frame); button_frame.pack(fill=X)
        settings_btn = ttk.Button(button_frame, text="⚙️ 设置", command=self.show_settings_dialog, style="primary.TButton"); settings_btn.pack(side=LEFT, padx=(0, 5))
        adv_menu_button = ttk.Menubutton(button_frame, text="🛠️ 高级", style="primary.Outline.TMenubutton"); adv_menu_button.pack(side=LEFT, padx=(0, 5))
        adv_menu = tk.Menu(adv_menu_button, tearoff=0)
        adv_menu.add_command(label="强制解锁AppID", command=lambda: self.manual_modify_unlock('add'))
        adv_menu.add_command(label="删除解锁AppID", command=lambda: self.manual_modify_unlock('remove'))
        adv_menu_button["menu"] = adv_menu
        refresh_btn = ttk.Button(button_frame, text="🔄 刷新", command=self.refresh_file_lists, style="info.TButton"); refresh_btn.pack(side=LEFT, expand=True, fill=X, padx=(0, 2))
        view_btn = ttk.Button(button_frame, text="📝 查看/编辑", command=self.view_selected_file, style="success.TButton"); view_btn.pack(side=LEFT, expand=True, fill=X, padx=2)
        delete_btn = ttk.Button(button_frame, text="🗑️ 删除", command=self.delete_selected_file, style="danger.TButton"); delete_btn.pack(side=LEFT, expand=True, fill=X, padx=(2, 0))
        search_frame = ttk.Frame(top_frame, padding=(0, 10, 0, 0)); search_frame.pack(fill=X, expand=True)
        ttk.Label(search_frame, text="🔍").pack(side=LEFT, padx=(0, 5))
        self.search_var = tk.StringVar(); self.search_var.trace_add("write", lambda *args: self.filter_list())
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var); self.search_entry.pack(side=LEFT, fill=X, expand=True)
        clear_button = ttk.Button(search_frame, text="清除", command=self.clear_search, style="light.TButton"); clear_button.pack(side=LEFT, padx=(5, 0))
        self.notebook = ttk.Notebook(main_frame); self.notebook.pack(fill=BOTH, expand=True, pady=(5,0))
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)
        self.st_tab = ttk.Frame(self.notebook, padding=10)
        self.st_file_list = self._create_treeview_in_frame(self.st_tab)
        self.notebook.add(self.st_tab, text="已入库文件 (SteamTools)")
        self.gl_tab = ttk.Frame(self.notebook, padding=10); self.gl_file_list = self._create_treeview_in_frame(self.gl_tab)
        self.assistant_tab = ttk.Frame(self.notebook, padding=10); self.assistant_file_list = self._create_treeview_in_frame(self.assistant_tab)
        self.status_bar = ttk.Label(self, text=" 正在初始化...", relief=SUNKEN, anchor=W, padding=5); self.status_bar.pack(side=BOTTOM, fill=X)
        
    def show_settings_dialog(self): SettingsDialog(self)

    def on_closing(self):
        print("正在关闭应用程序...")
        if self.fetcher_thread and self.fetcher_thread.is_alive(): print("后台任务仍在运行，等待其自然结束...")
        shutdown_thread = threading.Thread(target=lambda: asyncio.run(self.backend.close_client())); shutdown_thread.start()
        self.destroy()

    def process_name_queue(self):
        try:
            while not self.name_queue.empty():
                appid, game_name = self.name_queue.get_nowait()
                for key in self.full_file_data:
                    for item in self.full_file_data[key]:
                        if item['appid'] == appid: item['game_name'] = game_name
                if appid in self.list_view_data:
                    item_data = self.list_view_data[appid]
                    item_data['game_name'] = game_name
                    treeview, item_id = item_data['treeview'], item_data['item_id']
                    if treeview.exists(item_id):
                        values = self.format_treeview_values(item_data)
                        treeview.item(item_id, values=values)
        except queue.Empty: pass
        finally: self.after(200, self.process_name_queue)

    def _name_fetcher_worker(self):
        all_appids = {item['appid'] for key in self.full_file_data for item in self.full_file_data[key] if item['appid'].isdigit() and item['appid'] not in self.backend.name_cache}
        if not all_appids: return
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        async def fetch_all():
            tasks = [self.backend.fetch_game_name(appid) for appid in all_appids]
            results = await asyncio.gather(*tasks)
            for appid, name in zip(all_appids, results): self.name_queue.put((appid, name))
        try: loop.run_until_complete(fetch_all())
        finally: loop.close()

    def start_name_fetching_thread(self):
        if self.fetcher_thread and self.fetcher_thread.is_alive(): return
        self.fetcher_thread = threading.Thread(target=self._name_fetcher_worker, daemon=True); self.fetcher_thread.start()

    def _create_treeview_in_frame(self, parent_frame: ttk.Frame) -> ttk.Treeview:
        columns = ('status', 'filename', 'appid', 'game_name')
        tree = ttk.Treeview(parent_frame, columns=columns, show='headings', selectmode='extended')
        tree.heading('status', text='状态', anchor='w'); tree.heading('filename', text='文件名', anchor='w')
        tree.heading('appid', text='AppID', anchor='w'); tree.heading('game_name', text='游戏名', anchor='w')
        tree.column('status', width=80, stretch=False, anchor='w'); tree.column('filename', width=250, stretch=False, anchor='w')
        tree.column('appid', width=120, stretch=False, anchor='w'); tree.column('game_name', width=400, anchor='w')
        scrollbar = ttk.Scrollbar(parent_frame, orient=VERTICAL, command=tree.yview); tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=RIGHT, fill=Y); tree.pack(side=LEFT, fill=BOTH, expand=True)
        tree.tag_configure("UNLOCKED_ONLY", foreground=self.style.colors.warning)
        tree.tag_configure("CORE_FILE", foreground=self.style.colors.info)
        tree.bind("<Button-3>", self.show_file_context_menu); tree.bind("<Double-Button-1>", lambda e: self.install_game())
        return tree

    def initialize_app(self):
        self.backend.load_config()
        steam_path = self.backend.detect_steam_path()
        if not steam_path or not steam_path.exists():
            self.status_bar.config(text="❌ 未找到Steam路径！请在“设置”中指定。")
            if not self.backend.app_config.get("Custom_Steam_Path"): messagebox.showwarning("未找到Steam", "无法自动检测到Steam路径。\n请点击“设置”按钮手动指定。")
        else: self.status_bar.config(text=f"✅ Steam路径: {steam_path}")
        self.refresh_file_lists()

    def get_active_context(self) -> tuple[ttk.Treeview | None, Path | None, str]:
        try:
            current_tab_index = self.notebook.index('current')
            tab_text = self.notebook.tab(current_tab_index, "text")
            if "SteamTools" in tab_text: return self.st_file_list, self.backend.get_steamtools_plugin_path(), "st"
            elif "GreenLuma" in tab_text: return self.gl_file_list, self.backend.get_greenluma_applist_path(), "gl"
            elif "入库助手" in tab_text: return self.assistant_file_list, self.backend.get_steamtools_plugin_path(), "assistant"
        except tk.TclError: pass
        return None, None, ""

    def refresh_file_lists(self):
        for key in self.full_file_data: self.full_file_data[key].clear()
        self._load_data_from_disk_st()
        assistant_files_found = self._load_data_from_disk("assistant", self.backend.get_steamtools_plugin_path(), ".o")
        gl_files_found = self._load_data_from_disk("gl", self.backend.get_greenluma_applist_path(), ".txt")
        self._toggle_tab(self.assistant_tab, "已入库文件 (入库助手)", assistant_files_found)
        self._toggle_tab(self.gl_tab, "已入库文件 (GreenLuma)", gl_files_found)
        if self.file_menu: self.file_menu.entryconfig(self.gl_folder_label, state="normal" if gl_files_found else "disabled")
        self.filter_list(); self.start_name_fetching_thread()
        
    def format_treeview_values(self, data_item):
        status_map = {'unlocked_only': "仅解锁", 'core_file': "仅解锁储存lua", 'ok': "已入库"}
        status_text = status_map.get(data_item.get('status'), "")
        return (status_text, data_item.get('filename', 'N/A'), data_item.get('appid', 'N/A'), data_item.get('game_name', 'Loading...'))

    def filter_list(self):
        treeview, _, list_type = self.get_active_context()
        if not list_type: return
        search_term = self.search_var.get().lower()
        source_data = self.full_file_data[list_type]
        treeview.delete(*treeview.get_children()); self.list_view_data.clear()
        if not source_data:
            treeview.insert("", tk.END, values=("", " (列表为空)", "", "")); return
        for data_item in source_data:
            filename, appid, game_name = data_item.get('filename', ''), data_item.get('appid', ''), data_item.get('game_name', '')
            if search_term in filename.lower() or search_term in appid.lower() or search_term in game_name.lower():
                values = self.format_treeview_values(data_item)
                item_id = appid if list_type == 'st' and appid != "N/A" else filename
                tags = ()
                status = data_item.get('status')
                if status == 'unlocked_only': tags = ("UNLOCKED_ONLY",)
                elif status == 'core_file': tags = ("CORE_FILE",)
                treeview.insert("", tk.END, iid=item_id, values=values, tags=tags)
                if appid.isdigit(): self.list_view_data[appid] = {'treeview': treeview, 'item_id': item_id, **data_item}
                
    def clear_search(self): self.search_var.set("")
    def on_tab_change(self, event): self.filter_list()

    def _toggle_tab(self, tab: ttk.Frame, text: str, should_be_visible: bool):
        is_visible = tab in self.notebook.tabs()
        if should_be_visible and not is_visible: self.notebook.add(tab, text=text)
        elif not should_be_visible and is_visible: self.notebook.forget(tab)

    def _extract_st_appid(self, file_path: Path) -> str:
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            match = re.search(r'addappid\s*\(\s*(\d+)', content)
            return match.group(1) if match else "N/A"
        except Exception: return "ReadError"
    
    def _load_data_from_disk_st(self):
        directory = self.backend.get_steamtools_plugin_path()
        if not directory or not directory.exists():
            self.full_file_data['st'] = []
            return False

        loaded_data = []
        file_data_map = {}  # Maps appid -> data dictionary

        # 1. Process all .lua files first. Their existence means 'Normal' status.
        try:
            lua_files = [f for f in os.listdir(directory) if f.endswith(".lua") and f != "steamtools.lua"]
            for filename in lua_files:
                appid = self._extract_st_appid(directory / filename)
                if appid.isdigit():
                    # We found a file, so it's 'ok' (Normal).
                    file_data_map[appid] = {
                        "filename": filename,
                        "appid": appid,
                        "game_name": self.backend.name_cache.get(appid, "Loading..."),
                        "status": "ok"
                    }
        except Exception as e:
            messagebox.showerror("错误", f"读取stplug-in目录失败: {e}")

        # 2. Process steamtools.lua for 'Unlocked Only' entries and the core file itself.
        st_lua_path = directory / "steamtools.lua"
        if st_lua_path.exists():
            # Add the core file entry first.
            loaded_data.append({
                "filename": "steamtools.lua",
                "appid": "N/A",
                "game_name": "SteamTools Core File",
                "status": "core_file"
            })
            try:
                content = st_lua_path.read_text(encoding='utf-8', errors='ignore')
                unlocked_appids = set(re.findall(r'addappid\s*\(\s*(\d+)\s*,\s*1\s*\)', content))

                # 3. Find appids that are unlocked but have no corresponding .lua file.
                for appid in unlocked_appids:
                    if appid not in file_data_map:
                        # This is an 'Unlocked Only' case.
                        file_data_map[appid] = {
                            "filename": f"缺少 {appid}.lua",
                            "appid": appid,
                            "game_name": self.backend.name_cache.get(appid, "Loading..."),
                            "status": "unlocked_only"
                        }
            except Exception as e:
                messagebox.showerror("错误", f"读取 steamtools.lua 失败: {e}")

        # 4. Combine and sort the final list.
        # Start with the core file (already in loaded_data)
        # Then add all other items from our map, sorted by appid.
        all_items = sorted(file_data_map.values(), key=lambda item: int(item['appid']), reverse=True)
        loaded_data.extend(all_items)

        self.full_file_data['st'] = loaded_data
        return True

    def _load_data_from_disk(self, list_type: str, directory: Path | None, extension: str) -> bool:
        if list_type == 'st': return self._load_data_from_disk_st()
        if not directory or not directory.exists(): self.full_file_data[list_type] = []; return False
        try:
            files = sorted([f for f in os.listdir(directory) if f.endswith(extension)], key=lambda f: (directory / f).stat().st_mtime, reverse=True)
            if not files: self.full_file_data[list_type] = []; return False
            loaded_data = []
            for filename in files:
                appid = Path(filename).stem; game_name = self.backend.name_cache.get(appid, "Loading...")
                loaded_data.append({"filename": filename, "appid": appid, "game_name": game_name, "status": "ok"})
            self.full_file_data[list_type] = loaded_data; return True
        except Exception as e:
            messagebox.showerror("读取错误", f"读取目录 {directory} 时发生错误:\n{e}")
            self.full_file_data[list_type] = []; return False

    def get_selected_data_items(self) -> list[dict]:
        treeview, _, list_type = self.get_active_context()
        if not treeview: return []
        selected_iids = treeview.selection()
        source_data = self.full_file_data[list_type]
        if list_type == 'st': return [item for item in source_data if (item['appid'] in selected_iids or item['filename'] in selected_iids)]
        else: return [item for item in source_data if item['filename'] in selected_iids]

    def delete_selected_file(self):
        _, directory, list_type = self.get_active_context()
        selected_items = self.get_selected_data_items()
        if not selected_items: messagebox.showinfo("提示", "请先在列表中选择要删除的条目。", parent=self); return
        if not directory and any(item.get('status') != 'unlocked_only' for item in selected_items): return
        st_warning = "\n\n对于SteamTools条目，其关联的脚本文件、清单文件以及解锁条目都将被彻底删除。" if list_type == 'st' else ""
        msg = f"确定要删除这 {len(selected_items)} 个条目吗？\n此操作不可恢复！{st_warning}"
        if not messagebox.askyesno("确认删除", msg, parent=self): return
        deleted_count, failed_files, manifests_deleted_count, unlocked_removed_count = 0, [], 0, 0
        depotcache_path = self.backend.steam_path / 'config' / 'depotcache'
        for item in selected_items:
            filename = item.get('filename')
            if filename and "缺少" not in filename:
                try:
                    file_path = directory / filename
                    if file_path.exists():
                        if list_type == 'st' and item.get('status') != 'core_file':
                            try:
                                content = file_path.read_text(encoding='utf-8', errors='ignore')
                                gids = re.findall(r'setManifestid\s*\(\s*\d+\s*,\s*"(\d+)"\s*\)', content)
                                if gids and depotcache_path.exists():
                                    for gid in gids:
                                        for mf in depotcache_path.glob(f'*_{gid}.manifest'):
                                            if mf.exists(): os.remove(mf); manifests_deleted_count += 1
                            except Exception as e: failed_files.append(f"{filename} (清单清理失败: {e})")
                        os.remove(file_path); deleted_count += 1
                except Exception as e: failed_files.append(f"{filename} (删除文件时出错: {e})")
            if list_type == 'st' and item.get('status') != 'core_file':
                if self._modify_st_lua(item['appid'], 'remove', show_feedback=False): unlocked_removed_count += 1
        success_msg = f"成功处理 {len(selected_items)} 个条目。"
        if deleted_count > 0: success_msg += f"\n- 删除了 {deleted_count} 个文件。"
        if unlocked_removed_count > 0: success_msg += f"\n- 移除了 {unlocked_removed_count} 个解锁条目。"
        if manifests_deleted_count > 0: success_msg += f"\n- 清除了 {manifests_deleted_count} 个关联清单。"
        success_msg += "\n\n请重启Steam生效。"
        if deleted_count > 0 or unlocked_removed_count > 0:
            messagebox.showinfo("操作完成", success_msg, parent=self); self.refresh_file_lists()
        if failed_files: messagebox.showwarning("部分失败", "以下文件处理失败:\n" + "\n".join(failed_files), parent=self)

    def view_selected_file(self):
        selected_items = self.get_selected_data_items()
        if not selected_items: messagebox.showinfo("提示", "请选择一个文件进行查看或编辑。", parent=self); return
        if len(selected_items) > 1: messagebox.showinfo("提示", "一次只能编辑一个文件。", parent=self); return
        item = selected_items[0]; filename = item.get('filename')
        if not filename or "缺少" in filename: messagebox.showerror("错误", "此条目没有关联的物理文件可供编辑。", parent=self); return
        _, directory, _ = self.get_active_context()
        if not directory: return
        if filename.endswith(".o"): messagebox.showwarning("注意", ".o 是二进制文件，用文本编辑器打开和保存可能会损坏文件！", parent=self)
        try:
            file_path = directory / filename
            if file_path.exists():
                with open(file_path, "rb") as f_bin: content = f_bin.read().decode('utf-8', errors='ignore')
                SimpleNotepad(self, filename, content, str(file_path))
            else: messagebox.showerror("错误", f"文件 '{filename}' 已不存在。", parent=self); self.refresh_file_lists()
        except Exception as e: messagebox.showerror("读取错误", f"读取文件失败: {e}", parent=self)

    def check_depot_list(self, item: dict):
        filename = item.get('filename')
        if not filename or "缺少" in filename: messagebox.showerror("错误", "没有可供检查的LUA文件。", parent=self); return
        _, directory, _ = self.get_active_context();
        if not directory: return
        file_path = directory / filename
        if not file_path.exists(): messagebox.showerror("错误", f"文件 '{filename}' 不存在。", parent=self); return
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            pattern = re.compile(r'addappid\s*\(\s*(\d+)\s*,\s*\d+\s*,\s*"([a-fA-F0-9]{64})"\s*\)')
            DepotListDialog(self, pattern.findall(content), filename)
        except Exception as e: messagebox.showerror("解析失败", f"读取或解析文件时出错: {e}", parent=self)

    def toggle_manifest_version(self, item: dict, to_fixed: bool):
        filename = item.get('filename')
        if not filename or "缺少" in filename: messagebox.showerror("错误", "没有可供操作的LUA文件。", parent=self); return
        _, directory, _ = self.get_active_context();
        if not directory: return
        file_path = directory / filename
        if not file_path.exists(): messagebox.showerror("错误", f"文件 '{filename}' 不存在。", parent=self); return
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            if to_fixed:
                new_content = re.sub(r'--\s*(setManifestid\s*\()', r'\1', content); action_text = "固定版本"
            else:
                new_content = re.sub(r'^(setManifestid\s*\()', r'--\1', content, flags=re.MULTILINE); action_text = "自动更新"
            if content == new_content: messagebox.showinfo("无变化", "文件内容无需更改。", parent=self); return
            file_path.write_text(new_content, encoding='utf-8')
            messagebox.showinfo("成功", f"文件 '{filename}' 已成功转换为 {action_text} 模式。", parent=self)
            self.refresh_file_lists()
        except Exception as e: messagebox.showerror("操作失败", f"处理文件时出错: {e}", parent=self)

    def manual_modify_unlock(self, action: str):
        title = "强制解锁AppID" if action == 'add' else "删除解锁AppID"
        prompt = "请输入要强制解锁的AppID:" if action == 'add' else "请输入要删除解锁的AppID:"
        appid = simpledialog.askstring(title, prompt, parent=self)
        if appid and appid.isdigit():
            self._modify_st_lua(appid, action)
        elif appid:
            messagebox.showerror("输入无效", "请输入一个有效的数字AppID。", parent=self)

    def _modify_st_lua(self, appid: str, action: str, show_feedback=True) -> bool:
        st_dir = self.backend.get_steamtools_plugin_path()
        if not st_dir:
            if show_feedback: messagebox.showerror("错误", "无法找到SteamTools插件目录。")
            return False
        st_lua_path = st_dir / "steamtools.lua"
        try:
            st_dir.mkdir(parents=True, exist_ok=True)
            content = st_lua_path.read_text(encoding='utf-8', errors='ignore') if st_lua_path.exists() else ""
            unlock_line = f'addappid({appid}, 1)'
            check_pattern = re.compile(r'^\s*' + re.escape(unlock_line) + r'\s*$', re.MULTILINE)
            if action == 'add':
                if check_pattern.search(content):
                    if show_feedback: messagebox.showinfo("提示", "此游戏已经解锁。", parent=self)
                    return False
                new_content = content.strip() + (f"\n{unlock_line}\n" if content.strip() else f"{unlock_line}\n")
            elif action == 'remove':
                new_content, count = check_pattern.subn('', content)
                if count == 0:
                    if show_feedback: messagebox.showinfo("提示", "未找到该游戏的解锁条目。", parent=self)
                    return False
                new_content = "\n".join(line for line in new_content.splitlines() if line.strip())
                if new_content: new_content += "\n"
            else: return False
            with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', dir=st_dir, suffix='.tmp') as temp_f:
                temp_f.write(new_content); temp_path = temp_f.name
            shutil.move(temp_path, st_lua_path)
            if show_feedback:
                if action == 'add': messagebox.showinfo("成功", f"AppID {appid} 已成功解锁。", parent=self)
                elif action == 'remove': messagebox.showinfo("成功", f"AppID {appid} 的解锁条目已移除。", parent=self)
            self.refresh_file_lists()
            return True
        except (IOError, OSError, PermissionError) as e:
            if show_feedback: messagebox.showerror("文件操作失败", f"无法修改 steamtools.lua: {e}\n\n请尝试以管理员身份运行本程序。")
        except Exception as e:
            if show_feedback: messagebox.showerror("未知错误", f"修改 steamtools.lua 时发生未知错误: {e}")
        return False

    def install_game(self, item: dict | None = None):
        if not item:
            selected_items = self.get_selected_data_items()
            item = selected_items[0] if selected_items else None
        if not item: return
        appid = item.get('appid')
        if appid and appid.isdigit(): webbrowser.open(f"steam://install/{appid}")
        else: messagebox.showinfo("提示", f"条目 '{item.get('filename')}' 没有有效的AppID可供安装。", parent=self)

    def show_file_context_menu(self, event):
        treeview, _, list_type = self.get_active_context()
        if not treeview: return
        iid = treeview.identify_row(event.y)
        if iid:
            if iid not in treeview.selection():
                treeview.selection_set(iid)
        else: return
        selected_items = self.get_selected_data_items()
        if not selected_items: return
        menu = tk.Menu(self, tearoff=0)
        if len(selected_items) == 1:
            item = selected_items[0]
            filename, appid, status = item.get('filename'), item.get('appid'), item.get('status')
            if appid and appid.isdigit():
                menu.add_command(label=f"🚀 运行/安装此游戏 ({appid})", command=lambda i=item: self.install_game(i))
                menu.add_command(label=f"📚 在Steam库中查看", command=lambda i=item: self.view_in_steam_library(i))
            if filename and "缺少" not in filename:
                menu.add_command(label="📁 在文件浏览器中定位", command=lambda: self.locate_file(filename))
                menu.add_separator(); menu.add_command(label="📝 编辑文件", command=self.view_selected_file)
            if list_type == 'st' and status != 'core_file':
                menu.add_separator()
                if status == 'unlocked_only':
                    # --- MODIFIED: Removed the non-functional "Create File" option ---
                    menu.add_command(label="🗑️ 删除解锁", command=lambda a=appid: self._modify_st_lua(a, 'remove'))
                
                if filename and "缺少" not in filename:
                    menu.add_command(label="📊 检查Depot列表", command=lambda i=item: self.check_depot_list(i))
                    try:
                        _, directory, _ = self.get_active_context()
                        if directory and (directory / filename).exists():
                            content = (directory / filename).read_text(encoding='utf-8', errors='ignore')
                            manifest_lines = re.findall(r'(--)?\s*setManifestid\(.*?\)', content)
                            if manifest_lines:
                                all_commented = all(line.strip().startswith('--') for line in manifest_lines)
                                if all_commented: menu.add_command(label="✅ 转换为固定版本", command=lambda i=item: self.toggle_manifest_version(i, to_fixed=True))
                                else: menu.add_command(label="🔄 转换为自动更新", command=lambda i=item: self.toggle_manifest_version(i, to_fixed=False))
                    except Exception as e: print(f"检查版本模式时出错: {e}")
        menu.add_command(label=f"🗑️ 删除 {len(selected_items)} 个条目", command=self.delete_selected_file)
        menu.add_separator(); menu.add_command(label="🔄 刷新列表", command=self.refresh_file_lists)
        menu.tk_popup(event.x_root, event.y_root)

    def locate_file(self, filename: str):
        _, directory, _ = self.get_active_context()
        if not directory: return
        file_path = str(directory / filename)
        if os.path.exists(file_path): subprocess.run(['explorer', '/select,', file_path])
        else: messagebox.showerror("错误", "文件不存在。", parent=self); self.refresh_file_lists()

    def open_folder(self, folder_type: str):
        path = None
        if folder_type == 'st_assistant': path = self.backend.get_steamtools_plugin_path()
        elif folder_type == 'gl': path = self.backend.get_greenluma_applist_path()
        if path and path.exists(): os.startfile(path)
        else: messagebox.showerror("错误", "无法定位文件夹，它可能不存在。", parent=self)

    def view_in_steam_library(self, item: dict | None = None):
        if not item:
            selected_items = self.get_selected_data_items()
            item = selected_items[0] if selected_items else None
        if not item: return
        appid = item.get('appid')
        if appid and appid.isdigit(): webbrowser.open(f"steam://nav/games/details/{appid}")
        else: messagebox.showinfo("提示", f"条目 '{item.get('filename')}' 没有有效的AppID。", parent=self)

    def show_about_dialog(self):
        messagebox.showinfo("关于", "cai入库文件管理器V2 1.3by pvzcxw\n\n"
                            "一个用于管理steam入库游戏的工具。\n"
                            "From Cai Install。\n\n"
                            "作者: pvzcxw", parent=self)


if __name__ == '__main__':
    try:
        from ctypes import windll; windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    app = FileManagerGUI()
    app.mainloop()