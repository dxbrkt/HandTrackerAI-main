from __future__ import annotations

import tkinter as tk
from pathlib import Path

import customtkinter as ctk
import cv2
from PIL import Image, ImageSequence, ImageTk

from .action_controller import ActionController
from .config import AppConfig
from .hand_tracker import HandTracker


ASSETS_DIR = Path(__file__).resolve().parent / "pngfortutor"
WELCOME_GIF = Path("/Users/sb/Desktop/13321.gif")

PALETTE = {
    "bg": "#050505",
    "surface": "#0D0D0D",
    "panel": "#121212",
    "panel_alt": "#181818",
    "line": "#262626",
    "text": "#F5F5F5",
    "muted": "#A1A1A1",
    "subtle": "#737373",
    "accent": "#FFFFFF",
    "accent_soft": "#1E1E1E",
}

TUTORIAL_STEPS = [
    {
        "title": "Движение курсора",
        "subtitle": "Открытая ладонь",
        "body": "Покажите открытую ладонь в камеру. Положение указательного пальца используется как цель для курсора.",
        "image": ASSETS_DIR / "openpalm.png",
    },
    {
        "title": "Клик щепоткой",
        "subtitle": "Pinch",
        "body": "Сведите большой и указательный палец вместе. Когда жест распознан уверенно, приложение выполняет левый клик.",
        "image": ASSETS_DIR / "pinchclick.png",
    },
    {
        "title": "Управление системой",
        "subtitle": "Свайпы и кулак",
        "body": "Свайпы переключают рабочие столы, а кулак ставит медиа на паузу или снимает с паузы.",
        "image": ASSETS_DIR / "swape.png",
    },
    {
        "title": "Громкость вниз",
        "subtitle": "Thumbs down",
        "body": "Опустите большой палец вниз, держа остальные пальцы собранными. Когда жест распознан, приложение уменьшает системную громкость.",
        "image": ASSETS_DIR / "volumedown.png",
    },
    {
        "title": "Прокрутка вверх",
        "subtitle": "Два пальца вверх",
        "body": "Поднимите указательный и средний пальцы и сделайте короткое движение рукой вверх. Это запускает прокрутку страницы вверх.",
        "image": ASSETS_DIR / "twofingersup.png",
    },
    {
        "title": "Прокрутка вниз",
        "subtitle": "Два пальца вниз",
        "body": "С тем же положением двух пальцев сделайте короткое движение рукой вниз. Это запускает прокрутку страницы вниз.",
        "image": ASSETS_DIR / "twofingersdown.png",
    },
]


class GestureControlApp:
    def __init__(self, config: AppConfig | None = None) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.config = config or AppConfig()
        self.root = ctk.CTk()
        self.root.title(self.config.window_title)
        self.root.geometry("1420x900")
        self.root.minsize(1200, 780)
        self.root.configure(fg_color=PALETTE["bg"])

        self._tracker = HandTracker(self.config)
        self._actions = ActionController(
            cooldown_seconds=self.config.gesture.command_cooldown_seconds,
            shutdown_hold_seconds=self.config.gesture.shutdown_hold_seconds,
        )

        self._image_handle = None
        self._gif_frames: list[ImageTk.PhotoImage] = []
        self._gif_index = 0
        self._gif_job: str | None = None
        self._tutorial_index = 0
        self._tutorial_images: dict[Path, ctk.CTkImage] = {}

        self._active = tk.BooleanVar(value=False)
        self._last_action = tk.StringVar(value="ожидание жеста")
        self._last_gesture = tk.StringVar(value="нет")
        self._latency = tk.StringVar(value="0 мс")
        self._confidence = tk.StringVar(value="0%")
        self._ai_state = tk.StringVar(value="ожидание")
        self._hand_state = tk.StringVar(value="рука не найдена")
        self._pointer_state = tk.StringVar(value="курсор неактивен")
        self._engine_mode = tk.StringVar(value="только просмотр")
        self._camera_profile = tk.StringVar(
            value=(
                f"{self.config.camera.width}x{self.config.camera.height}"
                f" @ {self.config.camera.fps_hint} FPS"
            )
        )
        self._detail_text = tk.StringVar(
            value=(
                "Камера захватывает кадр, модель выделяет ключевые точки руки,"
                " затем движок определяет жест и запускает действие."
            )
        )
        self._page_transition_job: str | None = None

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        shell = ctk.CTkFrame(
            self.root,
            fg_color=PALETTE["surface"],
            corner_radius=24,
            border_width=1,
            border_color=PALETTE["line"],
        )
        shell.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(1, weight=1)

        self.pages: dict[str, ctk.CTkFrame] = {}
        self.nav_buttons: dict[str, ctk.CTkButton] = {}

        self._build_header(shell)

        self.page_host = ctk.CTkFrame(shell, fg_color="transparent")
        self.page_host.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.page_host.grid_columnconfigure(0, weight=1)
        self.page_host.grid_rowconfigure(0, weight=1)

        self._build_welcome_page()
        self._build_tutorial_page()
        self._build_dashboard_page()
        self._show_page("welcome")

    def _build_header(self, parent: ctk.CTkFrame) -> None:
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 12))
        header.grid_columnconfigure(1, weight=1)

        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w")

        dot = ctk.CTkLabel(
            brand,
            text="●",
            text_color=PALETTE["accent"],
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        dot.pack(side="left")

        ctk.CTkLabel(
            brand,
            text="HandTracker AI",
            text_color=PALETTE["text"],
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(side="left", padx=(10, 0))

        nav = ctk.CTkFrame(header, fg_color="transparent")
        nav.grid(row=0, column=1)

        for page_id, title in (
            ("welcome", "Старт"),
            ("tutorial", "Обучение"),
            ("dashboard", "Панель"),
        ):
            button = ctk.CTkButton(
                nav,
                text=title,
                command=lambda page_id=page_id, button_ref=None: None,
                fg_color="transparent",
                hover_color=PALETTE["accent_soft"],
                text_color=PALETTE["muted"],
                corner_radius=14,
                border_width=0,
                width=110,
                height=36,
            )
            button.configure(
                command=lambda page_id=page_id, button=button: self._animate_button_press(
                    button,
                    lambda: self._show_page(page_id),
                    pressed_color=PALETTE["accent_soft"],
                    normal_color="transparent",
                )
            )
            button.pack(side="left", padx=4)
            self.nav_buttons[page_id] = button

        self.mode_label = ctk.CTkLabel(
            header,
            textvariable=self._engine_mode,
            text_color=PALETTE["text"],
            font=ctk.CTkFont(size=12),
        )
        self.mode_label.grid(row=0, column=2, sticky="e")

    def _build_welcome_page(self) -> None:
        page = ctk.CTkFrame(self.page_host, fg_color="transparent")
        page.grid(row=0, column=0, sticky="nsew")
        page.grid_columnconfigure(0, weight=1)
        page.grid_columnconfigure(1, weight=1)
        self.pages["welcome"] = page

        left = ctk.CTkFrame(page, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))

        ctk.CTkLabel(
            left,
            text="Управляйте Mac жестами",
            text_color=PALETTE["text"],
            justify="left",
            font=ctk.CTkFont(size=42, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(36, 12))

        ctk.CTkLabel(
            left,
            text=(
                "Минималистичный интерфейс, понятное обучение и живая панель"
                " управления без визуального шума."
            ),
            text_color=PALETTE["muted"],
            justify="left",
            wraplength=520,
            font=ctk.CTkFont(size=16),
        ).pack(anchor="w", padx=24, pady=(0, 24))

        buttons = ctk.CTkFrame(left, fg_color="transparent")
        buttons.pack(anchor="w", padx=24, pady=(0, 26))

        start_button = ctk.CTkButton(
            buttons,
            text="Открыть обучение",
            command=lambda: None,
            fg_color=PALETTE["accent"],
            hover_color="#E8E8E8",
            text_color="#050505",
            corner_radius=16,
            height=44,
            width=170,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        start_button.configure(
            command=lambda: self._animate_button_press(
                start_button,
                lambda: self._show_page("tutorial"),
                pressed_color="#D9D9D9",
                normal_color=PALETTE["accent"],
                pressed_text_color="#050505",
                normal_text_color="#050505",
            )
        )
        start_button.pack(side="left", padx=(0, 10))

        skip_button = ctk.CTkButton(
            buttons,
            text="Сразу в панель",
            command=lambda: None,
            fg_color=PALETTE["accent_soft"],
            hover_color="#252525",
            text_color=PALETTE["text"],
            corner_radius=16,
            height=44,
            width=150,
        )
        skip_button.configure(
            command=lambda: self._animate_button_press(
                skip_button,
                lambda: self._show_page("dashboard"),
                pressed_color="#2A2A2A",
                normal_color=PALETTE["accent_soft"],
            )
        )
        skip_button.pack(side="left")

        ctk.CTkLabel(
            left,
            text=(
                "Что внутри: камера, распознавание руки, определение жестов и"
                " запуск действий в системе."
            ),
            text_color=PALETTE["subtle"],
            justify="left",
            wraplength=520,
            font=ctk.CTkFont(size=13),
        ).pack(anchor="w", padx=24)

        right = ctk.CTkFrame(
            page,
            fg_color=PALETTE["panel"],
            corner_radius=22,
            border_width=1,
            border_color=PALETTE["line"],
        )
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            right,
            text="Анимация входа",
            text_color=PALETTE["text"],
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=22, pady=(22, 10))

        self.welcome_gif_label = tk.Label(
            right,
            bg=PALETTE["panel"],
            bd=0,
            relief="flat",
        )
        self.welcome_gif_label.grid(row=1, column=0, sticky="nsew", padx=22, pady=(0, 22))

    def _build_tutorial_page(self) -> None:
        page = ctk.CTkFrame(self.page_host, fg_color="transparent")
        page.grid(row=0, column=0, sticky="nsew")
        page.grid_columnconfigure(0, weight=1)
        self.pages["tutorial"] = page

        wrapper = ctk.CTkFrame(
            page,
            fg_color=PALETTE["panel"],
            corner_radius=22,
            border_width=1,
            border_color=PALETTE["line"],
        )
        wrapper.pack(fill="both", expand=True)
        wrapper.grid_columnconfigure(0, weight=3)
        wrapper.grid_columnconfigure(1, weight=2)
        wrapper.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(wrapper, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(24, 10))
        head.grid_columnconfigure(1, weight=1)

        self.tutorial_step_label = ctk.CTkLabel(
            head,
            text="Шаг 1",
            text_color=PALETTE["muted"],
            font=ctk.CTkFont(size=13),
        )
        self.tutorial_step_label.grid(row=0, column=0, sticky="w")

        self.progress_label = ctk.CTkLabel(
            head,
            text="● ○ ○",
            text_color=PALETTE["text"],
            font=ctk.CTkFont(size=14),
        )
        self.progress_label.grid(row=0, column=2, sticky="e")

        self.tutorial_image_label = ctk.CTkLabel(
            wrapper,
            text="",
            fg_color=PALETTE["panel_alt"],
            corner_radius=18,
        )
        self.tutorial_image_label.grid(row=1, column=0, sticky="nsew", padx=(24, 12), pady=(0, 24))

        side = ctk.CTkFrame(wrapper, fg_color="transparent")
        side.grid(row=1, column=1, sticky="nsew", padx=(12, 24), pady=(0, 24))

        self.tutorial_subtitle_label = ctk.CTkLabel(
            side,
            text="",
            text_color=PALETTE["muted"],
            font=ctk.CTkFont(size=13),
        )
        self.tutorial_subtitle_label.pack(anchor="w", pady=(8, 8))

        self.tutorial_title_label = ctk.CTkLabel(
            side,
            text="",
            text_color=PALETTE["text"],
            justify="left",
            font=ctk.CTkFont(size=30, weight="bold"),
        )
        self.tutorial_title_label.pack(anchor="w")

        self.tutorial_body_label = ctk.CTkLabel(
            side,
            text="",
            text_color=PALETTE["muted"],
            justify="left",
            wraplength=320,
            font=ctk.CTkFont(size=14),
        )
        self.tutorial_body_label.pack(anchor="w", pady=(12, 22))

        controls = ctk.CTkFrame(side, fg_color="transparent")
        controls.pack(anchor="w")

        self.prev_tutorial_button = ctk.CTkButton(
            controls,
            text="Назад",
            command=lambda: None,
            fg_color=PALETTE["accent_soft"],
            hover_color="#252525",
            text_color=PALETTE["text"],
            corner_radius=14,
            width=110,
            height=40,
        )
        self.prev_tutorial_button.configure(
            command=lambda: self._animate_button_press(
                self.prev_tutorial_button,
                self._prev_tutorial_step,
                pressed_color="#2A2A2A",
                normal_color=PALETTE["accent_soft"],
            )
        )
        self.prev_tutorial_button.pack(side="left", padx=(0, 10))

        self.next_tutorial_button = ctk.CTkButton(
            controls,
            text="Далее",
            command=lambda: None,
            fg_color=PALETTE["accent"],
            hover_color="#E8E8E8",
            text_color="#050505",
            corner_radius=14,
            width=110,
            height=40,
            font=ctk.CTkFont(weight="bold"),
        )
        self.next_tutorial_button.configure(
            command=lambda: self._animate_button_press(
                self.next_tutorial_button,
                self._next_tutorial_step,
                pressed_color="#D9D9D9",
                normal_color=PALETTE["accent"],
                pressed_text_color="#050505",
                normal_text_color="#050505",
            )
        )
        self.next_tutorial_button.pack(side="left")

        self._render_tutorial_step()

    def _build_dashboard_page(self) -> None:
        page = ctk.CTkFrame(self.page_host, fg_color="transparent")
        page.grid(row=0, column=0, sticky="nsew")
        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=2)
        page.grid_rowconfigure(0, weight=1)
        self.pages["dashboard"] = page

        left = ctk.CTkFrame(
            page,
            fg_color=PALETTE["panel"],
            corner_radius=22,
            border_width=1,
            border_color=PALETTE["line"],
        )
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            left,
            text="Живое превью",
            text_color=PALETTE["text"],
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        video_shell = ctk.CTkFrame(
            left,
            fg_color=PALETTE["panel_alt"],
            corner_radius=18,
        )
        video_shell.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        video_shell.grid_columnconfigure(0, weight=1)
        video_shell.grid_rowconfigure(0, weight=1)

        self.video_label = tk.Label(video_shell, bg=PALETTE["panel_alt"], bd=0)
        self.video_label.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

        right = ctk.CTkFrame(page, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 0))

        status = ctk.CTkFrame(
            right,
            fg_color=PALETTE["panel"],
            corner_radius=22,
            border_width=1,
            border_color=PALETTE["line"],
        )
        status.pack(fill="x")

        ctk.CTkLabel(
            status,
            text="Состояние",
            text_color=PALETTE["text"],
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(20, 12))

        for label, variable in (
            ("Жест", self._last_gesture),
            ("Уверенность", self._confidence),
            ("Задержка", self._latency),
            ("Рука", self._hand_state),
            ("Курсор", self._pointer_state),
            ("Режим", self._engine_mode),
            ("Камера", self._camera_profile),
            ("Действие", self._last_action),
        ):
            self._stat_row(status, label, variable).pack(fill="x", padx=20, pady=4)

        ctk.CTkCheckBox(
            status,
            text="Включить управление системой",
            variable=self._active,
            command=self._sync_control_state,
            fg_color=PALETTE["accent"],
            hover_color="#E8E8E8",
            checkmark_color="#050505",
            text_color=PALETTE["text"],
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(16, 18))

        explainer = ctk.CTkFrame(
            right,
            fg_color=PALETTE["panel"],
            corner_radius=22,
            border_width=1,
            border_color=PALETTE["line"],
        )
        explainer.pack(fill="x", pady=(14, 0))

        ctk.CTkLabel(
            explainer,
            text="Как это работает",
            text_color=PALETTE["text"],
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(18, 8))

        ctk.CTkLabel(
            explainer,
            textvariable=self._detail_text,
            text_color=PALETTE["muted"],
            justify="left",
            wraplength=360,
            font=ctk.CTkFont(size=13),
        ).pack(anchor="w", padx=20, pady=(0, 16))

    def _show_page(self, page_id: str) -> None:
        self._animate_page_transition()
        for key, page in self.pages.items():
            page.grid_remove()
            self.nav_buttons[key].configure(
                fg_color="transparent",
                text_color=PALETTE["muted"],
            )
        self.pages[page_id].grid()
        self.nav_buttons[page_id].configure(
            fg_color=PALETTE["accent_soft"],
            text_color=PALETTE["text"],
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
                button.configure(
                    fg_color=normal_color,
                    text_color=original_text_color,
                )
            except tk.TclError:
                pass
            command()

        self.root.after(85, finish)

    def _animate_page_transition(self) -> None:
        if self._page_transition_job is not None:
            self.root.after_cancel(self._page_transition_job)

        try:
            self.page_host.configure(fg_color=PALETTE["accent_soft"])
        except tk.TclError:
            return

        def restore() -> None:
            try:
                self.page_host.configure(fg_color="transparent")
            except tk.TclError:
                pass

        self._page_transition_job = self.root.after(120, restore)

    def _stat_row(
        self, parent: ctk.CTkFrame, label: str, variable: tk.StringVar
    ) -> ctk.CTkFrame:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(
            row,
            text=label,
            text_color=PALETTE["muted"],
            font=ctk.CTkFont(size=13),
        ).pack(side="left", padx=(0, 0), pady=8)
        ctk.CTkLabel(
            row,
            textvariable=variable,
            text_color=PALETTE["text"],
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="right", padx=(0, 0), pady=8)
        return row

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
        self.tutorial_step_label.configure(text=f"Шаг {self._tutorial_index + 1}")
        self.progress_label.configure(
            text=" ".join("●" if i == self._tutorial_index else "○" for i in range(len(TUTORIAL_STEPS)))
        )
        self.tutorial_subtitle_label.configure(text=step["subtitle"])
        self.tutorial_title_label.configure(text=step["title"])
        self.tutorial_body_label.configure(text=step["body"])

        image = self._load_ctk_image(step["image"], (480, 300))
        if image is not None:
            self.tutorial_image_label.configure(image=image, text="")
        else:
            self.tutorial_image_label.configure(
                image=None,
                text="Изображение не найдено",
                text_color=PALETTE["muted"],
            )

        self.prev_tutorial_button.configure(state="normal" if self._tutorial_index > 0 else "disabled")
        self.next_tutorial_button.configure(
            text="Открыть панель" if self._tutorial_index == len(TUTORIAL_STEPS) - 1 else "Далее"
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

    def _load_welcome_gif(self) -> None:
        if not WELCOME_GIF.exists():
            return
        try:
            with Image.open(WELCOME_GIF) as gif:
                frames: list[ImageTk.PhotoImage] = []
                for frame in ImageSequence.Iterator(gif):
                    prepared = frame.convert("RGBA").resize((480, 300))
                    frames.append(ImageTk.PhotoImage(prepared))
        except OSError:
            return

        self._gif_frames = frames[::2] if len(frames) > 1 else frames
        if self._gif_frames:
            self._animate_welcome_gif()

    def _animate_welcome_gif(self) -> None:
        if not self._gif_frames:
            return
        frame = self._gif_frames[self._gif_index]
        self.welcome_gif_label.configure(image=frame)
        self.welcome_gif_label.image = frame
        self._gif_index = (self._gif_index + 1) % len(self._gif_frames)
        self._gif_job = self.root.after(90, self._animate_welcome_gif)

    def _sync_control_state(self) -> None:
        if self._active.get():
            self._engine_mode.set("управление включено")
        else:
            self._engine_mode.set("только просмотр")

    def run(self) -> None:
        self._sync_control_state()
        self._load_welcome_gif()
        self._tick()
        self.root.mainloop()

    def _tick(self) -> None:
        tracking_enabled = self._active.get()
        frame_result = self._tracker.read(track_enabled=tracking_enabled)
        if frame_result is not None:
            frame_rgb = cv2.cvtColor(frame_result.frame_bgr, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame_rgb)
            target_width = max(self.video_label.winfo_width() - 24, 720)
            target_height = max(self.video_label.winfo_height() - 24, 420)
            image.thumbnail((target_width, target_height))
            self._image_handle = ImageTk.PhotoImage(image=image)
            self.video_label.configure(image=self._image_handle)

            self._latency.set(f"{frame_result.latency_ms:.1f} мс")
            self._ai_state.set("активно" if tracking_enabled else "ожидание")

            prediction = frame_result.prediction
            if tracking_enabled and prediction is not None:
                self._last_gesture.set(prediction.gesture)
                self._confidence.set(f"{prediction.confidence * 100:.0f}%")
                self._hand_state.set("рука найдена")
                self._pointer_state.set(
                    "поток курсора"
                    if prediction.gesture == "open_palm"
                    else "режим команд"
                )

                if self._active.get():
                    if prediction.gesture == "open_palm":
                        self._actions.reset_pending()
                        pointer = self._tracker.pointer_target(frame_result)
                        if pointer is not None:
                            self._actions.move_pointer(pointer[0], pointer[1])
                            self._last_action.set("движение курсора")
                    elif self._actions.trigger(prediction.gesture):
                        self._last_action.set(prediction.gesture)
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
        if self._gif_job is not None:
            self.root.after_cancel(self._gif_job)
        self._tracker.close()
        self.root.destroy()
