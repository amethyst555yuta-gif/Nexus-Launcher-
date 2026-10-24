import builtins
import logging
from logging.handlers import RotatingFileHandler
import os
import urllib.request
import json
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import threading
import zipfile

# --- 1. HỆ THỐNG LOG ---
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE_PATH = os.path.join(CURRENT_SCRIPT_DIR, 'launcher.log')

logger = logging.getLogger("MinecraftLauncher")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('[%(asctime)s] [%(levelname)s]: %(message)s', '%d-%m-%Y %H:%M:%S')

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler = RotatingFileHandler(LOG_FILE_PATH, maxBytes=2*1024*1024, backupCount=3, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

logger.info("Đang khởi động hệ thống lõi NEXUS Launcher...")

# --- 2. QUẢN LÝ THƯ MỤC GAME ĐỘNG (CUSTOM STORAGE PATH) ---
DEFAULT_BASE_DIR = os.path.join(CURRENT_SCRIPT_DIR, ".minecraft_custom")
GLOBAL_CONFIG_PATH = os.path.join(CURRENT_SCRIPT_DIR, "nexus_global_settings.json")

def get_game_directories():
    """Xác định vị trí lưu trữ game do người dùng tùy biến"""
    base_dir = DEFAULT_BASE_DIR
    if os.path.exists(GLOBAL_CONFIG_PATH):
        try:
            with open(GLOBAL_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                custom_path = data.get("custom_game_dir", "")
                if custom_path and os.path.exists(custom_path):
                    base_dir = custom_path
        except builtins.Exception:
            pass
            
    instances_dir = os.path.join(base_dir, "instances")
    assets_dir = os.path.join(base_dir, "assets")
    config_file_path = os.path.join(base_dir, "launcher_config.json")
    
    for p in [instances_dir, assets_dir]:
        if not os.path.exists(p):
            os.makedirs(p)
            
    return base_dir, instances_dir, assets_dir, config_file_path

# Khởi tạo các biến đường dẫn toàn cục
BASE_DIR, INSTANCES_DIR, ASSETS_DIR, CONFIG_FILE_PATH = get_game_directories()

# --- 3. HỆ THỐNG ĐỌC CẤU HÌNH NGƯỜI DÙNG ---
def load_launcher_config():
    _, _, _, config_path = get_game_directories()
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Lỗi nạp tệp JSON cấu hình: {e}")
    return {"last_version": "1.20.1", "allocated_ram": 2, "instances": {}}

def save_launcher_config(config_data):
    _, _, _, config_path = get_game_directories()
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Lỗi lưu cấu hình: {e}")

def update_instance_data(version_id, username, java_path, ram_gb):
    config = load_launcher_config()
    config["last_version"] = version_id
    config["allocated_ram"] = ram_gb
    if "instances" not in config:
        config["instances"] = {}
    config["instances"][version_id] = {
        "username": username,
        "java_path": java_path
    }
    save_launcher_config(config)
# --- 4. TIẾN TRÌNH TẢI TÀI NGUYÊN GAME SẠCH TỪ MOJANG ---
def download_instance_assets(version_id):
    current_base, current_instances, current_assets, _ = get_game_directories()
    logger.info(f"=== TIẾN TRÌNH XỬ LÝ INSTANCE: {version_id} ===")
    
    instance_path = os.path.join(current_instances, f"instance_{version_id}")
    lib_dir = os.path.join(instance_path, "libraries")
    natives_dir = os.path.join(instance_path, "natives")
    
    for p in [instance_path, lib_dir, natives_dir]:
        if not os.path.exists(p):
            os.makedirs(p)
            
    json_path = os.path.join(instance_path, f"{version_id}.json")
    client_jar_path = os.path.join(instance_path, f"{version_id}.jar")
    
    version_manifest_url = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
    manifest_cache = os.path.join(current_base, "version_manifest.json")
    
    if not os.path.exists(manifest_cache):
        try:
            with urllib.request.urlopen(version_manifest_url, timeout=10) as response:
                manifest_content = response.read()
            with open(manifest_cache, 'wb') as f:
                f.write(manifest_content)
        except Exception as e:
            logger.error(f"Không thể tải danh mục Mojang: {e}")
            return None

    with open(manifest_cache, 'r', encoding='utf-8') as f:
        manifest_data = json.load(f)
    
    version_url = None
    for v in manifest_data.get('versions', []):
        if v.get('id') == version_id:
            version_url = v.get('url')
            break
            
    if not version_url:
        return None

    if not os.path.exists(json_path):
        try:
            with urllib.request.urlopen(version_url, timeout=10) as response:
                json_content = response.read()
            with open(json_path, 'wb') as f:
                f.write(json_content)
        except Exception as e:
            logger.error(f"Lỗi tải cấu hình JSON: {e}")
            return None

    with open(json_path, 'r', encoding='utf-8') as f:
        version_data = json.load(f)

    # TỰ ĐỘNG PHÂN TÍCH VÀ ĐỒNG BỘ CHỈ MỤC ASSETS (ĐÃ FIX LỖI ĐỌC SAI ID CHUỖI)
    asset_info = version_data.get('assetIndex', {})
    if asset_info:
        asset_id = str(asset_info.get('id', 'legacy'))
        asset_url = asset_info.get('url')
        index_dir = os.path.join(current_assets, "indexes")
        objects_dir = os.path.join(current_assets, "objects")
        
        for p in [index_dir, objects_dir]:
            if not os.path.exists(p):
                os.makedirs(p)
                
        target_index_path = os.path.join(index_dir, f"{asset_id}.json")
        
        if not os.path.exists(target_index_path) and asset_url:
            try:
                with urllib.request.urlopen(asset_url, timeout=10) as response:
                    asset_content = response.read()
                with open(target_index_path, 'wb') as f:
                    f.write(asset_content)
            except Exception:
                pass

        if os.path.exists(target_index_path):
            try:
                with open(target_index_path, 'r', encoding='utf-8') as f_idx:
                    index_data = json.load(f_idx)
                
                objects_dict = index_data.get('objects', {})
                essential_assets = {k: v for k, v in objects_dict.items() if "sounds/" in k or "lang/" in k or "music/" in k or "textures/" in k or "icons/" in k}
                
                count = 0
                for asset_name, asset_meta in essential_assets.items():
                    obj_hash = asset_meta.get('hash')
                    if obj_hash:
                        obj_subfolder = obj_hash[:2]
                        obj_target_dir = os.path.join(objects_dir, obj_subfolder)
                        if not os.path.exists(obj_target_dir):
                            os.makedirs(obj_target_dir)
                            
                        obj_file_path = os.path.join(obj_target_dir, obj_hash)
                        if not os.path.exists(obj_file_path):
                            obj_url = f"https://resources.download.minecraft.net/{obj_subfolder}/{obj_hash}"
                            try:
                                with urllib.request.urlopen(obj_url, timeout=5) as res_obj:
                                    obj_data = res_obj.read()
                                with open(obj_file_path, 'wb') as f_obj:
                                    f_obj.write(obj_data)
                                count += 1
                            except Exception:
                                continue
                if count > 0:
                    logger.info(f"Đã cập nhật thêm {count} tệp tài nguyên thành công.")
            except Exception as e:
                logger.error(f"Lỗi xử lý sơ đồ Assets: {e}")

    if not os.path.exists(client_jar_path):
        client_download_url = version_data.get('downloads', {}).get('client', {}).get('url')
        if client_download_url:
            try:
                with urllib.request.urlopen(client_download_url, timeout=30) as response:
                    jar_content = response.read()
                with open(client_jar_path, 'wb') as f:
                    f.write(jar_content)
            except Exception:
                pass
                
    libs = version_data.get('libraries', [])
    for lib in libs:
        downloads = lib.get('downloads', {})
        artifacts_to_download = []
        if 'artifact' in downloads and downloads['artifact']:
            artifacts_to_download.append(downloads['artifact'])
        if 'classifiers' in downloads and downloads['classifiers']:
            classifiers = downloads['classifiers']
            for key in ['natives-windows', 'natives-windows-x86_64', 'natives-windows-amd64']:
                if key in classifiers:
                    artifacts_to_download.append(classifiers[key])
                    
        for artifact in artifacts_to_download:
            download_url = artifact.get('url')
            relative_path = artifact.get('path')
            if download_url and relative_path:
                dest_file_path = os.path.join(lib_dir, relative_path)
                dest_dir = os.path.dirname(dest_file_path)
                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir)
                if not os.path.exists(dest_file_path):
                    try:
                        with urllib.request.urlopen(download_url, timeout=10) as response:
                            lib_content = response.read()
                        with open(dest_file_path, 'wb') as f:
                            f.write(lib_content)
                    except Exception:
                        continue
                if zipfile.is_zipfile(dest_file_path) and ("natives" in os.path.basename(dest_file_path) or "windows" in os.path.basename(dest_file_path)):
                    try:
                        with zipfile.ZipFile(dest_file_path, 'r') as zip_ref:
                            for file_name in zip_ref.namelist():
                                if file_name.endswith('.dll') or '.dll' in file_name:
                                    target_name = os.path.basename(file_name)
                                    if target_name:
                                        with open(os.path.join(natives_dir, target_name), "wb") as f_out:
                                            f_out.write(zip_ref.read(file_name))
                    except Exception:
                        pass
    return instance_path, json_path, client_jar_path, lib_dir, natives_dir

# --- 5. LOGIC KHỞI CHẠY GAME NÂNG CAO (FIX HOÀN TOÀN TEXTURE & CẤP RAM ĐỘNG) ---
def launch_game_instance(username, version_id, selected_java, allocated_ram, on_success_callback=None):
    _, _, current_assets, _ = get_game_directories()
    setup_data = download_instance_assets(version_id)
    if not setup_data:
        logger.error("Không thể đồng bộ tài nguyên!")
        return
        
    instance_path, json_path, client_jar_path, lib_dir, natives_dir = setup_data
    classpath_libraries = []
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    for lib in data.get('libraries', []):
        downloads = lib.get('downloads', {})
        if 'artifact' in downloads and downloads['artifact']:
            relative_path = downloads['artifact'].get('path')
            if relative_path:
                full_path = os.path.join(lib_dir, relative_path)
                if os.path.exists(full_path):
                    classpath_libraries.append(full_path)
                    
    classpath_libraries.append(client_jar_path)
    classpath_string = ";".join(classpath_libraries)
    
    asset_info = data.get('assetIndex', {})
    asset_index = str(asset_info.get('id', 'legacy'))
    
    abs_instance_dir = os.path.abspath(instance_path)
    abs_assets_dir = os.path.abspath(current_assets)
    abs_natives_dir = os.path.abspath(natives_dir)
    
    launch_args = [
        selected_java,
        f"-Xmx{allocated_ram}G",  # Nhận lượng RAM động chọn từ thanh trượt cài đặt
        "-XX:+UseG1GC",
        "-Dsun.java2d.noddraw=true",        
        f"-Djava.library.path={abs_natives_dir}",
        "-cp", classpath_string,
        "net.minecraft.client.main.Main",
        "--username", username,
        "--version", version_id,
        "--gameDir", abs_instance_dir,
        "--assetsDir", abs_assets_dir,       
        "--assetIndex", asset_index, 
        "--uuid", "00000000-0000-0000-0000-000000000000",
        "--accessToken", "null",
        "--userType", "legacy",
        "--userProperties", "{}"             
    ]
    
    logger.info("=== KÍCH HOẠT TIẾN TRÌNH KHỞI CHẠY GAME ===")
    try:
        if on_success_callback:
            on_success_callback()

        process = subprocess.Popen(
            launch_args, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='ignore',
            cwd=abs_instance_dir # Khóa môi trường làm việc tại mục chứa file .jar game để tránh Missing Textures
       )
        logger.info(f"Instance {version_id} đang chạy bằng Java: {selected_java} (PID: {process.pid})")
        for line in process.stdout:
            print(f"[MINECRAFT INSTANCE OUTPUT] {line.strip()}")
    except Exception as e:
        logger.error(f"Lỗi kích hoạt Java: {e}")

class NexusLauncher:
    def __init__(self, window):
        self.window = window
        self.window.title("NEXUS LAUNCHER - VN")
        self.window.geometry("520x460")
        self.window.resizable(False, False)
        
        self.COLOR_BG = "#13131A"        
        self.COLOR_CARD = "#1A1A24"      
        self.COLOR_TEXT = "#E2E8F0"      
        self.COLOR_ACCENT = "#00FF66"    
        self.COLOR_BTN = "#10B981"       
        self.COLOR_BTN_HOVER = "#059669" 

        self.window.configure(bg=self.COLOR_BG)
        
        # Tải cấu hình tài khoản và mức RAM đã lưu trước đó
        self.config_data = load_launcher_config()
        self.ram_value_gb = self.config_data.get("allocated_ram", 2)
        
        self.setup_styles()
        self.create_widgets()
        self.load_saved_instance_data()

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TCombobox", 
                             fieldbackground=self.COLOR_CARD, 
                             background=self.COLOR_CARD, 
                             foreground=self.COLOR_TEXT, 
                             arrowcolor=self.COLOR_ACCENT,
                             bordercolor=self.COLOR_BG)
        self.window.option_add("*TCombobox*Listbox.background", self.COLOR_CARD)
        self.window.option_add("*TCombobox*Listbox.foreground", self.COLOR_TEXT)
        self.window.option_add("*TCombobox*Listbox.selectBackground", self.COLOR_ACCENT)

    def create_widgets(self):
        # 📌 THANH TIÊU ĐỀ NÊN CÓ NÚT BA GẠCH CÀI ĐẶT NGẦU
        header_frame = tk.Frame(self.window, bg=self.COLOR_BG)
        header_frame.pack(fill="x", padx=25, pady=(15, 2))
        
        # Nút cài đặt 3 gạch biểu tượng tối giản
        btn_settings = tk.Button(header_frame, text="☰", font=("Segoe UI", 14, "bold"), bg=self.COLOR_BG, fg=self.COLOR_ACCENT, bd=0, activebackground=self.COLOR_BG, activeforeground="#FFFFFF", cursor="hand2", command=self.open_settings_panel)
        btn_settings.pack(side="left", anchor="w")

        self.title_label = tk.Label(header_frame, text="NEXUS LAUNCHER VN", font=("Segoe UI", 16, "bold"), fg=self.COLOR_ACCENT, bg=self.COLOR_BG)
        self.title_label.pack(side="left", padx=15)
        
        self.subtitle_label = tk.Label(self.window, text="Hệ thống quản lý Multi-Instance mượt mà", font=("Segoe UI", 9, "italic"), fg="#718096", bg=self.COLOR_BG)
        self.subtitle_label.pack(pady=(0, 10))

        self.card_frame = tk.Frame(self.window, bg=self.COLOR_CARD, bd=0, highlightbackground="#2D3748", highlightthickness=1)
        self.card_frame.pack(padx=25, pady=5, fill="both", expand=True)
        self.card_frame.columnconfigure(0, weight=1)

        # 1. TÊN NGƯỜI CHƠI
        tk.Label(self.card_frame, text="TÊN NGƯỜI CHƠI (OFFLINE)", font=("Segoe UI", 9, "bold"), fg=self.COLOR_TEXT, bg=self.COLOR_CARD).grid(row=0, column=0, sticky="w", padx=20, pady=(10, 2))
        self.username_entry = tk.Entry(self.card_frame, font=("Segoe UI", 10), bg=self.COLOR_BG, fg="#FFFFFF", insertbackground=self.COLOR_ACCENT, bd=0, highlightthickness=1, highlightbackground="#2D3748", highlightcolor=self.COLOR_ACCENT)
        self.username_entry.grid(row=1, column=0, sticky="we", padx=20, pady=(0, 8), ipady=4)

        # 2. CHỌN PHIÊN BẢN
        tk.Label(self.card_frame, text="CHỌN PHIÊN BẢN GAME", font=("Segoe UI", 9, "bold"), fg=self.COLOR_TEXT, bg=self.COLOR_CARD).grid(row=2, column=0, sticky="w", padx=20, pady=(4, 2))
        self.version_combo = ttk.Combobox(self.card_frame, font=("Segoe UI", 10), state="readonly")
        self.version_combo['values'] = ('1.0.0', '1.10', '1.11', '1.12.2', '1.16.5', '1.20.1', '1.21', '1.21.1', '1.21.3')
        self.version_combo.grid(row=3, column=0, sticky="we", padx=20, pady=(0, 8))
        self.version_combo.bind("<<ComboboxSelected>>", self.on_version_changed)

        # 3. ĐƯỜNG DẪN JAVA RUNTIME CUSTOM
        tk.Label(self.card_frame, text="ĐƯỜNG DẪN ĐẾN JAVA RUNTIME (ÉP BUỘC)", font=("Segoe UI", 9, "bold"), fg=self.COLOR_ACCENT, bg=self.COLOR_CARD).grid(row=4, column=0, sticky="w", padx=20, pady=(4, 2))
        
        java_select_frame = tk.Frame(self.card_frame, bg=self.COLOR_CARD)
        java_select_frame.grid(row=5, column=0, sticky="we", padx=20, pady=(0, 10))
        java_select_frame.columnconfigure(0, weight=1)

        self.java_path_entry = tk.Entry(java_select_frame, font=("Segoe UI", 9), bg=self.COLOR_BG, fg="#A0AEC0", insertbackground=self.COLOR_ACCENT, bd=0, highlightthickness=1, highlightbackground="#2D3748", highlightcolor=self.COLOR_ACCENT)
        self.java_path_entry.grid(row=0, column=0, sticky="we", ipady=4)

        btn_browse_java = tk.Button(java_select_frame, text="Chọn tệp...", font=("Segoe UI", 9, "bold"), bg="#4A5568", fg="#FFFFFF", bd=0, cursor="hand2", padx=10, command=self.browse_java_path)
        btn_browse_java.grid(row=0, column=1, padx=(8, 0), sticky="ns")

        # 4. NÚT KHỞI CHẠY GAME
        self.btn_play = tk.Button(self.window, text="LAUNCH GAME", font=("Segoe UI", 12, "bold"), bg=self.COLOR_BTN, fg="#FFFFFF", activebackground=self.COLOR_BTN_HOVER, activeforeground="#FFFFFF", bd=0, cursor="hand2", command=self.start_play_thread)
        self.btn_play.pack(fill="x", padx=25, pady=(10, 15), ipady=6)
        
        self.btn_play.bind("<Enter>", lambda e: self.btn_play.config(bg=self.COLOR_BTN_HOVER))
        self.btn_play.bind("<Leave>", lambda e: self.btn_play.config(bg=self.COLOR_BTN))

    def browse_java_path(self):
        file_selected = filedialog.askopenfilename(title="Chọn tệp thực thi java.exe của bạn", filetypes=[("Java Executable", "java.exe"), ("All Files", "*.*")])
        if file_selected:
            self.java_path_entry.delete(0, tk.END)
            self.java_path_entry.insert(0, file_selected)

    def load_saved_instance_data(self):
        last_version = self.config_data.get("last_version", "1.20.1")
        if last_version in self.version_combo['values']:
            self.version_combo.set(last_version)
        else:
            self.version_combo.current(5) # Mặc định trỏ vào bản 1.20.1
        self.on_version_changed(None)

    def on_version_changed(self, event):
        selected_version = self.version_combo.get()
        instances_config = self.config_data.get("instances", {})
        
        self.username_entry.delete(0, tk.END)
        self.java_path_entry.delete(0, tk.END)
        
        if selected_version in instances_config:
            saved_name = instances_config[selected_version].get("username", "MojoPC_Player")
            saved_java = instances_config[selected_version].get("java_path", "java")
            self.username_entry.insert(0, saved_name)
            self.java_path_entry.insert(0, saved_java)
        else:
            self.username_entry.insert(0, "MojoPC_Player")
            self.java_path_entry.insert(0, "java")

    # 📌 CỬA SỔ SETTINGS PHỤ ẨN (KÍCH HOẠT KHI BẤM NÚT ☰)
    def open_settings_panel(self):
        settings_win = tk.Toplevel(self.window)
        settings_win.title("NEXUS LAUNCHER - SETTINGS")
        settings_win.geometry("420x300")
        settings_win.resizable(False, False)
        settings_win.configure(bg=self.COLOR_BG)
        settings_win.transient(self.window)
        settings_win.grab_set()

        tk.Label(settings_win, text="CẤU HÌNH HỆ THỐNG LAUNCHER", font=("Segoe UI", 12, "bold"), fg=self.COLOR_ACCENT, bg=self.COLOR_BG).pack(pady=(15, 10))

        # --- A. THANH TRƯỢT ĐIỀU CHỈNH RAM (TỐI ĐA 32GB) ---
        ram_frame = tk.Frame(settings_win, bg=self.COLOR_CARD, bd=0, highlightbackground="#2D3748", highlightthickness=1)
        ram_frame.pack(padx=20, pady=5, fill="x")
        
        ram_label = tk.Label(ram_frame, text=f"Dung lượng RAM cấp cho game: {self.ram_value_gb} GB", font=("Segoe UI", 9, "bold"), fg=self.COLOR_TEXT, bg=self.COLOR_CARD)
        ram_label.pack(anchor="w", padx=15, pady=(8, 2))

        def update_ram_label(val):
            self.ram_value_gb = int(float(val))
            ram_label.config(text=f"Dung lượng RAM cấp cho game: {self.ram_value_gb} GB")

        #  ĐOẠN MỚI HIỂN THỊ THANH TRƯỢT RÕ RÀNG:
        ram_slider = tk.Scale(ram_frame, from_=1, to=32, orientation=tk.HORIZONTAL, bg=self.COLOR_CARD, fg=self.COLOR_ACCENT, highlightthickness=0, troughcolor=self.COLOR_BG, activebackground=self.COLOR_ACCENT, label="Kéo để chọn mức RAM (GB)", command=update_ram_label)
        ram_slider.set(self.ram_value_gb)
        ram_slider.pack(fill="x", padx=15, pady=(0, 10))

        # --- B. THAY ĐỔI ĐƯỜNG DẪN LƯU GAME (.minecraft_custom) ---
        dir_frame = tk.Frame(settings_win, bg=self.COLOR_CARD, bd=0, highlightbackground="#2D3748", highlightthickness=1)
        dir_frame.pack(padx=20, pady=10, fill="x")

        tk.Label(dir_frame, text="Thư mục lưu dữ liệu Game & Instances:", font=("Segoe UI", 9, "bold"), fg=self.COLOR_TEXT, bg=self.COLOR_CARD).pack(anchor="w", padx=15, pady=(8, 2))
        
        current_base, _, _, _ = get_game_directories()
        path_lbl = tk.Label(dir_frame, text=current_base, font=("Segoe UI", 8), fg="#A0AEC0", bg=self.COLOR_BG, wraplength=350, justify="left")
        path_lbl.pack(fill="x", padx=15, pady=2, ipady=3)

        def change_global_game_dir():
            chosen_dir = filedialog.askdirectory(title="Chọn thư mục mới để lưu dữ liệu Minecraft")
            if chosen_dir:
                try:
                    with open(GLOBAL_CONFIG_PATH, "w", encoding="utf-8") as f_global:
                        json.dump({"custom_game_dir": chosen_dir}, f_global, indent=4)
                    path_lbl.config(text=chosen_dir)
                    messagebox.showinfo("Thành công", "Đã đổi thư mục lưu game! Hãy khởi động lại Launcher để áp dụng dữ liệu sạch.")
                except Exception as ex:
                    messagebox.showerror("Lỗi", f"Không thể ghi cấu hình đường dẫn: {ex}")

        btn_change_dir = tk.Button(dir_frame, text="Thay đổi thư mục lưu...", font=("Segoe UI", 9, "bold"), bg="#4A5568", fg="#FFFFFF", bd=0, cursor="hand2", command=change_global_game_dir)
        btn_change_dir.pack(anchor="e", padx=15, pady=(5, 10))

    def start_play_thread(self):
        username = self.username_entry.get().strip()
        selected_version = self.version_combo.get()
        selected_java = self.java_path_entry.get().strip()
        
        if not username:
            messagebox.showwarning("Cảnh báo", "Tên người chơi không được để trống!")
            return
        if not selected_java:
            selected_java = "java"
            
        # 📌 HỆ THỐNG EASTER EGG TROLL NGƯỜI CHƠI KHÔNG TIN BẠN LÀ DEV
        TEN_NGUOI_CHOI_TROLL = "GamerCungDau123"
        if username == TEN_NGUOI_CHOI_TROLL:
            self.window.title(f"{TEN_NGUOI_CHOI_TROLL}'s Launcher (Not Nexus anymore!)")
            self.title_label.config(text=f"{TEN_NGUOI_CHOI_TROLL.upper()} LAUNCHER", fg="#FF3333")
            self.subtitle_label.config(text="Ứng dụng này đã bị chiếm quyền bởi Creator!", fg="#FF8888")
            messagebox.showwarning("Hệ Thống Bị Can Thiệp", f"Launcher nhận diện tài khoản {TEN_NGUOI_CHOI_TROLL}! Kích hoạt chế độ Troll!")
        
        # Cập nhật và lưu lại dữ liệu RAM + Tài khoản
        update_instance_data(selected_version, username, selected_java, self.ram_value_gb)
        
        self.btn_play.config(text="ĐANG KHỞI CHẠY GAME...", state="disabled", bg="#4A5568")
        
        launcher_thread = threading.Thread(
            target=launch_game_instance, 
            args=(username, selected_version, selected_java, self.ram_value_gb, self.hide_launcher_safely),
            daemon=True
        )
        launcher_thread.start()

    def hide_launcher_safely(self):
        try:
            self.window.withdraw()
        except Exception:
            pass

if __name__ == "__main__":
    root = tk.Tk()
    app = NexusLauncher(root)
    root.mainloop()

