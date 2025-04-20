import customtkinter as ctk
import yt_dlp
import os
import threading
import requests
import json
from tkinter import filedialog
from PIL import Image, ImageTk
from io import BytesIO
from datetime import datetime
import re  # 放在最上方

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


# 加在啟動前（主程式前）
download_icon_image = Image.open("assets/download.png").resize((24, 24))
download_icon = ctk.CTkImage(light_image=download_icon_image, size=(24, 24))

# 加在啟動前（主程式前）
folder_icon_image = Image.open("assets/folder-search.png").resize((24, 24))
folder_icon = ctk.CTkImage(light_image=folder_icon_image, size=(24, 24))


app = ctk.CTk()
app.title("🎬 多任務影片下載器")
app.geometry("1000x600")

# ========== 左側輸入區 ==========
url_entry = ctk.CTkEntry(app, width=400, height=40, placeholder_text="請輸入影片網址")
url_entry.place(x=20, y=20)

folder_path = ctk.StringVar(value="./downloads")
folder_entry = ctk.CTkEntry(app, width=400, height=40, textvariable=folder_path)
folder_entry.place(x=20, y=80)

def choose_folder():
    folder = filedialog.askdirectory()
    if folder:
        folder_path.set(folder)

ctk.CTkButton(app,  image=folder_icon,text="", width=40,height=40, command=choose_folder).place(x=430, y=80)

# ========== 任務區域（右側） ==========
scroll_frame = ctk.CTkScrollableFrame(app, width=460, height=560)
scroll_frame.place(x=520, y=20)

task_index = 0
task_list = []

# ========== 任務卡結構 ==========
class DownloadTaskFrame(ctk.CTkFrame):
    def __init__(self, master, info, output_folder):
        super().__init__(master, corner_radius=10)
        


        self.title = info.get("title", "未知標題")
        self.thumb_url = info.get("thumbnail")
        self.url = info.get("webpage_url")
        self.output_folder = output_folder
        self.cancel_flag = threading.Event()
        self.last_eta_seconds = None  # <--- 加這一行！
        self.eta_history = []

        # 建立橫向內容區塊
        content_frame = ctk.CTkFrame(self)
        content_frame.pack(padx=10, pady=5, fill="x")

        thumb_max_height = 100
        display_size = (thumb_max_height, thumb_max_height)

        if self.thumb_url:
            response = requests.get(self.thumb_url)
            image = Image.open(BytesIO(response.content))
            w, h = image.size
            aspect_ratio = w / h

            if aspect_ratio < 1:
                # 直式影片：高度統一為 100，寬度依比例縮小
                display_height = thumb_max_height
                display_width = int(display_height * aspect_ratio)
            else:
                # 橫式影片：固定寬度為 160，高度依比例縮小
                display_height = thumb_max_height
                display_width = int(display_height * aspect_ratio)

            display_size = (display_width, display_height)
            image = image.resize(display_size, Image.Resampling.LANCZOS)
            self.tk_image = ctk.CTkImage(light_image=image, size=display_size)
            # 左側 thumbnail 容器（固定寬高）
            thumb_container = ctk.CTkFrame(content_frame, width=160, height=100)
            thumb_container.pack_propagate(False)  # 不讓內容改變大小
            thumb_container.pack(side="left", padx=10, pady=10)

            # 加入縮圖置中顯示
            self.thumb = ctk.CTkLabel(thumb_container, image=self.tk_image, text="")
            self.thumb.place(relx=0.5, rely=0.5, anchor="center")  # 完全置中


        info_frame = ctk.CTkFrame(content_frame, fg_color="transparent")  # 改為透明背景
        info_frame.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=5)

        self.label = ctk.CTkLabel(info_frame, text=self.title, anchor="w", justify="left", wraplength=300, font=("Helvetica", 14))
        self.label.pack(anchor="w", pady=(0, 5), padx=(5, 0), fill="x")

        self.progress = ctk.CTkProgressBar(info_frame)
        self.progress.set(0)
        self.progress.pack(pady=5, fill="x", padx=(5, 20))

        self.status = ctk.CTkLabel(info_frame, text="等待中...", font=("Helvetica", 12))
        self.status.pack(anchor="w", padx=(5, 0))

        self.cancel_btn = ctk.CTkButton(info_frame, text="取消下載", fg_color="red", command=self.cancel_download)
        self.cancel_btn.pack(pady=2, anchor="w", padx=(5, 0))

        # 啟動執行緒下載
        threading.Thread(target=self.download, daemon=True).start()
        

    def cancel_download(self):
        self.cancel_flag.set()
        self.status.configure(text="⛔ 已取消")
        self.progress.set(0)


    def pack_self(self):
        children = self.master.winfo_children()
        if children and children[0] != self:
            self.pack(pady=10, padx=10, fill="x", before=children[0])
        else:
            self.pack(pady=10, padx=10, fill="x")

    def download(self):
        def hook(d):
            if self.cancel_flag.is_set():
                raise Exception("使用者取消下載")

            if d['status'] == 'downloading':
                raw_percent = d.get('_percent_str', '0%')

                # ✅ 移除 ANSI 顏色控制碼
                clean_percent = re.sub(r'\x1b\[[0-9;]*m', '', raw_percent).strip('%')

                try:
                    p = float(clean_percent) / 100.0
                except:
                    p = 0.0

                self.progress.set(p)
                
                self.status.configure(text=f"下載中... {int(p*100)}%")
                       



            elif d['status'] == 'finished':
                self.status.configure(text="✅ 完成！")

        filename_tpl = os.path.join(self.output_folder, '%(title)s.%(ext)s')
        os.makedirs(self.output_folder, exist_ok=True)

        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
            'outtmpl': filename_tpl,
            'merge_output_format': 'mp4',
            'quiet': True,
            'progress_hooks': [hook],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            self.status.configure(text="🎉 下載完成")
            self.save_history()
        except Exception as e:
            self.status.configure(text=f"❌ 錯誤：{e}")

    def save_history(self):
        record = {
            "title": self.title,
            "url": self.url,
            "thumbnail": self.thumb_url,
            "datetime": datetime.now().isoformat()
        }
        history_file = "download_history.json"
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = []
        data.append(record)
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

# ========== 開始下載按鈕功能 ==========
def start_download():
    url = url_entry.get().strip()
    folder = folder_path.get()
    if not url:
        return
    threading.Thread(target=create_task, args=(url, folder), daemon=True).start()

def create_task(url, folder):
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)

        task = DownloadTaskFrame(scroll_frame, info, folder)

        # ✅ 插到「最新一個任務」上方（也就是 task_list 最前面那個）
        if task_list:
            task.pack(pady=10, padx=10, fill="x", before=task_list[0])
        else:
            task.pack(pady=10, padx=10, fill="x")

        # 放進最前面位置
        task_list.insert(0, task)

    except Exception as e:
        print("❌ 影片抓取錯誤：", e)




ctk.CTkButton(app, text="開始下載", image=download_icon, compound="left", command=start_download, width=200, height=40, fg_color="#22c55e", hover_color="#16a34a",text_color="#000000").place(x=20, y=140)

app.mainloop()
