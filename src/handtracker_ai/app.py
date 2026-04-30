from __future__ import annotations
import tkinter as tk
from pathlib import Path

import customtkinter as ctk
import cv2
from PIL import Image, ImageTk

from .action_controller import ActionController
from .config import AppConfig
from .hand_tracker import HandTracker


ASSETS_DIR = Path(__file__).resolve().parent / "pngfortutor"


PALETTE = {
    # Backgrounds — deep navy-black
    "bg":              "#030309",
    "bg_mid":          "#060610",
    "surface":         "#09091A",
    "surface_raised":  "#0D0D22",

    # Glass
    "glass":           "#0B0B1E",
    "glass_rim":       "#141430",
    "glass_highlight": "#1A1A3E",

    # Borders
    "border":          "#1C1C48",
    "border_soft":     "#282868",
    "border_glow":     "#5B4DCE",

    # Typography
    "text":            "#F0EFFF",
    "text_secondary":  "#B5B0D8",
    "text_muted":      "#6A659A",
    "text_dim":        "#3A3660",

    # Primary accent — electric violet
    "accent":          "#9B7DFF",
    "accent_dim":      "#7B5CE0",
    "accent_deep":     "#160E38",
    "accent_glow":     "#B09AFF",

    # Secondary accent — electric cyan
    "blue":            "#22D3EE",
    "blue_dim":        "#0EA5E9",
    "blue_deep":       "#081826",

    # Semantic
    "success":         "#34D399",
    "success_dim":     "#10B981",
    "warning":         "#FBBF24",
    "danger":          "#FB7185",

    # Button tones
    "btn_primary":     "#7C3AED",
    "btn_primary_fg":  "#FFFFFF",
    "btn_secondary":   "#0D0D22",
    "btn_secondary_h": "#171736",

    # Glow layers — violet-tinted darks for ambient background
    "glow_a":          "#080618",
    "glow_b":          "#0E0B26",
    "glow_c":          "#161038",
    "glow_d":          "#1F1550",
    "glow_e":          "#2A1E68",
    "glow_spot":       "#3D2C90",
}

TUTORIAL_STEPS = [
    {
        "title": "Движение курсора",
        "subtitle": "Открытая ладонь",
        "body": (
            "Покажите открытую ладонь в камеру. "
            "Положение указательного пальца используется как цель для курсора."
        ),
        "image": ASSETS_DIR / "openpalm.png",
        "icon": "✋",
    },
    {
        "title": "Клик щепоткой",
        "subtitle": "Pinch",
        "body": (
            "Сведите большой и указательный палец вместе. "
            "Когда жест распознан уверенно, приложение выполняет левый клик."
        ),
        "image": ASSETS_DIR / "pinchclick.png",
        "icon": "🤏",
    },
    {
        "title": "Управление системой",
        "subtitle": "Свайпы и кулак",
        "body": (
            "Свайпы переключают рабочие столы, "
            "а кулак ставит медиа на паузу или снимает с паузы."
        ),
        "image": ASSETS_DIR / "swape.png",
        "icon": "✊",
    },
    {
        "title": "Громкость вниз",
        "subtitle": "Thumbs down",
        "body": (
            "Опустите большой палец вниз, держа остальные пальцы собранными. "
            "Когда жест распознан, приложение уменьшает системную громкость."
        ),
        "image": ASSETS_DIR / "volumedown.png",
        "icon": "👎",
    },
    {
        "title": "Прокрутка вверх",
        "subtitle": "Два пальца вверх",
        "body": (
            "Поднимите указательный и средний пальцы и сделайте короткое "
            "движение рукой вверх. Это запускает прокрутку страницы вверх."
        ),
        "image": ASSETS_DIR / "twofingersup.png",
        "icon": "☝️",
    },
    {
        "title": "Прокрутка вниз",
        "subtitle": "Два пальца вниз",
        "body": (
            "С тем же положением двух пальцев сделайте короткое движение "
            "рукой вниз. Это запускает прокрутку страницы вниз."
        ),
        "image": ASSETS_DIR / "twofingersdown.png",
        "icon": "👇",
    },
]


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _lerp_color(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


# ──────────────────────────────────────────────────────────────────────────────
# APP
# ──────────────────────────────────────────────────────────────────────────────

class GestureControlApp:
    def __init__(self, config: AppConfig | None = None) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.config = config or AppConfig()
        self.root = ctk.CTk()
        self.root.title(self.config.window_title)
        self.root.geometry("1480x920")
        self.root.minsize(1200, 800)
        self.root.configure(fg_color=PALETTE["bg"])

        self._tracker = HandTracker(self.config)
        self._actions = ActionController(
            cooldown_seconds=self.config.gesture.command_cooldown_seconds,
            shutdown_hold_seconds=self.config.gesture.shutdown_hold_seconds,
        )

        self._image_handle = None
        self._tutorial_index = 0
        self._tutorial_images: dict[Path, ctk.CTkImage] = {}

        self._active = tk.BooleanVar(value=False)
        self._last_action   = tk.StringVar(value="ожидание жеста")
        self._last_gesture  = tk.StringVar(value="нет")
        self._latency       = tk.StringVar(value="0 мс")
        self._confidence    = tk.StringVar(value="0%")
        self._ai_state      = tk.StringVar(value="ожидание")
        self._hand_state    = tk.StringVar(value="рука не найдена")
        self._pointer_state = tk.StringVar(value="курсор неактивен")
        self._engine_mode   = tk.StringVar(value="только просмотр")
        self._camera_profile = tk.StringVar(
            value=(
                f"{self.config.camera.width}×{self.config.camera.height}"
                f"  {self.config.camera.fps_hint} FPS"
            )
        )
        self._detail_text = tk.StringVar(
            value=(
                "Камера захватывает кадр, модель выделяет ключевые точки руки, "
                "затем движок определяет жест и запускает действие."
            )
        )

        self._background_canvas: tk.Canvas | None = None
        self._background_redraw_job: str | None = None
        self._page_transition_job: str | None = None
        self._pulse_job: str | None = None
        self._pulse_phase: float = 0.0

        self._build_ui()
        self.root.bind("<Configure>", self._schedule_background_redraw)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _glass_card(
        self,
        parent,
        *,
        fg_color: str | None = None,
        corner_radius: int = 20,
        border_color: str | None = None,
    ) -> ctk.CTkFrame:
        return ctk.CTkFrame(
            parent,
            fg_color=fg_color or PALETTE["glass"],
            corner_radius=corner_radius,
            border_width=1,
            border_color=border_color or PALETTE["border"],
        )

    def _label(
        self,
        parent,
        text: str = "",
        *,
        textvariable=None,
        size: int = 13,
        weight: str = "normal",
        color: str | None = None,
        wraplength: int = 0,
        justify: str = "left",
        anchor: str = "w",
    ) -> ctk.CTkLabel:
        kw = dict(
            fg_color="transparent",
            text_color=color or PALETTE["text"],
            font=ctk.CTkFont(size=size, weight=weight),
            justify=justify,
            anchor=anchor,
        )
        if wraplength:
            kw["wraplength"] = wraplength
        if textvariable is not None:
            kw["textvariable"] = textvariable
        else:
            kw["text"] = text
        return ctk.CTkLabel(parent, **kw)

    def _primary_button(
        self,
        parent,
        text: str,
        width: int = 150,
        height: int = 42,
    ) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=text,
            fg_color=PALETTE["btn_primary"],
            hover_color=PALETTE["accent_dim"],
            text_color=PALETTE["btn_primary_fg"],
            corner_radius=14,
            width=width,
            height=height,
            font=ctk.CTkFont(size=13, weight="bold"),
        )

    def _secondary_button(
        self,
        parent,
        text: str,
        width: int = 150,
        height: int = 42,
    ) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=text,
            fg_color=PALETTE["btn_secondary"],
            hover_color=PALETTE["btn_secondary_h"],
            text_color=PALETTE["text_secondary"],
            corner_radius=14,
            border_width=1,
            border_color=PALETTE["border"],
            width=width,
            height=height,
            font=ctk.CTkFont(size=13),
        )


    def _schedule_background_redraw(self, event: tk.Event | None = None) -> None:
        if event is not None and event.widget is not self.root:
            return
        if self._background_redraw_job is not None:
            self.root.after_cancel(self._background_redraw_job)
        self._background_redraw_job = self.root.after(16, self._draw_background_glow)

    def _draw_background_glow(self) -> None:
        self._background_redraw_job = None
        if self._background_canvas is None:
            return

        W = max(self.root.winfo_width(), 1200)
        H = max(self.root.winfo_height(), 800)
        c = self._background_canvas
        c.delete("all")
        c.configure(width=W, height=H, bg=PALETTE["bg"])
        c.create_rectangle(0, 0, W, H, fill=PALETTE["bg"], outline="")

        # Subtle scanline texture — very slight violet tint
        for y in range(0, H, 4):
            alpha_band = "#050410" if (y // 4) % 2 == 0 else PALETTE["bg"]
            c.create_line(0, y, W, y, fill=alpha_band, width=1)

        # Top center — large violet/purple ambient halo
        cx, cy = W * 0.5, H * 0.06
        for r, col in [
            (520, "#080618"),
            (390, "#0E0B26"),
            (270, "#161038"),
            (165, "#1F1550"),
            (90,  "#2A1E68"),
            (42,  "#3D2C90"),
        ]:
            c.create_oval(cx - r, cy - r * 0.55, cx + r, cy + r * 0.55,
                          fill=col, outline="", stipple="gray25")

        # Bottom right — cyan/teal accent halo
        cx2, cy2 = W * 0.88, H * 0.84
        for r, col in [
            (340, "#040C18"),
            (235, "#07131E"),
            (145, "#0B1D2E"),
            (75,  "#10283E"),
            (34,  "#163448"),
        ]:
            c.create_oval(cx2 - r, cy2 - r * 0.65, cx2 + r, cy2 + r * 0.65,
                          fill=col, outline="", stipple="gray25")

        # Left edge — subtle magenta/rose depth accent
        cx3, cy3 = W * 0.0, H * 0.5
        for r, col in [
            (210, "#0E0614"),
            (125, "#16091E"),
            (62,  "#200D28"),
        ]:
            c.create_oval(cx3 - r, cy3 - r * 1.6, cx3 + r, cy3 + r * 1.6,
                          fill=col, outline="", stipple="gray25")

        # Diagonal accent line — top: vivid violet
        c.create_line(
            W * 0.0,  H * 0.30,
            W * 0.38, H * 0.12,
            W * 0.72, H * 0.22,
            W * 1.02, H * 0.08,
            smooth=True, splinesteps=40,
            fill=PALETTE["border_glow"], width=1,
        )

        # Diagonal accent line — bottom: dark cyan
        c.create_line(
            W * -0.02, H * 0.88,
            W * 0.25,  H * 0.72,
            W * 0.60,  H * 0.84,
            W * 1.02,  H * 0.65,
            smooth=True, splinesteps=40,
            fill="#163448", width=1,
        )

        # Vertical fade strip — left edge
        for x_off, col in [(0, "#060410"), (30, "#090818"), (60, PALETTE["bg"])]:
            c.create_rectangle(x_off, 0, x_off + 30, H, fill=col, outline="")

    # ── main layout ───────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # Background layer
        self._background_canvas = tk.Canvas(
            self.root, highlightthickness=0, bd=0, bg=PALETTE["bg"]
        )
        self._background_canvas.grid(row=0, column=0, sticky="nsew")
        self._draw_background_glow()

        # Main glass shell
        shell = ctk.CTkFrame(
            self.root,
            fg_color=PALETTE["surface"],
            corner_radius=24,
            border_width=1,
            border_color=PALETTE["border_glow"],
        )
        shell.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        shell.lift()
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(1, weight=1)

        self.pages: dict[str, ctk.CTkFrame] = {}
        self.nav_buttons: dict[str, ctk.CTkButton] = {}

        self._build_header(shell)

        self.page_host = ctk.CTkFrame(shell, fg_color="transparent")
        self.page_host.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.page_host.grid_columnconfigure(0, weight=1)
        self.page_host.grid_rowconfigure(0, weight=1)

        self._build_welcome_page()
        self._build_tutorial_page()
        self._build_dashboard_page()
        self._show_page("welcome")

    # ── header ────────────────────────────────────────────────────────────────

    def _build_header(self, parent: ctk.CTkFrame) -> None:
        header = ctk.CTkFrame(
            parent,
            fg_color=PALETTE["surface_raised"],
            corner_radius=0,
            border_width=0,
        )
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(1, weight=1)

        # ── Brand ──
        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w", padx=(22, 0), pady=16)

        # Animated dot (color will pulse via _pulse_dot)
        self._brand_dot = ctk.CTkLabel(
            brand,
            text="⬡",
            text_color=PALETTE["accent"],
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        self._brand_dot.pack(side="left")

        ctk.CTkLabel(
            brand,
            text="HandTracker",
            text_color=PALETTE["text"],
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left", padx=(8, 0))

        ctk.CTkLabel(
            brand,
            text="  AI",
            text_color=PALETTE["accent"],
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left")

        ctk.CTkLabel(
            brand,
            text="  v2",
            text_color=PALETTE["text_muted"],
            font=ctk.CTkFont(size=11),
        ).pack(side="left", pady=(4, 0))

        # ── Nav ──
        nav_shell = ctk.CTkFrame(
            header,
            fg_color=PALETTE["glass"],
            corner_radius=12,
            border_width=1,
            border_color=PALETTE["border"],
        )
        nav_shell.grid(row=0, column=1, pady=14)

        for page_id, icon, title in (
            ("welcome",   "⊹",  "Старт"),
            ("tutorial",  "◈",  "Обучение"),
            ("dashboard", "⬡",  "Панель"),
        ):
            btn = ctk.CTkButton(
                nav_shell,
                text=f"{icon}  {title}",
                fg_color="transparent",
                hover_color=PALETTE["glass_highlight"],
                text_color=PALETTE["text_secondary"],
                corner_radius=10,
                border_width=0,
                width=120,
                height=34,
                font=ctk.CTkFont(size=13),
            )
            btn.configure(
                command=lambda pid=page_id, b=btn: self._animate_button_press(
                    b,
                    lambda pid=pid: self._show_page(pid),
                    pressed_color=PALETTE["accent_deep"],
                    normal_color="transparent",
                )
            )
            btn.pack(side="left", padx=3, pady=4)
            self.nav_buttons[page_id] = btn

        # ── Mode badge ──
        badge = ctk.CTkFrame(
            header,
            fg_color=PALETTE["glass"],
            corner_radius=10,
            border_width=1,
            border_color=PALETTE["border"],
        )
        badge.grid(row=0, column=2, sticky="e", padx=(0, 22), pady=16)

        ctk.CTkLabel(
            badge,
            textvariable=self._engine_mode,
            text_color=PALETTE["accent"],
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(padx=12, pady=6)

        # thin accent line under header
        sep = tk.Frame(parent, bg=PALETTE["border_glow"], height=1)
        sep.grid(row=0, column=0, sticky="sew", padx=0)

        self._start_pulse()

    def _start_pulse(self) -> None:
        self._pulse_phase = 0.0
        self._pulse_dot()

    def _pulse_dot(self) -> None:
        self._pulse_phase = (self._pulse_phase + 0.04) % (3.14159 * 2)
        import math
        t = (math.sin(self._pulse_phase) + 1) / 2          # 0..1
        color = _lerp_color(PALETTE["accent_dim"], PALETTE["accent"], t)
        try:
            self._brand_dot.configure(text_color=color)
        except tk.TclError:
            return
        self._pulse_job = self.root.after(40, self._pulse_dot)

    # ── WELCOME PAGE ──────────────────────────────────────────────────────────

    def _build_welcome_page(self) -> None:
        page = ctk.CTkFrame(self.page_host, fg_color="transparent")
        page.grid(row=0, column=0, sticky="nsew")
        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=2)
        page.grid_rowconfigure(0, weight=1)
        self.pages["welcome"] = page

        # ── Left hero ──
        left = ctk.CTkFrame(page, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.grid_rowconfigure(3, weight=1)

        # Eyebrow
        eyebrow = ctk.CTkFrame(left, fg_color=PALETTE["accent_deep"], corner_radius=8)
        eyebrow.pack(anchor="w", padx=28, pady=(42, 0))
        ctk.CTkLabel(
            eyebrow,
            text="  ◈  GESTURE CONTROL  ◈  ",
            text_color=PALETTE["accent"],
            font=ctk.CTkFont(size=10, weight="bold"),
        ).pack(padx=4, pady=5)

        self._label(
            left, "Управляйте\nкомпьютером\nжестами",
            size=46, weight="bold",
        ).pack(anchor="w", padx=28, pady=(14, 0))

        self._label(
            left,
            "Без мыши. Без клавиатуры.\nТолько ваши руки и камера.",
            size=16, color=PALETTE["text_secondary"],
        ).pack(anchor="w", padx=28, pady=(10, 28))

        # CTA buttons
        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.pack(anchor="w", padx=28, pady=(0, 32))

        start_btn = self._primary_button(btn_row, "⊹  Обучение", width=170, height=46)
        start_btn.configure(
            command=lambda: self._animate_button_press(
                start_btn,
                lambda: self._show_page("tutorial"),
                pressed_color=PALETTE["accent_dim"],
                normal_color=PALETTE["btn_primary"],
            )
        )
        start_btn.pack(side="left", padx=(0, 12))

        skip_btn = self._secondary_button(btn_row, "⬡  В панель", width=150, height=46)
        skip_btn.configure(
            command=lambda: self._animate_button_press(
                skip_btn,
                lambda: self._show_page("dashboard"),
                pressed_color=PALETTE["accent_deep"],
                normal_color=PALETTE["btn_secondary"],
            )
        )
        skip_btn.pack(side="left")

        # Feature chips
        chip_row = ctk.CTkFrame(left, fg_color="transparent")
        chip_row.pack(anchor="w", padx=28)

        for icon, text in [("◈", "MediaPipe"), ("⊹", "Real-time"), ("⬡", "macOS")]:
            chip = ctk.CTkFrame(
                chip_row,
                fg_color=PALETTE["glass"],
                corner_radius=10,
                border_width=1,
                border_color=PALETTE["border"],
            )
            chip.pack(side="left", padx=(0, 8))
            ctk.CTkLabel(
                chip,
                text=f" {icon} {text} ",
                text_color=PALETTE["text_secondary"],
                font=ctk.CTkFont(size=12),
            ).pack(padx=6, pady=6)

        # ── Right info card ──
        right = self._glass_card(page, corner_radius=22)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right.grid_rowconfigure(2, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkFrame(
            right, fg_color=PALETTE["border_glow"], height=2, corner_radius=1
        ).grid(row=0, column=0, sticky="ew", padx=0, pady=0)

        self._label(
            right, "Как начать", size=20, weight="bold"
        ).grid(row=1, column=0, sticky="w", padx=22, pady=(20, 0))

        steps_frame = ctk.CTkFrame(right, fg_color="transparent")
        steps_frame.grid(row=2, column=0, sticky="nsew", padx=22, pady=(14, 22))

        for num, heading, desc in [
            ("01", "Обучение жестам",  "Посмотрите все доступные жесты в разделе Обучение"),
            ("02", "Откройте панель",  "Перейдите в Панель управления и разрешите доступ к камере"),
            ("03", "Включите режим",   "Активируйте чекбокс — система начнёт слушать жесты"),
            ("04", "Управляйте",       "Используйте жесты для управления мышью, медиа и громкостью"),
        ]:
            step_card = ctk.CTkFrame(
                steps_frame,
                fg_color=PALETTE["surface_raised"],
                corner_radius=12,
                border_width=1,
                border_color=PALETTE["border"],
            )
            step_card.pack(fill="x", pady=(0, 8))
            step_card.grid_columnconfigure(1, weight=1)

            # Number badge
            num_badge = ctk.CTkFrame(
                step_card,
                fg_color=PALETTE["accent_deep"],
                corner_radius=8,
                width=36,
                height=36,
            )
            num_badge.grid(row=0, column=0, rowspan=2, padx=(12, 10), pady=12, sticky="ns")
            num_badge.grid_propagate(False)
            ctk.CTkLabel(
                num_badge,
                text=num,
                text_color=PALETTE["accent"],
                font=ctk.CTkFont(size=11, weight="bold"),
            ).place(relx=0.5, rely=0.5, anchor="center")

            self._label(step_card, heading, size=13, weight="bold").grid(
                row=0, column=1, sticky="sw", pady=(10, 0)
            )
            self._label(step_card, desc, size=11, color=PALETTE["text_secondary"],
                        wraplength=280).grid(
                row=1, column=1, sticky="nw", pady=(2, 10)
            )

    # ── TUTORIAL PAGE ─────────────────────────────────────────────────────────

    def _build_tutorial_page(self) -> None:
        page = ctk.CTkFrame(self.page_host, fg_color="transparent")
        page.grid(row=0, column=0, sticky="nsew")
        page.grid_columnconfigure(0, weight=1)
        self.pages["tutorial"] = page

        wrapper = self._glass_card(page, corner_radius=22)
        wrapper.pack(fill="both", expand=True)
        wrapper.grid_columnconfigure(0, weight=3)
        wrapper.grid_columnconfigure(1, weight=2)
        wrapper.grid_rowconfigure(1, weight=1)

        # Header bar
        head = ctk.CTkFrame(
            wrapper,
            fg_color=PALETTE["surface_raised"],
            corner_radius=0,
            border_width=0,
        )
        head.grid(row=0, column=0, columnspan=2, sticky="ew")
        head.grid_columnconfigure(1, weight=1)

        self.tutorial_step_label = ctk.CTkLabel(
            head,
            text="Шаг 1",
            text_color=PALETTE["text_secondary"],
            font=ctk.CTkFont(size=12),
        )
        self.tutorial_step_label.grid(row=0, column=0, sticky="w", padx=22, pady=14)

        self.progress_label = ctk.CTkLabel(
            head,
            text="● ○ ○ ○ ○ ○",
            text_color=PALETTE["accent"],
            font=ctk.CTkFont(size=13),
        )
        self.progress_label.grid(row=0, column=1, pady=14)

        ctk.CTkLabel(
            head,
            text=f"{len(TUTORIAL_STEPS)} жестов",
            text_color=PALETTE["text_muted"],
            font=ctk.CTkFont(size=11),
        ).grid(row=0, column=2, sticky="e", padx=22, pady=14)

        # Image panel
        img_shell = ctk.CTkFrame(
            wrapper,
            fg_color=PALETTE["surface_raised"],
            corner_radius=16,
            border_width=1,
            border_color=PALETTE["border"],
        )
        img_shell.grid(row=1, column=0, sticky="nsew", padx=(18, 8), pady=18)
        img_shell.grid_columnconfigure(0, weight=1)
        img_shell.grid_rowconfigure(0, weight=1)

        self.tutorial_image_label = ctk.CTkLabel(
            img_shell, text="", fg_color="transparent", corner_radius=14
        )
        self.tutorial_image_label.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)

        # Side content
        side = ctk.CTkFrame(wrapper, fg_color="transparent")
        side.grid(row=1, column=1, sticky="nsew", padx=(8, 18), pady=18)
        side.grid_rowconfigure(3, weight=1)

        # Icon badge
        self.tutorial_icon_label = ctk.CTkLabel(
            side,
            text="✋",
            font=ctk.CTkFont(size=40),
            fg_color=PALETTE["surface_raised"],
            corner_radius=16,
            width=68,
            height=68,
        )
        self.tutorial_icon_label.pack(anchor="w", pady=(4, 12))

        self.tutorial_subtitle_label = self._label(
            side, "", size=11, color=PALETTE["accent"]
        )
        self.tutorial_subtitle_label.pack(anchor="w")

        self.tutorial_title_label = ctk.CTkLabel(
            side,
            text="",
            text_color=PALETTE["text"],
            justify="left",
            font=ctk.CTkFont(size=28, weight="bold"),
        )
        self.tutorial_title_label.pack(anchor="w", pady=(4, 0))

        # Thin accent divider
        ctk.CTkFrame(side, fg_color=PALETTE["border_glow"], height=1, corner_radius=1).pack(
            fill="x", pady=(12, 12)
        )

        self.tutorial_body_label = self._label(
            side, "", size=13, color=PALETTE["text_secondary"], wraplength=300
        )
        self.tutorial_body_label.pack(anchor="w", pady=(0, 20))

        # Nav controls
        controls = ctk.CTkFrame(side, fg_color="transparent")
        controls.pack(anchor="w", side="bottom", pady=(0, 4))

        self.prev_tutorial_button = self._secondary_button(controls, "← Назад", width=118, height=40)
        self.prev_tutorial_button.configure(
            command=lambda: self._animate_button_press(
                self.prev_tutorial_button,
                self._prev_tutorial_step,
                pressed_color=PALETTE["accent_deep"],
                normal_color=PALETTE["btn_secondary"],
            )
        )
        self.prev_tutorial_button.pack(side="left", padx=(0, 10))

        self.next_tutorial_button = self._primary_button(controls, "Далее →", width=118, height=40)
        self.next_tutorial_button.configure(
            command=lambda: self._animate_button_press(
                self.next_tutorial_button,
                self._next_tutorial_step,
                pressed_color=PALETTE["accent_dim"],
                normal_color=PALETTE["btn_primary"],
            )
        )
        self.next_tutorial_button.pack(side="left")

        self._render_tutorial_step()

    # ── DASHBOARD PAGE ────────────────────────────────────────────────────────

    def _build_dashboard_page(self) -> None:
        page = ctk.CTkFrame(self.page_host, fg_color="transparent")
        page.grid(row=0, column=0, sticky="nsew")
        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=2)
        page.grid_rowconfigure(0, weight=1)
        self.pages["dashboard"] = page

        # ── Camera feed card ──
        left = self._glass_card(page, corner_radius=22)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        cam_header = ctk.CTkFrame(left, fg_color="transparent")
        cam_header.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 8))
        cam_header.grid_columnconfigure(1, weight=1)

        ctk.CTkFrame(
            left, fg_color=PALETTE["border_glow"], height=2, corner_radius=1
        ).grid(row=0, column=0, sticky="new", padx=0, pady=0)

        self._label(left, "Живое превью", size=18, weight="bold").grid(
            row=0, column=0, sticky="w", padx=20, pady=(18, 10)
        )

        video_shell = ctk.CTkFrame(
            left,
            fg_color=PALETTE["surface_raised"],
            corner_radius=16,
            border_width=1,
            border_color=PALETTE["border_glow"],
        )
        video_shell.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        video_shell.grid_columnconfigure(0, weight=1)
        video_shell.grid_rowconfigure(0, weight=1)

        self.video_label = tk.Label(video_shell, bg=PALETTE["surface_raised"], bd=0)
        self.video_label.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # ── Right column ──
        right = ctk.CTkFrame(page, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right.grid_rowconfigure(0, weight=0)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # Status card
        status = self._glass_card(right, corner_radius=22)
        status.grid(row=0, column=0, sticky="ew")
        status.grid_columnconfigure(0, weight=1)

        ctk.CTkFrame(
            status, fg_color=PALETTE["border_glow"], height=2, corner_radius=1
        ).grid(row=0, column=0, sticky="ew", padx=0, pady=0)

        self._label(status, "Состояние системы", size=18, weight="bold").grid(
            row=1, column=0, sticky="w", padx=18, pady=(16, 10)
        )

        stat_grid = ctk.CTkFrame(status, fg_color="transparent")
        stat_grid.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 4))
        stat_grid.grid_columnconfigure(0, weight=1)
        stat_grid.grid_columnconfigure(1, weight=1)

        stat_pairs = [
            ("Жест",       self._last_gesture,  "◈"),
            ("Уверенность",self._confidence,    "⊹"),
            ("Задержка",   self._latency,        "◷"),
            ("Рука",       self._hand_state,     "✋"),
            ("Курсор",     self._pointer_state,  "⌖"),
            ("Режим",      self._engine_mode,    "⬡"),
        ]
        for i, (label, var, icon) in enumerate(stat_pairs):
            col = i % 2
            row_idx = i // 2
            self._stat_chip(stat_grid, icon, label, var).grid(
                row=row_idx, column=col,
                padx=(0 if col == 0 else 5, 0 if col == 1 else 5),
                pady=4,
                sticky="ew",
            )

        # Full-width stats
        for label, var, icon in [
            ("Камера",   self._camera_profile, "◎"),
            ("Действие", self._last_action,    "▷"),
        ]:
            self._stat_row_wide(status, icon, label, var).grid(
                row=status.grid_size()[1], column=0,
                sticky="ew", padx=18, pady=3
            )

        # Control toggle
        toggle_frame = ctk.CTkFrame(
            status,
            fg_color=PALETTE["surface_raised"],
            corner_radius=12,
            border_width=1,
            border_color=PALETTE["border"],
        )
        toggle_frame.grid(
            row=status.grid_size()[1], column=0,
            sticky="ew", padx=18, pady=(12, 16)
        )

        ctk.CTkCheckBox(
            toggle_frame,
            text=" ⬡  Включить управление системой",
            variable=self._active,
            command=self._sync_control_state,
            fg_color=PALETTE["accent"],
            hover_color=PALETTE["accent_glow"],
            checkmark_color=PALETTE["btn_primary_fg"],
            border_color=PALETTE["border_soft"],
            text_color=PALETTE["text"],
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=14, pady=12)

        # How it works card
        explainer = self._glass_card(right, corner_radius=22)
        explainer.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        ctk.CTkFrame(
            explainer, fg_color=PALETTE["border_glow"], height=2, corner_radius=1
        ).grid(row=0, column=0, sticky="ew", padx=0)

        self._label(explainer, "Как это работает", size=16, weight="bold").grid(
            row=1, column=0, sticky="w", padx=18, pady=(14, 6)
        )
        self._label(
            explainer,
            textvariable=self._detail_text,
            size=12, color=PALETTE["text_secondary"], wraplength=340,
        ).grid(row=2, column=0, sticky="nw", padx=18, pady=(0, 14))

    def _stat_chip(
        self,
        parent,
        icon: str,
        label: str,
        variable: tk.StringVar,
    ) -> ctk.CTkFrame:
        chip = ctk.CTkFrame(
            parent,
            fg_color=PALETTE["surface_raised"],
            corner_radius=10,
            border_width=1,
            border_color=PALETTE["border"],
        )
        top = ctk.CTkFrame(chip, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(8, 2))

        ctk.CTkLabel(
            top,
            text=f"{icon}  {label}",
            text_color=PALETTE["text_muted"],
            font=ctk.CTkFont(size=10),
        ).pack(side="left")

        ctk.CTkLabel(
            chip,
            textvariable=variable,
            text_color=PALETTE["accent"],
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(0, 8))

        return chip

    def _stat_row_wide(
        self,
        parent,
        icon: str,
        label: str,
        variable: tk.StringVar,
    ) -> ctk.CTkFrame:
        row = ctk.CTkFrame(
            parent,
            fg_color=PALETTE["surface_raised"],
            corner_radius=8,
            border_width=1,
            border_color=PALETTE["border"],
        )
        ctk.CTkLabel(
            row,
            text=f"{icon}  {label}",
            text_color=PALETTE["text_muted"],
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=12, pady=8)
        ctk.CTkLabel(
            row,
            textvariable=variable,
            text_color=PALETTE["text"],
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="right", padx=12, pady=8)
        return row

    # ── page routing ──────────────────────────────────────────────────────────

    def _show_page(self, page_id: str) -> None:
        self._animate_page_transition()
        for key, page in self.pages.items():
            page.grid_remove()
            self.nav_buttons[key].configure(
                fg_color="transparent",
                text_color=PALETTE["text_secondary"],
                border_width=0,
            )
        self.pages[page_id].grid()
        self.nav_buttons[page_id].configure(
            fg_color=PALETTE["accent_deep"],
            text_color=PALETTE["accent"],
            border_width=1,
            border_color=PALETTE["border_glow"],
        )

    def _animate_button_press(
        self,
        button: ctk.CTkButton,
        command,
        *,
        pressed_color: str,
        normal_color: str,
        pressed_text_color: str | None = None,
        normal_text_color: str | None = None,
    ) -> None:
        original_text_color = normal_text_color or button.cget("text_color")
        button.configure(
            fg_color=pressed_color,
            text_color=pressed_text_color or original_text_color,
        )

        def finish() -> None:
            try:
                button.configure(fg_color=normal_color, text_color=original_text_color)
            except tk.TclError:
                pass
            command()

        self.root.after(80, finish)

    def _animate_page_transition(self) -> None:
        if self._page_transition_job is not None:
            self.root.after_cancel(self._page_transition_job)
        try:
            self.page_host.configure(fg_color=PALETTE["glass"])
        except tk.TclError:
            return

        def restore() -> None:
            try:
                self.page_host.configure(fg_color="transparent")
            except tk.TclError:
                pass

        self._page_transition_job = self.root.after(100, restore)

    # ── tutorial rendering ────────────────────────────────────────────────────

    def _load_ctk_image(self, path: Path, size: tuple[int, int]) -> ctk.CTkImage | None:
        if path in self._tutorial_images:
            return self._tutorial_images[path]
        try:
            image = Image.open(path)
        except OSError:
            return None
        ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=size)
        self._tutorial_images[path] = ctk_image
        return ctk_image

    def _render_tutorial_step(self) -> None:
        step = TUTORIAL_STEPS[self._tutorial_index]
        n = self._tutorial_index
        total = len(TUTORIAL_STEPS)

        self.tutorial_step_label.configure(text=f"Шаг {n + 1} из {total}")
        self.progress_label.configure(
            text=" ".join("●" if i == n else "○" for i in range(total))
        )
        self.tutorial_icon_label.configure(text=step["icon"])
        self.tutorial_subtitle_label.configure(text=step["subtitle"].upper())
        self.tutorial_title_label.configure(text=step["title"])
        self.tutorial_body_label.configure(text=step["body"])

        image = self._load_ctk_image(step["image"], (500, 320))
        if image is not None:
            self.tutorial_image_label.configure(image=image, text="")
        else:
            self.tutorial_image_label.configure(
                image=None,
                text="Изображение не найдено",
                text_color=PALETTE["text_muted"],
            )

        self.prev_tutorial_button.configure(
            state="normal" if n > 0 else "disabled"
        )
        self.next_tutorial_button.configure(
            text="⬡  Открыть панель" if n == total - 1 else "Далее →"
        )

    def _prev_tutorial_step(self) -> None:
        if self._tutorial_index == 0:
            return
        self._tutorial_index -= 1
        self._render_tutorial_step()

    def _next_tutorial_step(self) -> None:
        if self._tutorial_index == len(TUTORIAL_STEPS) - 1:
            self._show_page("dashboard")
            return
        self._tutorial_index += 1
        self._render_tutorial_step()

    # ── control state ─────────────────────────────────────────────────────────

    def _sync_control_state(self) -> None:
        if self._active.get():
            self._engine_mode.set("управление включено")
        else:
            self._engine_mode.set("только просмотр")

    # ── main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        self._sync_control_state()
        self._tick()
        self.root.mainloop()

    def _tick(self) -> None:
        tracking_enabled = self._active.get()
        frame_result = self._tracker.read(track_enabled=tracking_enabled)
        if frame_result is not None:
            frame_rgb = cv2.cvtColor(frame_result.frame_bgr, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame_rgb)
            target_width  = max(self.video_label.winfo_width()  - 24, 720)
            target_height = max(self.video_label.winfo_height() - 24, 420)
            image.thumbnail((target_width, target_height))
            self._image_handle = ImageTk.PhotoImage(image=image)
            self.video_label.configure(image=self._image_handle)

            self._latency.set(f"{frame_result.latency_ms:.1f} мс")
            self._ai_state.set("активно" if tracking_enabled else "ожидание")

            prediction = frame_result.prediction
            if tracking_enabled and prediction is not None:
                state_label = {
                    "idle": "ожидание",
                    "gesture_started": "жест начинается",
                    "gesture_confirmed": prediction.gesture,
                }.get(prediction.state, prediction.gesture)
                self._last_gesture.set(state_label)
                self._confidence.set(f"{prediction.confidence * 100:.0f}%")
                self._hand_state.set("рука найдена")
                self._pointer_state.set(
                    "поток курсора"
                    if prediction.gesture == "open_palm" and prediction.state == "gesture_confirmed"
                    else "режим команд"
                )
                if self._active.get():
                    if (
                        prediction.gesture == "open_palm"
                        and prediction.state == "gesture_confirmed"
                        and prediction.emit_action
                    ):
                        self._actions.reset_pending()
                        pointer = self._tracker.pointer_target(frame_result)
                        if pointer is not None:
                            self._actions.move_pointer(pointer[0], pointer[1])
                            self._last_action.set("движение курсора")
                    elif prediction.state == "gesture_confirmed" and prediction.emit_action:
                        action = self._actions.trigger(prediction.gesture)
                        if action is not None:
                            self._last_action.set(action)
                else:
                    self._actions.reset_pending()
                    self._last_action.set("предпросмотр")
            elif tracking_enabled:
                self._actions.reset_pending()
                self._last_gesture.set("нет")
                self._confidence.set("0%")
                self._hand_state.set("рука не найдена")
                self._pointer_state.set("курсор неактивен")
            else:
                self._actions.reset_pending()
                self._last_gesture.set("нет")
                self._confidence.set("0%")
                self._hand_state.set("трекинг выключен")
                self._pointer_state.set("курсор неактивен")
                self._last_action.set("предпросмотр")

        self.root.after(20, self._tick)

    def _on_close(self) -> None:
        if self._pulse_job is not None:
            self.root.after_cancel(self._pulse_job)
        self._tracker.close()
        self.root.destroy()
