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

        # Window size and position
        self.width = 240
        self.height = 300
        self.root.geometry(f"{self.width}x{self.height}+100+100")

        # Make it draggable
        self.root.bind("<Button-1>", self.start_move)
        self.root.bind("<B1-Motion>", self.do_move)

        # UI Components
        self.canvas = tk.Canvas(root, width=self.width, height=200, bg="black", highlightthickness=0)
        self.canvas.pack()

        # --- Character Design (Full Figured Bot) ---
        # Head
        self.head = self.canvas.create_oval(90, 20, 150, 70, outline="#00FF00", width=2)
        # Eyes
        self.eye_l = self.canvas.create_oval(105, 35, 115, 45, fill="#00FF00", outline="")
        self.eye_r = self.canvas.create_oval(125, 35, 135, 45, fill="#00FF00", outline="")
        # Torso
        self.torso = self.canvas.create_polygon(90, 75, 150, 75, 160, 140, 80, 140, outline="#00FF00", fill="black", width=2)
        # Arms
        self.arm_l = self.canvas.create_line(90, 85, 60, 110, fill="#00FF00", width=3)
        self.arm_r = self.canvas.create_line(150, 85, 180, 110, fill="#00FF00", width=3)
        # Legs
        self.leg_l = self.canvas.create_line(100, 140, 95, 180, fill="#00FF00", width=3)
        self.leg_r = self.canvas.create_line(140, 140, 145, 180, fill="#00FF00", width=3)

        # Text labels
        self.lbl_pnl = tk.Label(root, text="Daily PnL: $0.00", fg="#00FF00", bg="black", font=("Courier", 12, "bold"))
        self.lbl_pnl.pack()
        
        self.lbl_status = tk.Label(root, text="Status: IDLE", fg="#AAAAAA", bg="black", font=("Courier", 10))
        self.lbl_status.pack()

        self.lbl_positions = tk.Label(root, text="Positions: 0", fg="#AAAAAA", bg="black", font=("Courier", 10))
        self.lbl_positions.pack()

        # Animation variables
        self.pulse_val = 0
        self.pulse_dir = 1
        self.blink_timer = 0
        self.breath_val = 0
        
        # State paths
        self.bot_state_path = Config.BOT_STATE_FILE
        self.risk_state_path = Config.RISK_STATE_FILE

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
        self.root.geometry(f"+{x}+{y}")

    def animate(self):
        # 1. Breathing effect (torso and arms)
        self.breath_val += 0.05
        offset = math.sin(self.breath_val) * 3
        
        # Update torso breathing
        self.canvas.coords(self.torso, 90, 75, 150, 75, 160 + offset, 140, 80 - offset, 140)
        
        # Update arms breathing
        self.canvas.coords(self.arm_l, 90, 85, 60 - offset, 110 + offset)
        self.canvas.coords(self.arm_r, 150, 85, 180 + offset, 110 + offset)

        # 2. Blinking effect
        self.blink_timer += 1
        if self.blink_timer > 50: # Blink every ~2.5 seconds
            if self.blink_timer < 55: # Blink lasts 5 frames
                self.canvas.itemconfig(self.eye_l, state="hidden")
                self.canvas.itemconfig(self.eye_r, state="hidden")
            else:
                self.canvas.itemconfig(self.eye_l, state="normal")
                self.canvas.itemconfig(self.eye_r, state="normal")
                self.blink_timer = 0

        # 3. Pulse effect (eyes glow)
        self.pulse_val += 0.1 * self.pulse_dir
        if self.pulse_val >= 1 or self.pulse_val <= 0:
            self.pulse_dir *= -1
        
        # Color intensity based on pulse could be added here if we used hex colors dynamically
        
        self.root.after(50, self.animate)

    def update_data(self):
        # Read Bot State
        try:
            if os.path.exists(self.bot_state_path):
                with open(self.bot_state_path, "r") as f:
                    bot_state = json.load(f)
                num_pos = len(bot_state.get("positions", {}))
                self.lbl_positions.config(text=f"Positions: {num_pos}")
                if num_pos > 0:
                    self.lbl_status.config(text="Status: ACTIVE", fg="#00FF00")
                else:
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
                self.lbl_pnl.config(text=f"Daily PnL: ${pnl:.2f}", fg=color)
                
                # Apply color to the bot parts
                self.canvas.itemconfig(self.head, outline=color)
                self.canvas.itemconfig(self.eye_l, fill=color)
                self.canvas.itemconfig(self.eye_r, fill=color)
                self.canvas.itemconfig(self.torso, outline=color)
                self.canvas.itemconfig(self.arm_l, fill=color)
                self.canvas.itemconfig(self.arm_r, fill=color)
                self.canvas.itemconfig(self.leg_l, fill=color)
                self.canvas.itemconfig(self.leg_r, fill=color)
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
