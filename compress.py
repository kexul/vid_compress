import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinterdnd2 import DND_FILES, TkinterDnD
import subprocess
import os
import threading
import cv2
from PIL import Image, ImageTk

# Global variables
original_frame = None
compressed_frame = None
slider_x = None
is_sliding = False
original_photo = None  # Cache for original image
compressed_photo = None  # Cache for compressed image
canvas_bottom = None  # Bottom layer canvas
canvas_top = None    # Top layer canvas

def calculate_preview_size(width, height, max_size=1080):
    """Calculate appropriate preview size while maintaining aspect ratio"""
    scale = min(max_size/width, max_size/height)
    return int(width*scale), int(height*scale)

def update_preview(file_path, is_compressed=False):
    global original_frame, compressed_frame, slider_x, original_photo, compressed_photo
    
    if not file_path.lower().endswith(('.mp4', '.avi', '.mkv', '.mov')):
        status_label.config(text="Error: Unsupported file format", foreground="red")
        return False
        
    try:
        cap = cv2.VideoCapture(file_path)
        ret, frame = cap.read()
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        
        if not ret:
            status_label.config(text="Error: Cannot read video file", foreground="red")
            return False
            
        # Calculate preview size
        preview_w, preview_h = calculate_preview_size(w, h)
        
        # Adjust Canvas size
        canvas_bottom.config(width=preview_w, height=preview_h)
        canvas_top.config(width=preview_w // 2, height=preview_h)
        
        # Convert color from BGR to RGB and resize
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = cv2.resize(frame, (preview_w, preview_h))
        
        # Store frames
        if is_compressed:
            compressed_frame = frame
        else:
            original_frame = frame
            compressed_frame = None  # Clear old compressed frame
            slider_x = preview_w // 2  # Initialize slider position
            original_photo = None
            compressed_photo = None
        
        update_comparison_view()
        
        # Adjust window size
        window.geometry(f"{preview_w + 40}x{preview_h + 150}")
        center_window()
        return True
        
    except Exception as e:
        status_label.config(text=f"Error: {str(e)}", foreground="red")
        return False

def update_comparison_view():
    global original_photo, compressed_photo
    if original_frame is None:
        return
        
    h, w = original_frame.shape[:2]
    
    # Clear canvas
    canvas_bottom.delete("all")
    canvas_top.delete("all")
    
    # Create or refresh original image
    if original_photo is None:
        image = Image.fromarray(original_frame)
        original_photo = ImageTk.PhotoImage(image)
    
    if compressed_frame is not None:
        # Create compressed image
        if compressed_photo is None:
            image = Image.fromarray(compressed_frame)
            compressed_photo = ImageTk.PhotoImage(image)
            
        # Bottom canvas displays compressed image
        canvas_bottom.create_image(w//2, h//2, image=compressed_photo, anchor='center')
        
        # Top canvas displays original image
        canvas_top.create_image(w//2, h//2, image=original_photo, anchor='center')
        
        # Update top canvas width
        canvas_top.configure(width=slider_x)
        
        # Draw separator line and controller
        y_mid = h // 2
        arrow_size = 10  # Triangle size
        
        # Draw orange border triangle
        canvas_bottom.create_polygon(
            slider_x - 2, y_mid - arrow_size,
            slider_x - 2, y_mid + arrow_size,
            slider_x + arrow_size, y_mid,
            fill='#FF3D00'
        )
        
    else:
        # Only display original image
        canvas_bottom.create_image(w//2, h//2, image=original_photo, anchor='center')

def handle_slider(event):
    global slider_x, is_sliding
    if compressed_frame is not None and is_sliding:
        w = canvas_bottom.winfo_width()
        slider_x = max(0, min(w, event.x))
        update_comparison_view()

def start_slide(event):
    global is_sliding
    if compressed_frame is not None:
        # Check if clicked near slider
        if abs(event.x - slider_x) < 20:
            is_sliding = True
            canvas_bottom.config(cursor="sb_h_double_arrow")
            return  # Return if sliding operation
    
    # Trigger file selection in other cases
    select_file(event)

def end_slide(event):
    global is_sliding
    is_sliding = False
    canvas_bottom.config(cursor="hand2")

def handle_mouse_move(event):
    if compressed_frame is not None:
        # Check if near slider
        if abs(event.x - slider_x) < 20:
            canvas_bottom.config(cursor="sb_h_double_arrow")
        else:
            canvas_bottom.config(cursor="hand2")

def show_file_info(file_path):
    try:
        file_size = get_file_size(file_path)
        status_label.config(text=f"File size: {file_size}MB", foreground="#666666")
    except Exception as e:
        status_label.config(text="Error: Cannot get file size", foreground="red")

def handle_drop(event):
    file_path = event.data.strip('{}')
    if not os.path.isfile(file_path):
        return
    
    # Clear drop highlight
    canvas_bottom.configure(highlightbackground='#cccccc')
    
    # Show file size
    show_file_info(file_path)
    
    # Try preview, return if failed
    if not update_preview(file_path):
        return
    
    # Auto-generate output file path
    dirname = os.path.dirname(file_path)
    basename = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.join(dirname, f"{basename}_compressed.mp4")
    
    compress_video(file_path, output_path)

def get_file_size(file_path):
    size_bytes = os.path.getsize(file_path)
    # Convert to MB and keep 2 decimal places
    return round(size_bytes / (1024 * 1024), 2)

def compress_video(input_file, output_file):
    ffmpeg_path = os.path.join(os.path.dirname(__file__), "ffmpeg.exe")
    
    if not os.path.exists(ffmpeg_path):
        status_label.config(text="Error: ffmpeg.exe not found in program directory", foreground="red")
        return
    
    input_size = get_file_size(input_file)
    
    # First get compressed preview frame
    preview_cmd = [
        ffmpeg_path, "-i", input_file,
        "-vframes", "1",  # Process only one frame
        "-c:v", "libx264",
        "-crf", "23",
        "-preset", "medium",
        "-y", "temp_preview.mp4"
    ]
    
    try:
        subprocess.run(preview_cmd, capture_output=True)
        # Immediately update preview
        update_preview("temp_preview.mp4", is_compressed=True)
        # Delete temporary file
        os.remove("temp_preview.mp4")
    except Exception as e:
        print(f"Preview generation failed: {e}")
    
    # Continue full compression process
    ffmpeg_cmd = [
        ffmpeg_path, "-i", input_file,
        "-c:v", "libx264",
        "-crf", "23",
        "-preset", "medium",
        "-c:a", "aac",
        "-b:a", "128k",
        "-y", output_file
    ]
    
    canvas_bottom.config(state=tk.DISABLED)
    status_label.config(text=f"File size: {input_size}MB, Compressing...", foreground="blue")
    progress_bar['value'] = 0
    window.update()
    
    def run_compression():
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        process = subprocess.Popen(
            ffmpeg_cmd,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            universal_newlines=True,
            encoding='utf-8'
        )
        
        duration = None
        while True:
            line = process.stderr.readline()
            if not line:
                break
            
            if "Duration:" in line:
                time_str = line.split("Duration: ")[1].split(",")[0].strip()
                if time_str != "N/A":
                    h, m, s = time_str.split(":")
                    duration = float(h) * 3600 + float(m) * 60 + float(s)
            
            if "time=" in line and duration:
                time_str = line.split("time=")[1].strip().split()[0]
                if time_str != "N/A":
                    try:
                        parts = time_str.split(':')
                        current = float(parts[-1].split('.')[0])
                        if len(parts) > 1:
                            current += float(parts[-2]) * 60
                        if len(parts) > 2:
                            current += float(parts[-3]) * 3600
                        
                        progress = (current / duration) * 100
                        progress_bar['value'] = min(progress, 100)
                        window.update_idletasks()
                    except (ValueError, IndexError):
                        continue
        
        output_size = get_file_size(output_file)
        ratio = round((1 - output_size/input_size) * 100, 1)
        status_label.config(
            text=f"Complete: {input_size}MB → {output_size}MB (Reduced {ratio}%)", 
            foreground="green"
        )
        progress_bar['value'] = 100
        
        canvas_bottom.config(state=tk.NORMAL)
    
    threading.Thread(target=run_compression, daemon=True).start()

def select_file(event=None):
    file_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov")])
    if file_path:
        # Show file size
        show_file_info(file_path)
        # Simulate drop event
        class DummyEvent:
            def __init__(self, data):
                self.data = data
        
        handle_drop(DummyEvent(file_path))


# Create window
window = TkinterDnD.Tk()
window.title("Video Compressor")
window.geometry("300x400")  # Adjust window height
window.configure(bg='white')

# Center window on screen
def center_window():
    window.update_idletasks()  # Update window size
    width = window.winfo_width()
    height = window.winfo_height()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry('{}x{}+{}+{}'.format(width, height, x, y))

center_window()

style = ttk.Style()
style.layout('Custom.Horizontal.TProgressbar', 
             [('Horizontal.Progressbar.trough',
               {'children': [('Horizontal.Progressbar.pbar',
                            {'side': 'left', 'sticky': 'ns'})],
                'sticky': 'nswe'})])
style.configure('Custom.Horizontal.TProgressbar',
               background='#2196F3',
               troughcolor='#E0E0E0',
               borderwidth=0,
               thickness=10)

main_frame = ttk.Frame(window, padding=10)
main_frame.pack(fill=tk.BOTH, expand=True)

# Replace original drop_area creation code with dual canvas implementation
canvas_frame = ttk.Frame(main_frame)
canvas_frame.pack(pady=20, expand=True)

# Create overlapping canvases
canvas_bottom = tk.Canvas(canvas_frame, 
                         width=250, height=250,
                         bg='white', 
                         highlightthickness=2,
                         highlightbackground='#cccccc',
                         cursor="hand2")
canvas_bottom.pack(fill="both", expand=True)

canvas_bottom.create_text(125, 125, text="Drop video file here", 
                         fill='#666666', 
                         font=('Microsoft YaHei UI', 10))

# Create top layer canvas, initial width is half of bottom canvas
canvas_top = tk.Canvas(canvas_frame,
                      width=10, height=250,
                      bg='white', 
                      highlightthickness=2,
                      highlightbackground='#cccccc',
                      cursor="hand2")
canvas_top.place(x=0, y=0, relheight=1.0)

# Modify event bindings
canvas_bottom.drop_target_register(DND_FILES)
canvas_bottom.dnd_bind('<<Drop>>', handle_drop)

canvas_bottom.bind('<Button-1>', start_slide)
canvas_bottom.bind('<B1-Motion>', handle_slider)
canvas_bottom.bind('<ButtonRelease-1>', end_slide)
canvas_bottom.bind('<Motion>', handle_mouse_move)

canvas_top.bind('<Button-1>', start_slide)
canvas_top.bind('<B1-Motion>', handle_slider)
canvas_top.bind('<ButtonRelease-1>', end_slide)
canvas_top.bind('<Motion>', handle_mouse_move)

# Progress bar and status
progress_bar = ttk.Progressbar(main_frame, 
                             style="Custom.Horizontal.TProgressbar",
                             mode='determinate')
progress_bar.pack(fill=tk.X, pady=5)

status_label = ttk.Label(main_frame, text="Waiting for file...", anchor='center')
status_label.pack(fill=tk.X)

window.mainloop()