from itertools import cycle
from random import randrange, choice
from tkinter import Canvas, Tk, messagebox, font, Toplevel, Button, Label
import math 
import sys
import os

# --- DATABASE SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

DB_CONNECTED = False

try:
    from db_config import get_db_connection
    DB_CONNECTED = True
except ImportError:
    print("Error: Could not import db_config.")
    get_db_connection = None

CURRENT_USER_ID = sys.argv[1] if len(sys.argv) > 1 else None

# --- GAME WINDOW SETUP ---
root = Tk()
root.title("Shape Catcher")

# Force focus
root.lift()
root.attributes('-topmost', True)
root.after_idle(root.attributes, '-topmost', False)
root.focus_force()

# Maximize
try:
    root.state('zoomed')
except:
    w, h = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{w}x{h}+0+0")

CANVAS_WIDTH = root.winfo_screenwidth()
CANVAS_HEIGHT = root.winfo_screenheight() - 80 

# Colors
COLOR_BG_ARCADE = "#1F1A33"  
COLOR_GRID_LINES = "#3E3B5A"
COLOR_HEADER = "#E900FF"     
COLOR_SCOREBOARD = "#00F0FF" 
CATCHER_PRIMARY = "#FF00EE"
CATCHER_ACCENT = "#4133FF"     
CATCHER_CORE = "#3374FF"     
CATCHER_DARK = "#0A0815"       

DEFAULT_SHAPE_POINTS = 10
SHAPE_CONFIG = [
    {"type": 'circle', "color": '#FF5733', "size": 50, "points": DEFAULT_SHAPE_POINTS}, 
    {"type": 'square', "color": '#33FF57', "size": 50, "points": DEFAULT_SHAPE_POINTS}, 
    {"type": 'triangle', "color": '#FF33E9', "size": 60, "points": DEFAULT_SHAPE_POINTS}, 
    {"type": 'star', "color": '#FFFF00', "size": 70, "points": DEFAULT_SHAPE_POINTS + 5}, 
    {"type": 'hexagon', "color": '#00FFFF', "size": 55, "points": DEFAULT_SHAPE_POINTS} 
]

CATCHER_WIDTH = 180
CATCHER_HEIGHT = 25 
CATCHER_MOVE_STEP = 40 

SHAPE_SPEED_MS = 20  
SHAPE_DROP_PIXELS = 6
SHAPE_INTERVAL_MS = 1500 
DIFFICULTY_FACTOR = 0.94 

if not CURRENT_USER_ID:
    messagebox.showwarning("Warning", "Playing in Guest Mode. Score will NOT be saved.")

game_frame = Canvas(root, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, background=COLOR_BG_ARCADE, highlightthickness=0)
game_frame.pack(fill="both", expand=True)

# Grid
for i in range(0, CANVAS_WIDTH, 50):
    game_frame.create_line(i, 0, i, CANVAS_HEIGHT, fill=COLOR_GRID_LINES, width=1)
for j in range(0, CANVAS_HEIGHT, 50):
    game_frame.create_line(0, j, CANVAS_WIDTH, j, fill=COLOR_GRID_LINES, width=1)

# Fonts
game_font = font.nametofont("TkFixedFont")
game_font.config(size=16, weight='bold')
header_font = font.nametofont("TkFixedFont")
header_font.config(size=24, weight='bold')
name_font = font.nametofont("TkFixedFont")
name_font.config(size=10, slant='italic')

# UI Text
game_frame.create_text(CANVAS_WIDTH / 2, 30, font=header_font, fill=COLOR_HEADER, text="S H A P E   C A T C H E R")
game_frame.create_text(CANVAS_WIDTH / 2, 55, font=name_font, fill="#FFFFFF", text="Designed by: Rassel John Dizon")

score = 0
score_text = game_frame.create_text(20, 85, anchor="nw", font=game_font, fill=COLOR_SCOREBOARD, text="SCORE: " + str(score))

lives_remaining = 3
lives_text = game_frame.create_text(CANVAS_WIDTH - 20, 85, anchor="ne", font=game_font, fill=COLOR_SCOREBOARD, text="LIVES: " + str(lives_remaining))

# Catcher Init
catcher_startx = CANVAS_WIDTH / 2 - CATCHER_WIDTH / 2
catcher_starty = CANVAS_HEIGHT - CATCHER_HEIGHT - 20
catcher_startx2 = catcher_startx + CATCHER_WIDTH
catcher_starty2 = catcher_starty + CATCHER_HEIGHT

catcher_elements = []
catcher_base_dark = game_frame.create_rectangle(catcher_startx - 5, catcher_starty - 5, catcher_startx2 + 5, catcher_starty2 + 5, fill=CATCHER_DARK, outline="", width=0)
catcher_elements.append(catcher_base_dark)
catcher_body = game_frame.create_rectangle(catcher_startx, catcher_starty, catcher_startx2, catcher_starty2, fill=CATCHER_PRIMARY, outline=CATCHER_ACCENT, width=2)
catcher_elements.append(catcher_body)
dx = CATCHER_WIDTH * 0.15
dy = CATCHER_HEIGHT * 0.25
catcher_detail = game_frame.create_rectangle(catcher_startx + dx, catcher_starty + dy, catcher_startx2 - dx, catcher_starty2 - dy, fill=CATCHER_CORE, outline=CATCHER_PRIMARY, width=1)
catcher_elements.append(catcher_detail)
catcher_collision_element = catcher_elements[1] 

shapes = []
current_speed = SHAPE_DROP_PIXELS
current_interval = SHAPE_INTERVAL_MS
game_running = True
paused = False

# --- PAUSE MENU LOGIC ---
def show_pause_menu(event=None):
    global game_running, paused
    if not game_running: return # Don't pause if game over
    
    paused = True # Stop the loops
    
    menu_win = Toplevel(root)
    menu_win.title("Paused")
    menu_win.geometry("300x250")
    
    # Center the window
    x = root.winfo_x() + (root.winfo_width() // 2) - 150
    y = root.winfo_y() + (root.winfo_height() // 2) - 125
    menu_win.geometry(f"+{x}+{y}")
    
    menu_win.config(bg=COLOR_BG_ARCADE)
    menu_win.grab_set() # Modal window
    menu_win.overrideredirect(True) # Remove title bar for cleaner look
    
    # Border
    frame = Canvas(menu_win, bg=COLOR_BG_ARCADE, highlightthickness=2, highlightbackground=COLOR_HEADER)
    frame.pack(fill="both", expand=True)

    Label(frame, text="GAME PAUSED", font=header_font, fg=COLOR_HEADER, bg=COLOR_BG_ARCADE).pack(pady=20)

    def resume():
        global paused
        paused = False
        menu_win.destroy()
        # Restart loops
        game_loop_tick()

    def retry():
        menu_win.destroy()
        reset_game()

    def quit_game():
        root.destroy()
        sys.exit()

    btn_style = {"font": game_font, "bg": COLOR_SCOREBOARD, "fg": COLOR_BG_ARCADE, "width": 15, "bd": 0}

    Button(frame, text="RESUME", command=resume, **btn_style).pack(pady=5)
    Button(frame, text="RETRY", command=retry, **btn_style).pack(pady=5)
    Button(frame, text="EXIT TO MENU", command=quit_game, **btn_style).pack(pady=5)

# --- Drawing Functions ---
def get_catcher_coords():
    return game_frame.coords(catcher_collision_element)

def draw_shape(x, y, config):
    shape_size = config["size"]
    half = shape_size / 2
    x1, y1, x2, y2 = x - half, y - half, x + half, y + half
    fill = config["color"]
    outline = "#FFFFFF"
    
    if config["type"] == 'circle':
        return game_frame.create_oval(x1, y1, x2, y2, fill=fill, width=3, outline=outline)
    elif config["type"] == 'square':
        return game_frame.create_rectangle(x1, y1, x2, y2, fill=fill, width=3, outline=outline)
    elif config["type"] == 'triangle':
        return game_frame.create_polygon(x, y1, x2, y2, x1, y2, fill=fill, width=3, outline=outline)
    elif config["type"] == 'hexagon':
        pts = []
        for i in range(6):
            ang = math.radians(30 + 60 * i)
            pts.extend([x + half * math.cos(ang), y + half * math.sin(ang)])
        return game_frame.create_polygon(pts, fill=fill, width=3, outline=outline)
    elif config["type"] == 'star':
        pts = []
        for i in range(10):
            r = half if i % 2 == 0 else half * 0.4
            ang = math.radians(i * 36 - 90)
            pts.extend([x + r * math.cos(ang), y + r * math.sin(ang)])
        return game_frame.create_polygon(pts, fill=fill, width=3, outline=outline)
    
    return game_frame.create_rectangle(x1, y1, x2, y2, fill=fill, width=3, outline=outline)

# --- Game Logic ---
def create_shape():
    if not game_running or paused: return
    config = choice(SHAPE_CONFIG)
    sz = config["size"]
    sx = randrange(sz, CANVAS_WIDTH - sz)
    sy = -sz
    id = draw_shape(sx, sy, config)
    shapes.append({"id": id, "config": config, "x": sx, "y": sy})
    root.after(int(current_interval), create_shape)

def game_loop_tick():
    """Main loop for movement and collision to handle pausing easier."""
    if not game_running or paused: return

    # Move Shapes
    for shape in shapes[:]:
        game_frame.move(shape["id"], 0, current_speed)
        coords = game_frame.coords(shape["id"])
        
        # Approximate Y for collision/drop check
        if coords:
            # Handle different shape coordinate structures
            ys = coords[1::2] # Get every Y coordinate
            max_y = max(ys)
            if max_y > CANVAS_HEIGHT:
                if shape in shapes: shapes.remove(shape)
                game_frame.delete(shape["id"])
                lose_a_life()
                if lives_remaining == 0: 
                    game_over()
                    return

    # Check Catch
    (cx1, cy1, cx2, cy2) = get_catcher_coords()
    for shape in shapes[:]:
        bbox = game_frame.bbox(shape["id"])
        if bbox:
            sx1, sy1, sx2, sy2 = bbox
            # Simple AABB collision
            if sy2 > cy1 and sy1 < cy2 and sx2 > cx1 and sx1 < cx2:
                shapes.remove(shape)
                game_frame.delete(shape["id"])
                increase_score(shape["config"]["points"])

    root.after(SHAPE_SPEED_MS, game_loop_tick)

def lose_a_life():
    global lives_remaining
    lives_remaining -= 1
    game_frame.itemconfigure(lives_text, text="LIVES: " + str(lives_remaining))

def increase_score(points):
    global score, current_speed, current_interval
    score += points
    current_speed = SHAPE_DROP_PIXELS + int(score / 40)
    current_interval *= DIFFICULTY_FACTOR
    game_frame.itemconfigure(score_text, text="SCORE: " + str(score))

def save_score():
    if CURRENT_USER_ID and DB_CONNECTED and get_db_connection:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO game_scores (user_id, game_name, score, timestamp, is_deleted) VALUES (%s, %s, %s, NOW(), 0)", 
                        (CURRENT_USER_ID, "Shape Catcher", score))
            conn.commit()
            conn.close()
            messagebox.showinfo("Saved", f"Score of {score} saved!")
        except Exception as e:
            print(e)

def game_over():
    global game_running
    game_running = False
    root.after(100, save_score)
    
    go_win = Toplevel(root)
    go_win.title("Game Over")
    go_win.geometry("300x200")
    
    x = root.winfo_x() + (root.winfo_width()//2) - 150
    y = root.winfo_y() + (root.winfo_height()//2) - 100
    go_win.geometry(f"+{x}+{y}")
    
    go_win.config(bg=COLOR_BG_ARCADE)
    go_win.grab_set()
    go_win.overrideredirect(True)

    Label(go_win, text="GAME OVER", font=header_font, fg="red", bg=COLOR_BG_ARCADE).pack(pady=20)
    Label(go_win, text=f"Final Score: {score}", font=game_font, fg="white", bg=COLOR_BG_ARCADE).pack(pady=5)
    
    Button(go_win, text="RETRY", command=lambda: [go_win.destroy(), reset_game()], bg=COLOR_SCOREBOARD, fg=COLOR_BG_ARCADE, width=10).pack(pady=5)
    Button(go_win, text="EXIT", command=lambda: [root.destroy(), sys.exit()], bg=COLOR_SCOREBOARD, fg=COLOR_BG_ARCADE, width=10).pack(pady=5)

def start_game():
    global game_running, paused
    game_running = True
    paused = False
    root.after(100, create_shape)
    root.after(100, game_loop_tick)

def reset_game():
    global score, lives_remaining, current_speed, current_interval, shapes
    score = 0
    lives_remaining = 3
    current_speed = SHAPE_DROP_PIXELS
    current_interval = SHAPE_INTERVAL_MS
    for s in shapes: game_frame.delete(s["id"])
    shapes = []
    game_frame.itemconfigure(score_text, text="SCORE: " + str(score))
    game_frame.itemconfigure(lives_text, text="LIVES: " + str(lives_remaining))
    
    # Center catcher
    (x1, _, x2, _) = get_catcher_coords()
    dx = (CANVAS_WIDTH/2) - ((x1+x2)/2)
    for e in catcher_elements: game_frame.move(e, dx, 0)
    
    start_game()

# --- Input ---
def move_catcher(dx):
    if not game_running or paused: return
    (x1, _, x2, _) = get_catcher_coords()
    if x1 + dx > 0 and x2 + dx < CANVAS_WIDTH:
        for e in catcher_elements: game_frame.move(e, dx, 0)

def on_mouse_move(e):
    if not game_running or paused: return
    (x1, _, x2, _) = get_catcher_coords()
    w = x2 - x1
    tx = e.x - w/2
    if tx < 0: tx = 0
    elif tx + w > CANVAS_WIDTH: tx = CANVAS_WIDTH - w
    dx = tx - x1
    for el in catcher_elements: game_frame.move(el, dx, 0)

root.bind("<Left>", lambda e: move_catcher(-CATCHER_MOVE_STEP))
root.bind("<Right>", lambda e: move_catcher(CATCHER_MOVE_STEP))
root.bind("<Escape>", show_pause_menu) # Bind Escape to Pause Menu
game_frame.bind("<Motion>", on_mouse_move)
game_frame.focus_set()

start_game()
root.mainloop()