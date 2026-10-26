from datetime import datetime
import math
import tkinter as tk
from tkinter import messagebox, ttk

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Circle
import matplotlib.ticker as ticker

# --- ตั้งค่าฟอนต์ภาษาไทยสำหรับ Matplotlib ---
plt.rcParams['font.family'] = 'Tahoma'
plt.rcParams['axes.unicode_minus'] = False


# --- ส่วนการคำนวณทางดาราศาสตร์และฟิสิกส์ ---
def is_leap_year(year):
  return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def get_day_of_year(date_obj):
  if isinstance(date_obj, datetime):
    start_of_year = datetime(date_obj.year, 1, 1)
    return (date_obj - start_of_year).days + 1
  else:
    start_of_year = datetime(date_obj.year, 1, 1).date()
    return (date_obj - start_of_year).days + 1


def calculate_solar_time(clock_time_hours, lon, n):
  """คำนวณเวลาดวงอาทิตย์ (ST) จากเวลานาฬิกามาตรฐาน ลองจิจูด และลำดับวันในรอบปี (n)"""
  b_deg = 360.0 * (n - 81) / 364.0
  b_rad = math.radians(b_deg)

  # ค่าสมการเวลา E (นาที)
  e_minutes = (
      9.87 * math.sin(2 * b_rad)
      - 7.53 * math.cos(b_rad)
      - 1.5 * math.sin(b_rad)
  )

  # คำนวณ ST (ชั่วโมง)
  st = clock_time_hours + (4.0 * (lon - 105.0) + e_minutes) / 60.0
  return st, e_minutes


def calculate_shadow(lat, lon, date_obj, clock_time_hours, radius, height):
  """คำนวณตำแหน่งเงาตรงตามหลักดาราศาสตร์จริง"""
  n = get_day_of_year(date_obj)

  # 1. คำนวณ ST จากเวลานาฬิกาที่กรอก
  st, e_minutes = calculate_solar_time(clock_time_hours, lon, n)

  # 2. เดคลิเนชัน (delta)
  delta_rad = math.radians(23.45 * math.sin(math.radians((360 / 365) * (284 + n))))
  delta_deg = math.degrees(delta_rad)

  # 3. มุมชั่วโมง (omega)
  omega_deg = 15.0 * (st - 12.0)
  omega_rad = math.radians(omega_deg)

  lat_rad = math.radians(lat)

  # 4. มุมเงย (alpha)
  sin_alpha = math.sin(delta_rad) * math.sin(lat_rad) + math.cos(
      delta_rad
  ) * math.cos(lat_rad) * math.cos(omega_rad)
  sin_alpha = max(-1.0, min(1.0, sin_alpha))
  alpha_rad = math.asin(sin_alpha)
  alpha_deg = math.degrees(alpha_rad)

  if alpha_deg <= 0:
    return {
        "n": n,
        "st": st,
        "e_minutes": e_minutes,
        "delta": delta_deg,
        "omega": omega_deg,
        "alpha": alpha_deg,
        "psi": 0,
        "d": 0,
        "xc": 0,
        "yc": 0,
        "theta": 90,
        "sun_up": False,
    }

  # 5. มุมทิศดวงอาทิตย์จากทิศเหนือ (Solar Azimuth: 0=N, 90=E, 180=S, 270=W)
  cos_az = (math.sin(delta_rad) - math.sin(lat_rad) * math.sin(alpha_rad)) / (
      math.cos(lat_rad) * math.cos(alpha_rad)
  )
  cos_az = max(-1.0, min(1.0, cos_az))
  az_deg = math.degrees(math.acos(cos_az))

  if omega_deg > 0:  # ช่วงบ่าย ดวงอาทิตย์อยู่ทางทิศตะวันตก
    az_deg = 360.0 - az_deg

  az_rad = math.radians(az_deg)

  # 6. ระยะทางเงากึ่งกลาง d = h / tan(alpha)
  d = height / math.tan(alpha_rad)

  # 7. พิกัดกึ่งกลางเงา (xc, yc): ทิศทางเงาตรงข้ามกับดวงอาทิตย์ 180 องศา
  xc = -d * math.sin(az_rad)
  yc = -d * math.cos(az_rad)

  # 8. มุมตกกระทบแสงสำหรับร่มราบแนวระดับ theta = 90 - alpha
  theta_deg = 90.0 - alpha_deg

  # มุมทิศอ้างอิงจากทิศใต้สำหรับแสดงผล
  psi_deg = az_deg - 180.0 if az_deg >= 180 else az_deg + 180.0

  return {
      "n": n,
      "st": st,
      "e_minutes": e_minutes,
      "delta": delta_deg,
      "omega": omega_deg,
      "alpha": alpha_deg,
      "psi": psi_deg,
      "d": d,
      "xc": xc,
      "yc": yc,
      "theta": theta_deg,
      "sun_up": True,
  }


# --- ส่วนการสร้างหน้าจอโปรแกรม GUI ---
class UmbrellaShadowApp:

  def __init__(self, root):
    self.root = root
    self.root.title("โปรแกรมจำลองพิกัดตำแหน่งเงาของร่มสนาม (ราบแนวระดับ)")
    self.root.geometry("1420x920")

    self.is_animating = False
    self.anim_clock_hours = 7.0
    self.anim_job = None
    self.max_daily_bound = None

    main_frame = ttk.Frame(self.root, padding=10)
    main_frame.pack(fill=tk.BOTH, expand=True)

    left_frame = ttk.Frame(main_frame)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    right_frame = ttk.LabelFrame(
        main_frame, text=" แสดงค่ามุมและพิกัดเงา ", padding=15
    )
    right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

    # --- แบบจำลองกราฟิก (Matplotlib Plot) ---
    self.fig, self.ax = plt.subplots(figsize=(7.5, 6.0), dpi=100)
    self.canvas = FigureCanvasTkAgg(self.fig, master=left_frame)
    self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # --- ส่วนกล่องป้อนข้อมูลด้านล่าง ---
    input_frame = ttk.LabelFrame(
        left_frame, text=" กำหนดค่าตัวแปรจำลองและโหมดแสดงผล ", padding=12
    )
    input_frame.pack(fill=tk.X, pady=(10, 0))

    lbl_font = ("Tahoma", 10, "bold")
    entry_font = ("Tahoma", 10)

    # 1. แถบเลือกโหมด
    mode_frame = ttk.Frame(input_frame)
    mode_frame.grid(row=0, column=0, columnspan=8, sticky=tk.W, pady=(0, 8))

    ttk.Label(mode_frame, text="โหมดแสดงผล:", font=lbl_font).pack(
        side=tk.LEFT, padx=(0, 10)
    )
    self.mode_var = tk.StringVar(value="static")
    self.radio_static = ttk.Radiobutton(
        mode_frame,
        text="📍 ดู ณ เวลาที่กำหนด (Static)",
        variable=self.mode_var,
        value="static",
        command=self.on_mode_change,
    )
    self.radio_static.pack(side=tk.LEFT, padx=10)

    self.radio_anim = ttk.Radiobutton(
        mode_frame,
        text="🎬 แสดง Animation ตลอดวัน (07:00 - 17:00)",
        variable=self.mode_var,
        value="anim",
        command=self.on_mode_change,
    )
    self.radio_anim.pack(side=tk.LEFT, padx=10)

    # 2. แถวที่ 1: ละติจูด, ลองจิจูด, วันที่, ปุ่มคำนวณ
    ttk.Label(input_frame, text="ละติจูด (°N):", font=lbl_font).grid(
        row=1, column=0, sticky=tk.E, padx=4, pady=4
    )
    self.ent_lat = ttk.Entry(input_frame, width=9, font=entry_font)
    self.ent_lat.insert(0, "13.75")
    self.ent_lat.grid(row=1, column=1, padx=4, pady=4)

    ttk.Label(input_frame, text="ลองจิจูด (°E):", font=lbl_font).grid(
        row=1, column=2, sticky=tk.E, padx=4, pady=4
    )
    self.ent_lon = ttk.Entry(input_frame, width=9, font=entry_font)
    self.ent_lon.insert(0, "100.50")
    self.ent_lon.grid(row=1, column=3, padx=4, pady=4)

    ttk.Label(
        input_frame, text="วันที่ (วว/ดด/ปปปป):", font=lbl_font
    ).grid(row=1, column=4, sticky=tk.E, padx=4, pady=4)
    self.ent_date = ttk.Entry(input_frame, width=12, font=entry_font)
    self.ent_date.insert(0, "1/5/2026")
    self.ent_date.grid(row=1, column=5, padx=4, pady=4)

    # 3. แถวที่ 2: เวลานาฬิกา, รัศมีร่ม, ความสูงร่ม
    ttk.Label(input_frame, text="เวลานาฬิกา:", font=lbl_font).grid(
        row=2, column=0, sticky=tk.E, padx=4, pady=4
    )

    time_box = ttk.Frame(input_frame)
    time_box.grid(row=2, column=1, columnspan=3, sticky=tk.W, padx=4, pady=4)

    self.combo_hour = ttk.Combobox(
        time_box,
        values=[f"{h:02d}" for h in range(0, 24)],
        width=4,
        state="readonly",
        font=entry_font,
    )
    self.combo_hour.set("09")
    self.combo_hour.pack(side=tk.LEFT)

    ttk.Label(time_box, text=" : ", font=lbl_font).pack(side=tk.LEFT)

    self.combo_min = ttk.Combobox(
        time_box,
        values=[f"{m:02d}" for m in range(0, 60)],
        width=4,
        state="readonly",
        font=entry_font,
    )
    self.combo_min.set("00")
    self.combo_min.pack(side=tk.LEFT)

    ttk.Label(time_box, text=" น.", font=lbl_font).pack(side=tk.LEFT)

    ttk.Label(input_frame, text="รัศมีร่ม R (m):", font=lbl_font).grid(
        row=2, column=4, sticky=tk.E, padx=4, pady=4
    )
    self.ent_radius = ttk.Entry(input_frame, width=8, font=entry_font)
    self.ent_radius.insert(0, "2")
    self.ent_radius.grid(row=2, column=5, padx=4, pady=4)

    ttk.Label(input_frame, text="ความสูงร่ม h (m):", font=lbl_font).grid(
        row=2, column=6, sticky=tk.E, padx=4, pady=4
    )
    self.ent_height = ttk.Entry(input_frame, width=8, font=entry_font)
    self.ent_height.insert(0, "5")
    self.ent_height.grid(row=2, column=7, padx=4, pady=4)

    self.btn_action = tk.Button(
        input_frame,
        text="▶ คำนวณและแสดงผล",
        command=self.on_action_click,
        bg="#10b981",
        fg="white",
        font=("Tahoma", 10, "bold"),
        padx=10,
        pady=4,
        cursor="hand2",
    )
    self.btn_action.grid(
        row=1, column=6, columnspan=2, padx=6, pady=4, sticky="ew"
    )

    # --- ส่วนแสดงค่ามุม พิกัด ด้านขวามือ ---
    lbl_font_large = ("Tahoma", 11, "bold")

    self.lbl_n = ttk.Label(
        right_frame, text="ลำดับวันในรอบปี (n): -", font=lbl_font_large
    )
    self.lbl_n.pack(anchor=tk.W, pady=5)

    self.lbl_st_val = ttk.Label(
        right_frame,
        text="เวลาดวงอาทิตย์ (ST): - น.",
        font=lbl_font_large,
        foreground="darkgreen",
    )
    self.lbl_st_val.pack(anchor=tk.W, pady=5)

    self.lbl_delta = ttk.Label(
        right_frame, text="ค่าเดคลิเนชัน (δ): - °", font=lbl_font_large
    )
    self.lbl_delta.pack(anchor=tk.W, pady=5)

    self.lbl_omega = ttk.Label(
        right_frame, text="มุมชั่วโมง (omega): - °", font=lbl_font_large
    )
    self.lbl_omega.pack(anchor=tk.W, pady=5)

    self.lbl_alpha = ttk.Label(
        right_frame, text="มุมเงย (alpha): - °", font=lbl_font_large
    )
    self.lbl_alpha.pack(anchor=tk.W, pady=5)

    self.lbl_psi = ttk.Label(
        right_frame, text="มุมทิศ (psi): - °", font=lbl_font_large
    )
    self.lbl_psi.pack(anchor=tk.W, pady=5)

    self.lbl_theta = ttk.Label(
        right_frame, text="มุมตกกระทบ (theta): - °", font=lbl_font_large
    )
    self.lbl_theta.pack(anchor=tk.W, pady=5)

    self.lbl_d = ttk.Label(
        right_frame, text="ระยะทางเงา (d): - m", font=lbl_font_large
    )
    self.lbl_d.pack(anchor=tk.W, pady=5)

    ttk.Separator(right_frame, orient="horizontal").pack(fill=tk.X, pady=12)

    self.lbl_coords = ttk.Label(
        right_frame,
        text="พิกัดจุดกึ่งกลางเงา (x, y):\n( -, - ) m",
        font=("Tahoma", 13, "bold"),
        foreground="blue",
    )
    self.lbl_coords.pack(anchor=tk.W, pady=5)

    self.update_simulation()

  def on_mode_change(self):
    self.stop_animation()
    if self.mode_var.get() == "anim":
      self.combo_hour.config(state="disabled")
      self.combo_min.config(state="disabled")
      self.btn_action.config(text="🎬 เริ่มเล่น Animation", bg="#f59e0b")
    else:
      self.combo_hour.config(state="readonly")
      self.combo_min.config(state="readonly")
      self.btn_action.config(text="▶ คำนวณและแสดงผล", bg="#10b981")

  def on_action_click(self):
    if self.mode_var.get() == "static":
      self.stop_animation()
      self.max_daily_bound = None
      self.update_simulation()
    else:
      if self.is_animating:
        self.stop_animation()
      else:
        self.start_animation()

  def stop_animation(self):
    self.is_animating = False
    if self.anim_job:
      self.root.after_cancel(self.anim_job)
      self.anim_job = None
    if self.mode_var.get() == "anim":
      self.btn_action.config(text="🎬 เริ่มเล่น Animation", bg="#f59e0b")

  def calculate_max_bound_for_day(self, lat, lon, date_obj, radius, height):
    """หาขอบแกนกว้างที่สุดของวัน เพื่อใช้ล็อกสเกลแกนตารางถาวรใน Animation"""
    max_b = 6.0
    for h in range(7, 18):
      res = calculate_shadow(lat, lon, date_obj, float(h), radius, height)
      if res["sun_up"]:
        ext_x = abs(res["xc"]) + radius
        ext_y = abs(res["yc"]) + radius
        max_b = max(max_b, ext_x + 3.0, ext_y + 3.0)
    return max_b

  def start_animation(self):
    try:
      lat = float(self.ent_lat.get())
      lon = float(self.ent_lon.get())
      date_str = self.ent_date.get()
      radius = float(self.ent_radius.get())
      height = float(self.ent_height.get())
      day, month, year = map(int, date_str.split("/"))
      date_obj = datetime(year, month, day)

      self.max_daily_bound = self.calculate_max_bound_for_day(
          lat, lon, date_obj, radius, height
      )
    except Exception:
      messagebox.showerror(
          "ข้อผิดพลาด", "กรุณากรอกข้อมูลให้ถูกต้องก่อนเริ่ม Animation"
      )
      return

    self.is_animating = True
    self.btn_action.config(text="⏹ หยุด Animation", bg="#ef4444")
    self.anim_clock_hours = 7.0
    self.run_animation_step()

  def run_animation_step(self):
    if not self.is_animating:
      return

    h_int = int(self.anim_clock_hours)
    m_int = int(round((self.anim_clock_hours - h_int) * 60))

    self.combo_hour.config(state="normal")
    self.combo_min.config(state="normal")
    self.combo_hour.set(f"{h_int:02d}")
    self.combo_min.set(f"{m_int:02d}")
    self.combo_hour.config(state="disabled")
    self.combo_min.config(state="disabled")

    success = self.update_simulation(
        override_clock_hours=self.anim_clock_hours,
        fixed_bound=self.max_daily_bound,
    )

    if not success:
      self.stop_animation()
      return

    self.anim_clock_hours += 0.1  # เพิ่มทีละ 6 นาที
    if self.anim_clock_hours > 17.05:
      self.anim_clock_hours = 7.0

    self.anim_job = self.root.after(50, self.run_animation_step)

  def update_simulation(self, override_clock_hours=None, fixed_bound=None):
    try:
      lat = float(self.ent_lat.get())
      lon = float(self.ent_lon.get())
      date_str = self.ent_date.get()

      if override_clock_hours is not None:
        clock_time_hours = override_clock_hours
      else:
        h = float(self.combo_hour.get())
        m = float(self.combo_min.get())
        clock_time_hours = h + (m / 60.0)

      radius = float(self.ent_radius.get())
      height = float(self.ent_height.get())

      day, month, year = map(int, date_str.split("/"))
      date_obj = datetime(year, month, day)
    except Exception:
      messagebox.showerror(
          "ข้อผิดพลาด",
          "กรุณากรอกข้อมูลให้ถูกต้อง\nเช่น วันที่ รูปแบบ DD/MM/YYYY",
      )
      return False

    res = calculate_shadow(lat, lon, date_obj, clock_time_hours, radius, height)

    # แปลง ST เป็นรูปแบบ ชั่วโมง:นาที สำหรับแสดงผล
    st_val = res["st"]
    st_h = int(st_val)
    st_m = int(round((st_val - st_h) * 60))
    if st_m == 60:
      st_h += 1
      st_m = 0

    clock_h = int(clock_time_hours)
    clock_m = int(round((clock_time_hours - clock_h) * 60))
    if clock_m == 60:
      clock_h += 1
      clock_m = 0

    # อัปเดตข้อมูลแผงขวามือ
    self.lbl_n.config(text=f"ลำดับวันในรอบปี (n): {res['n']} วัน")
    self.lbl_st_val.config(
        text=(
            f"เวลาดวงอาทิตย์ (ST): {st_h:02d}:{st_m:02d} น. ({res['st']:.2f}"
            " ชม.)"
        )
    )
    self.lbl_delta.config(text=f"ค่าเดคลิเนชัน (δ): {res['delta']:.2f}°")
    self.lbl_omega.config(text=f"มุมชั่วโมง (omega): {res['omega']:.2f}°")
    self.lbl_alpha.config(text=f"มุมเงย (alpha): {res['alpha']:.2f}°")
    self.lbl_psi.config(text=f"มุมทิศ (psi): {res['psi']:.2f}°")
    self.lbl_theta.config(text=f"มุมตกกระทบ (theta): {res['theta']:.2f}°")
    self.lbl_d.config(text=f"ระยะทางเงา (d): {res['d']:.2f} m")

    self.lbl_coords.config(
        text=(
            f"พิกัดจุดกึ่งกลางเงา (x, y):\n({res['xc']:.2f}, {res['yc']:.2f}) m"
        )
    )

    # --- วาดกราฟแบบจำลอง (2D Top-View Plot) ---
    self.ax.clear()

    # โคนเสาร่ม (จุดสีดำ)
    self.ax.plot(
        0, 0, "ko", markersize=7, label="ตำแหน่งเสาร่ม (0, 0)", zorder=5
    )

    # พื้นที่ผืนร่มสนาม (วงกลม)
    umbrella_circle = Circle(
        (0, 0),
        radius,
        color="deepskyblue",
        alpha=0.45,
        label="พื้นที่ผืนร่ม",
        zorder=4,
    )
    self.ax.add_patch(umbrella_circle)

    if res["sun_up"]:
      # วาดเงาบนพื้นสำหรับร่มกางแนวระดับ (วงกลมขนาดเท่าผืนร่ม)
      shadow_circle = Circle(
          (res["xc"], res["yc"]),
          radius,
          color="gray",
          alpha=0.55,
          label="พื้นที่เงาบนพื้น",
          zorder=2,
      )
      self.ax.add_patch(shadow_circle)

      # จุดกึ่งกลางเงา (จุดสีแดง 'ro')
      self.ax.plot(
          res["xc"],
          res["yc"],
          "ro",
          markersize=7,
          label=f"จุดกึ่งกลางเงา ({res['xc']:.2f}, {res['yc']:.2f})",
          zorder=6,
      )

      # ป้ายบอกพิกัด
      self.ax.text(
          res["xc"] + 0.4,
          res["yc"] + 0.4,
          f"({res['xc']:.2f}, {res['yc']:.2f})",
          fontsize=10,
          fontweight="bold",
          color="darkred",
          bbox=dict(
              boxstyle="round,pad=0.25",
              facecolor="white",
              edgecolor="red",
              alpha=0.85,
          ),
          zorder=7,
      )

      # เส้นรังสีเชื่อมโคนเสากับจุดกึ่งกลางเงา
      self.ax.plot(
          [0, res["xc"]],
          [0, res["yc"]],
          "r--",
          linewidth=1.2,
          alpha=0.75,
          zorder=3,
      )

    # --- การคำนวณและล็อกขอบเขตแกนตารางถาวร ---
    if fixed_bound is not None:
      max_bound = fixed_bound
    else:
      shadow_extent_x = abs(res["xc"]) + radius if res["sun_up"] else radius
      shadow_extent_y = abs(res["yc"]) + radius if res["sun_up"] else radius
      max_bound = max(6.0, shadow_extent_x + 3.0, shadow_extent_y + 3.0)

    self.ax.set_xlim(-max_bound, max_bound)
    self.ax.set_ylim(-max_bound, max_bound)
    self.ax.set_aspect("equal")

    if max_bound <= 15:
      step_major, step_minor = 2.0, 1.0
    elif max_bound <= 35:
      step_major, step_minor = 5.0, 1.0
    else:
      step_major, step_minor = 10.0, 2.0

    self.ax.xaxis.set_major_locator(ticker.MultipleLocator(step_major))
    self.ax.yaxis.set_major_locator(ticker.MultipleLocator(step_major))
    self.ax.xaxis.set_minor_locator(ticker.MultipleLocator(step_minor))
    self.ax.yaxis.set_minor_locator(ticker.MultipleLocator(step_minor))

    self.ax.grid(
        True, which="major", color="gray", linestyle="--", alpha=0.5, linewidth=0.8
    )
    self.ax.grid(
        True,
        which="minor",
        color="gainsboro",
        linestyle=":",
        alpha=0.7,
        linewidth=0.6,
    )

    self.ax.axhline(0, color="black", linewidth=1.0)
    self.ax.axvline(0, color="black", linewidth=1.0)

    text_margin = max_bound * 0.92
    self.ax.text(
        0,
        text_margin,
        "N",
        horizontalalignment="center",
        verticalalignment="center",
        fontweight="bold",
        fontsize=12,
        bbox=dict(
            boxstyle="circle,pad=0.2", facecolor="white", edgecolor="none"
        ),
    )
    self.ax.text(
        0,
        -text_margin,
        "S",
        horizontalalignment="center",
        verticalalignment="center",
        fontweight="bold",
        fontsize=12,
        bbox=dict(
            boxstyle="circle,pad=0.2", facecolor="white", edgecolor="none"
        ),
    )
    self.ax.text(
        text_margin,
        0,
        "E",
        horizontalalignment="center",
        verticalalignment="center",
        fontweight="bold",
        fontsize=12,
        bbox=dict(
            boxstyle="circle,pad=0.2", facecolor="white", edgecolor="none"
        ),
    )
    self.ax.text(
        -text_margin,
        0,
        "W",
        horizontalalignment="center",
        verticalalignment="center",
        fontweight="bold",
        fontsize=12,
        bbox=dict(
            boxstyle="circle,pad=0.2", facecolor="white", edgecolor="none"
        ),
    )

    self.ax.set_xlabel(
        "ทิศตะวันออก (+X) / ทิศตะวันตก (-X) [เมตร]",
        fontweight="bold",
        fontsize=10,
    )
    self.ax.set_ylabel(
        "ทิศเหนือ (+Y) / ทิศใต้ (-Y) [เมตร]", fontweight="bold", fontsize=10
    )

    self.ax.set_title(
        f"แบบจำลองตำแหน่งเงา (เวลานาฬิกา {clock_h:02d}:{clock_m:02d} น. | ST ="
        f" {st_h:02d}:{st_m:02d} น.)",
        fontsize=12,
        fontweight="bold",
        pad=10,
    )
    self.ax.legend(loc="upper right", fontsize=8.5, framealpha=0.9)

    self.fig.tight_layout()
    self.canvas.draw()
    return True


if __name__ == "__main__":
  root = tk.Tk()
  app = UmbrellaShadowApp(root)
  root.mainloop()