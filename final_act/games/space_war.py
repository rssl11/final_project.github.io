import tkinter as tk
from tkinter import messagebox
import random
import sys
import os
import mysql.connector

# --- DATABASE SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

try:
    from db_config import get_db_connection
except ImportError:
    def get_db_connection():
        return mysql.connector.connect(host="localhost", user="root", password="", database="authallica")

CURRENT_USER_ID = sys.argv[1] if len(sys.argv) > 1 else None

# --- WINDOW SETUP ---
root = tk.Tk()
root.title("Space War (Single Player)")

root.lift()
root.attributes('-topmost', True)
root.after_idle(root.attributes, '-topmost', False)
root.focus_force()

try:
    root.state('zoomed')
except:
    w, h = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{w}x{h}+0+0")

WIDTH = root.winfo_screenwidth()
HEIGHT = root.winfo_screenheight() - 80

# Constants
PLAYER_SIZE = 30
ENEMY_SIZE = 25
PLAYER_SPEED = 12
BULLET_SPEED = 30
ENEMY_BULLET_SPEED = 7
GAME_TICK_MS = 20

# Levels
LEVELS = [
    {'score_threshold': 0, 'enemy_health': 1, 'enemy_speed': 2.5, 'fire_power': 1, 'spawn_interval': 2500, 'enemy_count_base': 3},
    {'score_threshold': 20, 'enemy_health': 1, 'enemy_speed': 4.0, 'fire_power': 2, 'spawn_interval': 1800, 'enemy_count_base': 4},
    {'score_threshold': 50, 'enemy_health': 2, 'enemy_speed': 5.5, 'fire_power': 3, 'spawn_interval': 1200, 'enemy_count_base': 5}
]

def rect_collision(a, b):
    ax1, ay1 = a['x'] - a['size']/2, a['y'] - a['size']/2
    ax2, ay2 = a['x'] + a['size']/2, a['y'] + a['size']/2
    bx1, by1 = b['x'] - b['size']/2, b['y'] - b['size']/2
    bx2, by2 = b['x'] + b['size']/2, b['y'] + b['size']/2
    return not (ax2 < bx1 or ax1 > bx2 or ay2 < by1 or ay1 > by2)

class WarGame:
    def __init__(self, root):
        self.root = root
        self.root.bind("<Escape>", self.show_pause_menu)
        
        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg='#050515', highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.after_ids = {}
        
        root.bind('<KeyPress>', self.on_key_press)
        root.bind('<KeyRelease>', self.on_key_release)
        self.canvas.bind('<Button-1>', self.on_mouse_click)
        
        self._setup_game()

    def show_pause_menu(self, event=None):
        if not self.running: return
        
        self.paused = True
        
        menu_win = tk.Toplevel(self.root)
        menu_win.title("Paused")
        
        # Center Window
        ww, wh = 300, 250
        cx = self.root.winfo_x() + (self.root.winfo_width() // 2) - (ww // 2)
        cy = self.root.winfo_y() + (self.root.winfo_height() // 2) - (wh // 2)
        menu_win.geometry(f"{ww}x{wh}+{cx}+{cy}")
        
        menu_win.config(bg='#1F1A33')
        menu_win.grab_set()
        menu_win.overrideredirect(True)
        
        # Frame
        f = tk.Frame(menu_win, bg='#1F1A33', bd=2, relief='groove')
        f.pack(fill='both', expand=True, padx=2, pady=2)
        
        tk.Label(f, text="GAME PAUSED", font=('Consolas', 20, 'bold'), fg='#E900FF', bg='#1F1A33').pack(pady=20)
        
        btn_style = {"font": ('Consolas', 12, 'bold'), "bg": "#00F0FF", "fg": "#1F1A33", "width": 15, "bd": 0}
        
        def resume():
            self.paused = False
            self.pause_text = None
            self.canvas.delete("pause_overlay")
            menu_win.destroy()
            self._start_loops() # Restart loops

        def retry():
            menu_win.destroy()
            self._setup_game()

        def exit_game():
            self.root.destroy()
            sys.exit()

        tk.Button(f, text="RESUME", command=resume, **btn_style).pack(pady=5)
        tk.Button(f, text="RETRY", command=retry, **btn_style).pack(pady=5)
        tk.Button(f, text="EXIT TO MENU", command=exit_game, **btn_style).pack(pady=5)

    def save_score_to_db(self):
        if not CURRENT_USER_ID: return
        if self.score == 0: return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            # Note: game_name is "Space War" here
            query = "INSERT INTO game_scores (user_id, game_name, score, timestamp, is_deleted) VALUES (%s, %s, %s, NOW(), 0)"
            cursor.execute(query, (CURRENT_USER_ID, "Space War", self.score))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"DB Error: {e}")

    def _setup_game(self):
        self.running = True
        self.paused = False
        self.score = 0
        self.level = 1
        
        self._set_level_parameters()
        
        self.player = {
            'x': WIDTH // 2,
            'y': HEIGHT - 60,
            'size': PLAYER_SIZE,
            'health': 5,
            'cooldown': 0,
            'thruster_state': 0 
        }
        
        self.bullets = []
        self.enemies = []
        self.enemy_bullets = []
        self.explosions = []
        self.keys = set()
        
        self.canvas.delete('all')
        self.pause_text = None
        self._start_loops()

    def _start_loops(self):
        if not self.paused:
            self._schedule_spawn()
            self._game_loop()
        
    def _cancel_loops(self):
        for name, id in list(self.after_ids.items()):
            try: self.root.after_cancel(id)
            except ValueError: pass
            self.after_ids.pop(name, None)

    def on_mouse_click(self, event):
        if not self.paused and self.running and self.player['cooldown'] <= 0:
            self.player_shoot()
            self.player['cooldown'] = 10

    def on_key_press(self, event):
        key = event.keysym.lower()
        if key == 'p': self.show_pause_menu()
        self.keys.add(key)

    def on_key_release(self, event):
        key = event.keysym.lower()
        if key in self.keys:
            self.keys.remove(key)

    def _set_level_parameters(self):
        idx = min(self.level - 1, len(LEVELS) - 1)
        params = LEVELS[idx]
        self.enemy_health_base = params['enemy_health']
        self.enemy_speed_base = params['enemy_speed']
        self.fire_power = params['fire_power']
        self.spawn_interval = params['spawn_interval']
        self.enemy_count_base = params['enemy_count_base']
        
        # Infinite scaling if level > defined levels
        if self.level > len(LEVELS):
            extra = self.level - len(LEVELS)
            self.spawn_interval = max(500, int(self.spawn_interval * (0.9 ** extra)))
            self.fire_power = min(5, self.fire_power + extra // 2)
            self.enemy_speed_base += 0.5 * extra

    def _schedule_spawn(self):
        if self.paused or not self.running: return
        self.spawn_enemy_wave()
        id = self.root.after(self.spawn_interval, self._schedule_spawn)
        self.after_ids['_schedule_spawn'] = id

    def spawn_enemy_wave(self):
        for i in range(self.enemy_count_base):
            x = random.randint(40, WIDTH - 40)
            y = random.randint(-200, -40)
            enemy = {
                'x': x, 'y': y, 'size': ENEMY_SIZE,
                'health': self.enemy_health_base,
                'speed': self.enemy_speed_base,
                'cooldown': random.randint(50, 150)
            }
            self.enemies.append(enemy)

    def _game_loop(self):
        if self.paused or not self.running: return
        self.update()
        self.render()
        id = self.root.after(GAME_TICK_MS, self._game_loop)
        self.after_ids['_game_loop'] = id

    def update(self):
        dx, dy = 0, 0
        self.player['thruster_state'] = (self.player['thruster_state'] + 1) % 4 
        
        if 'left' in self.keys or 'a' in self.keys: dx -= PLAYER_SPEED
        if 'right' in self.keys or 'd' in self.keys: dx += PLAYER_SPEED
        if 'up' in self.keys or 'w' in self.keys: dy -= PLAYER_SPEED
        if 'down' in self.keys or 's' in self.keys: dy += PLAYER_SPEED
            
        self.player['x'] = max(self.player['size']//2, min(WIDTH - self.player['size']//2, self.player['x'] + dx))
        self.player['y'] = max(self.player['size']//2, min(HEIGHT - self.player['size']//2, self.player['y'] + dy))
        
        if ('space' in self.keys or 'z' in self.keys) and self.player['cooldown'] <= 0:
            self.player_shoot()
            self.player['cooldown'] = 10
            
        if self.player['cooldown'] > 0: self.player['cooldown'] -= 1
            
        for exp in list(self.explosions):
            exp['radius'] += 2 
            exp['life'] -= 1
            if exp['life'] <= 0: self.explosions.remove(exp)

        for b in list(self.bullets):
            b['y'] -= BULLET_SPEED
            if b['y'] < -10: self.bullets.remove(b)
                
        for b in list(self.enemy_bullets):
            b['y'] += ENEMY_BULLET_SPEED
            if b['y'] > HEIGHT + 10: self.enemy_bullets.remove(b)
                
        for e in list(self.enemies):
            e['y'] += e['speed']
            e['cooldown'] -= 1
            if e['cooldown'] <= 0:
                self.enemy_shoot(e)
                e['cooldown'] = random.randint(50, 150)
            if e['y'] > HEIGHT + 40: self.enemies.remove(e)
                
        # Bullet vs Enemy
        for b in list(self.bullets):
            hit = False
            for e in list(self.enemies):
                if rect_collision({'x': b['x'], 'y': b['y'], 'size': 6}, e):
                    e['health'] -= 1
                    if b in self.bullets: self.bullets.remove(b)
                    if e['health'] <= 0: self.enemy_destroyed(e)
                    hit = True
                    break
            if hit: continue
                    
        # Enemy Bullet vs Player
        for b in list(self.enemy_bullets):
            if rect_collision({'x': b['x'], 'y': b['y'], 'size': 8}, self.player):
                if b in self.enemy_bullets: self.enemy_bullets.remove(b)
                self.player['health'] -= 1
                self.create_explosion(self.player['x'], self.player['y'], 2) 
                if self.player['health'] <= 0: self.game_over()
                break
        
        # Enemy vs Player (Crash)
        for e in list(self.enemies):
            if rect_collision(e, self.player):
                if e in self.enemies: self.enemies.remove(e)
                self.player['health'] -= 1
                self.create_explosion(e['x'], e['y'], 5) 
                if self.player['health'] <= 0: self.game_over()
                    
        # Level Logic
        if self.level < len(LEVELS):
            next_thresh = LEVELS[self.level]['score_threshold']
            if self.score >= next_thresh:
                self.level += 1
                self._set_level_parameters()
        elif self.score > LEVELS[-1]['score_threshold']:
             # Simple infinite scaling
             if (self.score - LEVELS[-1]['score_threshold']) % 30 == 0:
                 self.level += 1
                 self._set_level_parameters()

    def player_shoot(self):
        spread = 10
        for i in range(self.fire_power):
            offset = (i - (self.fire_power - 1) / 2) * spread
            bullet = {'x': self.player['x'] + offset, 'y': self.player['y'] - self.player['size']//2, 'size': 6, 'color': 'lime'}
            self.bullets.append(bullet)

    def enemy_shoot(self, enemy):
        bullet = {'x': enemy['x'], 'y': enemy['y'] + enemy['size']//2 + 6, 'size': 8, 'color': 'red'}
        self.enemy_bullets.append(bullet)

    def enemy_destroyed(self, enemy):
        if enemy in self.enemies: self.enemies.remove(enemy)
        self.score += 1
        self.create_explosion(enemy['x'], enemy['y'], 8) 

    def create_explosion(self, x, y, magnitude):
        self.explosions.append({'x': x, 'y': y, 'radius': 1, 'life': magnitude, 'max_radius': magnitude * 5})

    def game_over(self):
        self.running = False
        self._cancel_loops() 
        self.save_score_to_db()
        
        self.canvas.create_text(WIDTH//2, HEIGHT//2 - 40, text='GAME OVER', fill='red', font=('Consolas', 46))
        self.canvas.create_text(WIDTH//2, HEIGHT//2 + 20, text=f'Score: {self.score}', fill='white', font=('Consolas', 24))
        self.canvas.create_text(WIDTH//2, HEIGHT//2 + 60, text='Press R to Restart or ESC to Menu', fill='yellow', font=('Consolas', 18))
        
        self.root.bind('r', self.restart) 

    def restart(self, event=None):
        self.root.unbind('r')
        self._setup_game()

    def render(self):
        self.canvas.delete('all')
        
        # Stars
        for i in range(60): 
            x = (i * 37 + (self.score * 2)) % WIDTH
            y = (i * 19 + (self.level * 5)) % HEIGHT
            self.canvas.create_rectangle(x, y, x+2, y+2, fill='white')

        for exp in self.explosions:
            r = 255
            g = min(255, int(255 * (exp['life'] / 8)))
            color = f'#{r:02x}{g:02x}00'
            self.canvas.create_oval(exp['x']-exp['radius'], exp['y']-exp['radius'], exp['x']+exp['radius'], exp['y']+exp['radius'], fill=color, outline='yellow')

        # Player
        x, y, s = self.player['x'], self.player['y'], self.player['size']
        hull = [x, y - s, x - s/2, y + s/3, x + s/2, y + s/3]
        self.canvas.create_polygon(hull, fill='#00BFFF', outline='#33CCFF', width=2)
        self.canvas.create_oval(x-5, y-s/2-5, x+5, y-s/2+5, fill='white')
        
        # Health Bar (Top Right)
        self.canvas.create_text(WIDTH-120, 20, text='HEALTH:', fill='lime', font=('Consolas', 12), anchor='e')
        for i in range(self.player['health']):
            self.canvas.create_rectangle(WIDTH-110 + i*22, 10, WIDTH-110 + 18 + i*22, 26, fill='lime', outline='white')

        # Enemies
        for e in self.enemies:
            self.canvas.create_oval(e['x']-e['size']/2, e['y']-e['size']/2, e['x']+e['size']/2, e['y']+e['size']/2, fill='#8B0000', outline='red', width=2)
            
        # Bullets
        for b in self.bullets:
            self.canvas.create_rectangle(b['x']-2, b['y']-6, b['x']+2, b['y']+6, fill='lime', outline='')
            
        for b in self.enemy_bullets:
            self.canvas.create_oval(b['x']-4, b['y']-4, b['x']+4, b['y']+4, fill='red', outline='yellow')
            
        # HUD
        hud = f'SCORE: {self.score} | LEVEL: {self.level} | ENEMIES: {len(self.enemies)}'
        self.canvas.create_text(20, 20, anchor='nw', fill='cyan', font=('Consolas', 14), text=hud)

if __name__ == '__main__':
    game = WarGame(root)
    root.mainloop()