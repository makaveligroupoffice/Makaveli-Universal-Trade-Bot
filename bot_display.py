import tkinter as tk
import json
import os
import time
import math
from config import Config

class BotDisplay:
    def __init__(self, root):
        self.root = root
        self.root.title("TradeBot HUD")
        self.root.overrideredirect(True)  # Remove window borders
        self.root.attributes("-topmost", True)  # Always on top
        # MacOS transparency: -transparent is boolean on some systems, let's use it properly
        # if the system allows. We also use alpha for a nice UI feel.
        try:
            self.root.attributes("-transparent", True)
        except:
            pass
        self.root.attributes("-alpha", 0.9)
        self.root.configure(bg="black")

        # MacOS specific: Make visible on all Spaces (home screens)
        # We use a trick for macOS to make the window a 'floating' utility window 
        # which usually stays on all desktops.
        try:
            # NSWindowCollectionBehaviorCanJoinAllSpaces = 1 << 0
            # We can use tcl/tk to set the collection behavior if available, 
            # but more reliably, setting the type to 'utility' or similar.
            self.root.tk.call('tk', '::tk::mac::useCustomAppearance', '1')
            self.root.attributes("-type", "panel")
        except:
            pass
        
        # Additionally, for macOS, we can set the collection behavior via Tcl
        try:
            self.root.tk.call('::tk::mac::setCollectionBehavior', self.root.winfo_id(), 1)
        except:
            pass

        # Window size and position
        self.width = 240
        self.height = 350
        self.root.geometry(f"{self.width}x{self.height}+100+100")

        # Make it draggable
        self.root.bind("<Button-1>", self.start_move)
        self.root.bind("<B1-Motion>", self.do_move)

        # UI Components
        self.canvas = tk.Canvas(root, width=self.width, height=250, bg="black", highlightthickness=0)
        self.canvas.pack()

        # --- Character Design (Complex Cyber-Bot) ---
        # Aura / Background Circuitry
        self.aura = []
        for i in range(5):
            r = 30 + (i * 15)
            a = self.canvas.create_oval(120-r, 100-r, 120+r, 100+r, outline="#003300", width=1, state="hidden")
            self.aura.append(a)

        # Head
        self.head = self.canvas.create_oval(90, 20, 150, 70, outline="#00FF00", width=2)
        # Scan-line on face
        self.scan_line = self.canvas.create_line(95, 45, 145, 45, fill="#00FF00", width=1, dash=(2, 2))
        
        # Eyes
        self.eye_l = self.canvas.create_oval(105, 35, 115, 45, fill="#00FF00", outline="")
        self.eye_r = self.canvas.create_oval(125, 35, 135, 45, fill="#00FF00", outline="")
        
        # Torso (Geometric Panel)
        self.torso = self.canvas.create_polygon(90, 75, 150, 75, 165, 150, 75, 150, outline="#00FF00", fill="black", width=2)
        # Chest Monitor (Data display on torso)
        self.chest_display = self.canvas.create_rectangle(100, 90, 140, 120, outline="#004400", fill="#001100")
        self.chest_text = self.canvas.create_text(120, 105, text="SYNC", fill="#00FF00", font=("Courier", 6))

        # Arms with Joints
        self.arm_l = self.canvas.create_line(90, 85, 60, 115, fill="#00FF00", width=3)
        self.arm_r = self.canvas.create_line(150, 85, 180, 115, fill="#00FF00", width=3)
        self.joint_l = self.canvas.create_oval(85, 80, 95, 90, fill="#00FF00", outline="")
        self.joint_r = self.canvas.create_oval(145, 80, 155, 90, fill="#00FF00", outline="")

        # Legs
        self.leg_l = self.canvas.create_line(100, 150, 90, 195, fill="#00FF00", width=3)
        self.leg_r = self.canvas.create_line(140, 150, 150, 195, fill="#00FF00", width=3)
        self.foot_l = self.canvas.create_oval(80, 190, 100, 200, outline="#00FF00", width=1)
        self.foot_r = self.canvas.create_oval(140, 190, 160, 200, outline="#00FF00", width=1)

        # Text labels
        self.lbl_pnl = tk.Label(root, text="Daily PnL: $0.00", fg="#00FF00", bg="black", font=("Courier", 12, "bold"))
        self.lbl_pnl.pack()
        
        self.lbl_status = tk.Label(root, text="Status: IDLE", fg="#AAAAAA", bg="black", font=("Courier", 10))
        self.lbl_status.pack()

        self.lbl_positions = tk.Label(root, text="Positions: 0", fg="#AAAAAA", bg="black", font=("Courier", 10))
        self.lbl_positions.pack()

        # New: Symbol detail
        self.lbl_active = tk.Label(root, text="SYMBOL: ---", fg="#555555", bg="black", font=("Courier", 8))
        self.lbl_active.pack()

        # Animation variables
        self.pulse_val = 0
        self.pulse_dir = 1
        self.blink_timer = 0
        self.breath_val = 0
        self.scan_val = 0
        self.aura_val = 0
        
        # State paths
        self.bot_state_path = Config.BOT_STATE_FILE
        self.risk_state_path = Config.RISK_STATE_FILE

        # --- Random Wandering Logic ---
        self.target_x = 100
        self.target_y = 100
        self.move_speed = 1.0 # Pixels per frame
        self.last_target_update = 0
        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()

        self.update_data()
        self.animate()

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        # Ensure it doesn't get lost off-screen (basic check)
        # MacOS screen sizes can vary, but we want it to be movable anywhere
        self.root.geometry(f"+{x}+{y}")
        # When manually moved, update targets to avoid 'snapping' back immediately
        self.target_x, self.target_y = x, y

    def animate(self):
        # 0. Random Movement (Wandering)
        import random
        now = time.time()
        if now - self.last_target_update > 5: # Pick a new target every 5 seconds
            # Keep away from edges
            self.target_x = random.randint(50, self.screen_w - self.width - 50)
            self.target_y = random.randint(50, self.screen_h - self.height - 50)
            self.last_target_update = now

        curr_x = self.root.winfo_x()
        curr_y = self.root.winfo_y()
        
        # Smoothly move towards target
        dx = self.target_x - curr_x
        dy = self.target_y - curr_y
        dist = math.sqrt(dx**2 + dy**2)
        
        if dist > 5: # Only move if far enough
            move_x = (dx / dist) * self.move_speed
            move_y = (dy / dist) * self.move_speed
            self.root.geometry(f"+{int(curr_x + move_x)}+{int(curr_y + move_y)}")

        # 1. Breathing effect (torso and arms)
        self.breath_val += 0.05
        offset = math.sin(self.breath_val) * 3
        
        # Update torso breathing
        self.canvas.coords(self.torso, 90, 75, 150, 75, 165 + offset, 150, 75 - offset, 150)
        
        # Update arms breathing
        self.canvas.coords(self.arm_l, 90, 85, 60 - offset, 115 + offset)
        self.canvas.coords(self.arm_r, 150, 85, 180 + offset, 115 + offset)
        self.canvas.coords(self.joint_l, 85 - offset*0.5, 80 - offset*0.5, 95 + offset*0.5, 90 + offset*0.5)
        self.canvas.coords(self.joint_r, 145 - offset*0.5, 80 - offset*0.5, 155 + offset*0.5, 90 + offset*0.5)

        # 2. Scanning effect on face
        self.scan_val += 0.1
        scan_offset = math.sin(self.scan_val) * 15
        self.canvas.coords(self.scan_line, 95, 45 + scan_offset, 145, 45 + scan_offset)

        # 3. Aura pulsing
        self.aura_val += 0.05
        for i, a in enumerate(self.aura):
            vis = "normal" if math.sin(self.aura_val + i) > 0.5 else "hidden"
            self.canvas.itemconfig(a, state=vis)

        # 4. Blinking effect
        self.blink_timer += 1
        if self.blink_timer > 60: # Blink every ~3 seconds
            if self.blink_timer < 65:
                self.canvas.itemconfig(self.eye_l, state="hidden")
                self.canvas.itemconfig(self.eye_r, state="hidden")
            else:
                self.canvas.itemconfig(self.eye_l, state="normal")
                self.canvas.itemconfig(self.eye_r, state="normal")
                self.blink_timer = 0

        # 5. Chest Monitor "Heartbeat" / Glitch
        if time.time() % 2 < 0.2:
            self.canvas.itemconfig(self.chest_text, text="SCAN")
        elif time.time() % 3 < 0.3:
            self.canvas.itemconfig(self.chest_text, text="LIVE")
        else:
            self.canvas.itemconfig(self.chest_text, text="SYNC")
        
        self.root.after(50, self.animate)

    def update_data(self):
        # Read Bot State
        try:
            if os.path.exists(self.bot_state_path):
                with open(self.bot_state_path, "r") as f:
                    bot_state = json.load(f)
                
                positions = bot_state.get("positions", {})
                num_pos = len(positions)
                self.lbl_positions.config(text=f"Positions: {num_pos}")
                
                if num_pos > 0:
                    symbols = ", ".join(list(positions.keys())[:2])
                    self.lbl_active.config(text=f"SYMBOLS: {symbols}", fg="#00FF00")
                    self.lbl_status.config(text="Status: ACTIVE", fg="#00FF00")
                else:
                    self.lbl_active.config(text="SYMBOL: ---", fg="#555555")
                    self.lbl_status.config(text="Status: SCANNING", fg="#AAAAAA")
        except:
            pass

        # Read Risk State
        try:
            if os.path.exists(self.risk_state_path):
                with open(self.risk_state_path, "r") as f:
                    risk_state = json.load(f)
                
                pnl = risk_state.get("daily_pnl", 0.0)
                
                color = "#00FF00" if pnl >= 0 else "#FF0000"
                dim_color = "#004400" if pnl >= 0 else "#440000"
                
                self.lbl_pnl.config(text=f"Daily PnL: ${pnl:.2f}", fg=color)
                
                # Apply color to the bot parts
                self.canvas.itemconfig(self.head, outline=color)
                self.canvas.itemconfig(self.scan_line, fill=color)
                self.canvas.itemconfig(self.eye_l, fill=color)
                self.canvas.itemconfig(self.eye_r, fill=color)
                self.canvas.itemconfig(self.torso, outline=color)
                self.canvas.itemconfig(self.chest_display, outline=dim_color)
                self.canvas.itemconfig(self.chest_text, fill=color)
                self.canvas.itemconfig(self.arm_l, fill=color)
                self.canvas.itemconfig(self.arm_r, fill=color)
                self.canvas.itemconfig(self.joint_l, fill=color)
                self.canvas.itemconfig(self.joint_r, fill=color)
                self.canvas.itemconfig(self.leg_l, fill=color)
                self.canvas.itemconfig(self.leg_r, fill=color)
                self.canvas.itemconfig(self.foot_l, outline=color)
                self.canvas.itemconfig(self.foot_r, outline=color)
                
                for a in self.aura:
                    self.canvas.itemconfig(a, outline=dim_color)
        except:
            pass

        self.root.after(2000, self.update_data) # Update every 2 seconds

if __name__ == "__main__":
    root = tk.Tk()
    app = BotDisplay(root)
    
    # Close button (tiny in corner)
    btn_close = tk.Button(root, text="X", command=root.destroy, bg="black", fg="white", bd=0, font=("Arial", 7))
    btn_close.place(x=225, y=0)

    root.mainloop()
