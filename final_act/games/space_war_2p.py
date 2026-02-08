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
root.title("2D Space Battle - 2 Players")

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

# Game Constants
PLAYER_SIZE = 30
ENEMY_SIZE = 25
PLAYER_SPEED = 10
BULLET_SPEED = 30
ENEMY_BULLET_SPEED = 6
GAME_TICK_MS = 20

LEVELS = [
    {'score_threshold': 0, 'enemy_health': 1, 'enemy_speed': 2.0, 'fire_power': 1, 'spawn_interval': 2900, 'enemy_count_base': 2, 'enemy_cooldown_min': 100, 'enemy_cooldown_max': 200},
    {'score_threshold': 20, 'enemy_health': 1, 'enemy_speed': 3.5, 'fire_power': 2, 'spawn_interval': 2000, 'enemy_count_base': 3, 'enemy_cooldown_min': 80, 'enemy_cooldown_max': 160},
    {'score_threshold': 50, 'enemy_health': 2, 'enemy_speed': 4.5, 'fire_power': 3, 'spawn_interval': 1500, 'enemy_count_base': 4, 'enemy_cooldown_min': 50, 'enemy_cooldown_max': 100}
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
        # Removed old escape binding, handled in show_pause_menu
        self.root.bind("<Escape>", self.show_pause_menu)
        
        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg='#050515', highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.after_ids = {}
        self.high_score_p1 = {'score': 0, 'level': 1}
        self.high_score_p2 = {'score': 0, 'level': 1}

        root.bind('<KeyPress>', self.on_key_press)
        root.bind('<KeyRelease>', self.on_key_release)

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
        final_score = max(self.score_p1, self.score_p2)
        if final_score == 0: return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            query = "INSERT INTO game_scores (user_id, game_name, score, timestamp, is_deleted) VALUES (%s, %s, %s, NOW(), 0)"
            cursor.execute(query, (CURRENT_USER_ID, "Space War 2P", final_score))
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
        self.score_p1 = 0
        self.score_p2 = 0
        self.endless_mode = False
        self.last_endless_boss_score = None

        self._set_level_parameters()

        self.player1 = {'x': WIDTH // 2 - 100, 'y': HEIGHT - 80, 'size': PLAYER_SIZE, 'health': 5, 'cooldown': 0, 'thruster_state': 0}
        self.player2 = {'x': WIDTH // 2 + 100, 'y': HEIGHT - 80, 'size': PLAYER_SIZE, 'health': 5, 'cooldown': 0, 'thruster_state': 0}

        self.bullets = []
        self.enemies = []
        self.enemy_bullets = []
        self.explosions = []
        self.bosses = []
        self.keys = set()
        
        self.boss_spawned_for_level = False
        self.boss_announce_timer = 0  
        self.endless_announce_timer = 0  

        self.canvas.delete('all')
        self._start_loops()

    def _start_loops(self):
        if not self.paused:
            self._schedule_spawn()
            self._game_loop()

    def _cancel_loops(self):
        for name, id_ in list(self.after_ids.items()):
            try: self.root.after_cancel(id_)
            except ValueError: pass
            self.after_ids.pop(name, None)

    def on_key_press(self, event):
        key = event.keysym
        low = key.lower()
        # 'p' handling removed in favor of ESC menu, but can keep if you want both
        if low == 'p': self.show_pause_menu()
        self.keys.add(key)
        self.keys.add(low)

    def on_key_release(self, event):
        key = event.keysym
        low = key.lower()
        self.keys.discard(key)
        self.keys.discard(low)

    def _set_level_parameters(self):
        if self.level > 3: self.level = 3
        idx = min(self.level - 1, len(LEVELS) - 1)
        params = LEVELS[idx]
        self.enemy_health_base = params['enemy_health']
        self.enemy_speed_base = params['enemy_speed']
        self.fire_power = params['fire_power']
        self.spawn_interval = params['spawn_interval']
        self.enemy_count_base = params['enemy_count_base']
        self.enemy_cooldown_min = params['enemy_cooldown_min']
        self.enemy_cooldown_max = params['enemy_cooldown_max']

    def get_next_level_threshold(self):
        if self.level < len(LEVELS): return LEVELS[self.level]['score_threshold']
        else: return LEVELS[-1]['score_threshold'] + 25  

    def _schedule_spawn(self):
        if self.paused or not self.running: return
        self.spawn_enemy_wave()
        id_ = self.root.after(self.spawn_interval, self._schedule_spawn)
        self.after_ids['_schedule_spawn'] = id_

    def spawn_enemy_wave(self):
        for _ in range(self.enemy_count_base):
            x = random.randint(40, WIDTH - 40)
            y = random.randint(-200, -40)
            enemy = {'x': x, 'y': y, 'size': ENEMY_SIZE, 'health': self.enemy_health_base, 'speed': self.enemy_speed_base, 'cooldown': random.randint(self.enemy_cooldown_min, self.enemy_cooldown_max)}
            self.enemies.append(enemy)

    def spawn_boss_wave(self):
        self.bosses = []
        for idx in range(2):
            x = WIDTH // 3 * (idx + 1)
            boss_health = max(5, self.enemy_health_base * 5)
            boss = {'x': x, 'y': -80, 'size': 60, 'health': boss_health, 'max_health': boss_health, 'speed': max(1.5, self.enemy_speed_base * 0.6), 'cooldown': random.randint(40, 90)}
            self.bosses.append(boss)
        self.boss_announce_timer = 80  

    def _game_loop(self):
        if self.paused or not self.running: return
        self.update()
        self.render()
        id_ = self.root.after(GAME_TICK_MS, self._game_loop)
        self.after_ids['_game_loop'] = id_

    def all_players_dead(self):
        return self.player1['health'] <= 0 and self.player2['health'] <= 0

    def check_game_over(self):
        if self.running and self.all_players_dead(): self.game_over()

    def update(self):
        self.player1['thruster_state'] = (self.player1['thruster_state'] + 1) % 4
        self.player2['thruster_state'] = (self.player2['thruster_state'] + 1) % 4

        if self.boss_announce_timer > 0: self.boss_announce_timer -= 1
        if self.endless_announce_timer > 0: self.endless_announce_timer -= 1

        dx1 = dy1 = dx2 = dy2 = 0
        if self.player1['health'] > 0:
            if 'a' in self.keys: dx1 -= PLAYER_SPEED
            if 'd' in self.keys: dx1 += PLAYER_SPEED
            if 'w' in self.keys: dy1 -= PLAYER_SPEED
            if 's' in self.keys: dy1 += PLAYER_SPEED

        if self.player2['health'] > 0:
            if 'Left' in self.keys or 'left' in self.keys: dx2 -= PLAYER_SPEED
            if 'Right' in self.keys or 'right' in self.keys: dx2 += PLAYER_SPEED
            if 'Up' in self.keys or 'up' in self.keys: dy2 -= PLAYER_SPEED
            if 'Down' in self.keys or 'down' in self.keys: dy2 += PLAYER_SPEED

        for p, dx, dy in [(self.player1, dx1, dy1), (self.player2, dx2, dy2)]:
            p['x'] = max(p['size']//2, min(WIDTH - p['size']//2, p['x'] + dx))
            p['y'] = max(p['size']//2, min(HEIGHT - p['size']//2, p['y'] + dy))

        if self.player1['health'] > 0 and self.player1['cooldown'] <= 0:
            if 'space' in self.keys:
                self.player_shoot(self.player1, owner_id=1, color='lime')
                self.player1['cooldown'] = 10

        if self.player2['health'] > 0 and self.player2['cooldown'] <= 0:
            if 'Return' in self.keys or 'return' in self.keys:
                self.player_shoot(self.player2, owner_id=2, color='cyan')
                self.player2['cooldown'] = 10

        if self.player1['cooldown'] > 0: self.player1['cooldown'] -= 1
        if self.player2['cooldown'] > 0: self.player2['cooldown'] -= 1

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
                e['cooldown'] = random.randint(self.enemy_cooldown_min, self.enemy_cooldown_max)
            if e['y'] > HEIGHT + 40: self.enemies.remove(e)

        for boss in list(self.bosses):
            boss['y'] += boss['speed']
            boss['cooldown'] -= 1
            if boss['cooldown'] <= 0:
                self.enemy_shoot(boss)
                boss['cooldown'] = random.randint(30, 70)
            if boss['y'] > HEIGHT + 100: self.bosses.remove(boss)

        for b in list(self.bullets):
            hit = False
            for e in list(self.enemies):
                if rect_collision({'x': b['x'], 'y': b['y'], 'size': 6}, e):
                    e['health'] -= 1
                    if b in self.bullets: self.bullets.remove(b)
                    if e['health'] <= 0: self.enemy_destroyed(e, b['owner'])
                    hit = True
                    break
            if hit: continue
            for boss in list(self.bosses):
                if rect_collision({'x': b['x'], 'y': b['y'], 'size': 6}, boss):
                    boss['health'] -= 1
                    if b in self.bullets: self.bullets.remove(b)
                    if boss['health'] <= 0: self.boss_destroyed(boss, b['owner'])
                    break

        for b in list(self.enemy_bullets):
            hit_any = False
            for player in (self.player1, self.player2):
                if player['health'] > 0 and rect_collision({'x': b['x'], 'y': b['y'], 'size': 8}, player):
                    if b in self.enemy_bullets: self.enemy_bullets.remove(b)
                    player['health'] -= 1
                    self.create_explosion(player['x'], player['y'], 2)
                    self.check_game_over()
                    hit_any = True
                    break
            if hit_any: break

        for e in list(self.enemies):
            for player in (self.player1, self.player2):
                if player['health'] > 0 and rect_collision(e, player):
                    if e in self.enemies: self.enemies.remove(e)
                    player['health'] -= 1
                    self.create_explosion(e['x'], e['y'], 5)
                    self.check_game_over()
                    break

        for boss in list(self.bosses):
            for player in (self.player1, self.player2):
                if player['health'] > 0 and rect_collision(boss, player):
                    if boss in self.bosses: self.bosses.remove(boss)
                    player['health'] -= 1
                    self.create_explosion(boss['x'], boss['y'], 10)
                    self.check_game_over()
                    break

        if not self.endless_mode:
            next_threshold = self.get_next_level_threshold()
            if (not self.boss_spawned_for_level) and self.score >= next_threshold:
                self.boss_spawned_for_level = True
                self.spawn_boss_wave()
            if self.boss_spawned_for_level and len(self.bosses) == 0 and self.score >= next_threshold:
                if self.level < 3:
                    self.level += 1
                    self._set_level_parameters()
                    self.boss_spawned_for_level = False
                    self.boss_announce_timer = 0
                else:
                    self.endless_mode = True
                    self.boss_spawned_for_level = False
                    self.endless_announce_timer = 120  
                    self.last_endless_boss_score = self.score
        else:
            if len(self.bosses) == 0:
                if self.last_endless_boss_score is None: self.last_endless_boss_score = self.score
                if self.score - self.last_endless_boss_score >= 30:
                    self.spawn_boss_wave()
                    self.last_endless_boss_score = self.score

    def player_shoot(self, player, owner_id, color):
        spread = 10
        for i in range(self.fire_power):
            offset = (i - (self.fire_power - 1) / 2) * spread
            bullet = {'x': player['x'] + offset, 'y': player['y'] - player['size'] // 2, 'size': 6, 'color': color, 'owner': owner_id}
            self.bullets.append(bullet)

    def enemy_shoot(self, enemy):
        bullet = {'x': enemy['x'], 'y': enemy['y'] + enemy['size'] // 2 + 6, 'size': 8, 'color': 'red'}
        self.enemy_bullets.append(bullet)

    def enemy_destroyed(self, enemy, owner_id):
        if enemy in self.enemies: self.enemies.remove(enemy)
        self.score += 1
        if owner_id == 1: self.score_p1 += 1
        elif owner_id == 2: self.score_p2 += 1
        self.create_explosion(enemy['x'], enemy['y'], 8)

    def boss_destroyed(self, boss, owner_id):
        if boss in self.bosses: self.bosses.remove(boss)
        points = 5
        self.score += points
        if owner_id == 1: self.score_p1 += points
        elif owner_id == 2: self.score_p2 += points
        self.create_explosion(boss['x'], boss['y'], 15)

    def create_explosion(self, x, y, magnitude):
        self.explosions.append({'x': x, 'y': y, 'radius': 1, 'life': magnitude, 'max_radius': magnitude * 5})

    def game_over(self):
        self.running = False
        self._cancel_loops()
        self.save_score_to_db()

        if self.score_p1 > self.score_p2: result_text = "Player 1 Wins!"
        elif self.score_p2 > self.score_p1: result_text = "Player 2 Wins!"
        else: result_text = "It's a Tie!"

        self.canvas.create_text(WIDTH // 2, HEIGHT // 2 - 40, text='GAME OVER', fill='red', font=('Consolas', 32))
        self.canvas.create_text(WIDTH // 2, HEIGHT // 2, text=f'P1: {self.score_p1} | P2: {self.score_p2}', fill='white', font=('Consolas', 18))
        self.canvas.create_text(WIDTH // 2, HEIGHT // 2 + 65, text=result_text, fill='yellow', font=('Consolas', 20))
        self.canvas.create_text(WIDTH // 2, HEIGHT // 2 + 100, text='Press R to Restart or ESC to Menu', fill='cyan', font=('Consolas', 18))

        self.root.bind('r', self.restart)

    def restart(self, event=None):
        self.root.unbind('r')
        self._setup_game()

    def _draw_player_ship(self, x, y, s, color):
        hull = [x, y - s, x - s/2, y + s/3, x + s/2, y + s/3]
        self.canvas.create_polygon(hull, fill=color, outline='#33CCFF', width=2)
        self.canvas.create_oval(x - 5, y - s/2 - 5, x + 5, y - s/2 + 5, fill='white')
        
        thruster_len = 5 
        self.canvas.create_rectangle(x - 10, y + s/3, x - 5, y + s/3 + thruster_len, fill='red', outline='')
        self.canvas.create_rectangle(x + 5, y + s/3, x + 10, y + s/3 + thruster_len, fill='red', outline='')

    def _draw_enemy_ship(self, x, y, s):
        self.canvas.create_oval(x - s/2, y - s/2, x + s/2, y + s/2, fill='#8B0000', outline='#FF4500', width=2)
        self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill='yellow')
        self.canvas.create_line(x - s/2, y, x - s/2 - 5, y + 5, fill='red', width=2)
        self.canvas.create_line(x + s/2, y, x + s/2 + 5, y + 5, fill='red', width=2)

    def _draw_boss_ship(self, x, y, s):
        self.canvas.create_oval(x - s/2, y - s/2, x + s/2, y + s/2, fill='#4B0082', outline='#DA70D6', width=3)
        self.canvas.create_oval(x - 10, y - 10, x + 10, y + 10, fill='orange')

    def _draw_explosion(self, exp):
        r = 255
        g = min(255, int(255 * (exp['life'] / 8)))
        b = 0
        color_hex = f'#{r:02x}{g:02x}{b:02x}'
        self.canvas.create_oval(
            exp['x'] - exp['radius'], exp['y'] - exp['radius'],
            exp['x'] + exp['radius'], exp['y'] + exp['radius'],
            fill=color_hex, outline='yellow'
        )

    def render(self):
        self.canvas.delete('all')
        for i in range(100):
            x = (i * 23 + (self.score * 5)) % WIDTH
            y = (i * 47 + (self.level * 7)) % HEIGHT
            self.canvas.create_rectangle(x, y, x + 1, y + 1, fill='white')

        for exp in self.explosions: self._draw_explosion(exp)

        if self.player1['health'] > 0: self._draw_player_ship(self.player1['x'], self.player1['y'], self.player1['size'], '#00BFFF')
        if self.player2['health'] > 0: self._draw_player_ship(self.player2['x'], self.player2['y'], self.player2['size'], '#32CD32')

        self.canvas.create_text(10, HEIGHT - 28, anchor='w', text='P1 HEALTH:', fill='lime', font=('Consolas', 12))
        for i in range(self.player1['health']):
            self.canvas.create_rectangle(90 + i * 22, HEIGHT - 36, 90 + 18 + i * 22, HEIGHT - 20, fill='lime', outline='white')

        self.canvas.create_text(WIDTH - 10, HEIGHT - 28, anchor='e', text='P2 HEALTH:', fill='cyan', font=('Consolas', 12))
        for i in range(self.player2['health']):
            x2 = WIDTH - 90 - i * 22
            self.canvas.create_rectangle(x2 - 18, HEIGHT - 36, x2, HEIGHT - 20, fill='cyan', outline='white')

        for e in self.enemies: self._draw_enemy_ship(e['x'], e['y'], e['size'])
        for boss in self.bosses: self._draw_boss_ship(boss['x'], boss['y'], boss['size'])
        for b in self.bullets: self.canvas.create_rectangle(b['x'] - 2, b['y'] - 6, b['x'] + 2, b['y'] + 6, fill=b['color'], outline=b['color'])
        for b in self.enemy_bullets: self.canvas.create_oval(b['x'] - 4, b['y'] - 4, b['x'] + 4, b['y'] + 4, fill=b['color'], outline='yellow')

        level_label = f'LEVEL: {self.level}'
        if self.endless_mode: level_label += ' (ENDLESS)'
        stats_text = f'P1: {self.score_p1} | P2: {self.score_p2} | {level_label} | ENEMIES: {len(self.enemies)}'
        self.canvas.create_text(12, 12, anchor='nw', fill='cyan', font=('Consolas', 14), text=stats_text)
        controls_text = 'P1: WASD+Space | P2: Arrows+Enter | ESC: Pause Menu'
        self.canvas.create_text(WIDTH - 12, 32, anchor='ne', fill='lightgray', font=('Consolas', 12), text=controls_text)

        if self.boss_announce_timer > 0: self.canvas.create_text(WIDTH // 2, 70, text='BOSS INCOMING!', fill='magenta', font=('Consolas', 26))
        if self.endless_announce_timer > 0: self.canvas.create_text(WIDTH // 2, 110, text='ENDLESS MODE!', fill='orange', font=('Consolas', 24))

if __name__ == '__main__':
    game = WarGame(root)
    root.mainloop()