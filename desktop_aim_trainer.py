import ctypes
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QCursor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSlider,
    QStyle,
    QSystemTrayIcon,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


@dataclass
class Dot:
    x: float
    y: float
    radius: int
    born: float
    vx: float = 0.0
    vy: float = 0.0


class Overlay(QWidget):
    def __init__(self, trainer):
        super().__init__()
        self.trainer = trainer
        self.setWindowTitle("点击训练参数")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.set_click_mode(False)

        self.setGeometry(QApplication.primaryScreen().virtualGeometry())
        self.showFullScreen()

    def set_click_mode(self, enabled):
        self.setAttribute(Qt.WA_TransparentForMouseEvents, not enabled)
        self.setWindowFlag(Qt.WindowTransparentForInput, not enabled)
        self.showFullScreen()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        opacity = max(0.05, min(1.0, self.trainer.opacity / 100))
        painter.setOpacity(opacity)

        if self.trainer.target_style != "dot":
            pixmap = self.trainer.current_pixmap()
            if not pixmap.isNull():
                for dot in self.trainer.dots:
                    side = dot.radius * 2
                    scaled = pixmap.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    x = int(dot.x - scaled.width() // 2)
                    y = int(dot.y - scaled.height() // 2)
                    painter.drawPixmap(x, y, scaled)
                painter.setOpacity(1.0)
                return

        base = QColor(self.trainer.color)

        edge = QColor(255, 255, 255)
        edge.setAlphaF(0.45)

        highlight = QColor(255, 255, 255)
        highlight.setAlphaF(0.35)

        for dot in self.trainer.dots:
            painter.setPen(Qt.NoPen)
            painter.setBrush(base)
            painter.drawEllipse(QPoint(int(dot.x), int(dot.y)), dot.radius, dot.radius)

            painter.setBrush(highlight)
            small = max(2, dot.radius // 4)
            painter.drawEllipse(QPoint(int(dot.x - dot.radius // 3), int(dot.y - dot.radius // 3)), small, small)

            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(edge, 1.25))
            painter.drawEllipse(QPoint(int(dot.x), int(dot.y)), dot.radius, dot.radius)
        painter.setOpacity(1.0)

    def mousePressEvent(self, event):
        if self.trainer.hit_mode != "click" or event.button() != Qt.LeftButton:
            return
        self.trainer.try_click_hit(event.position().x(), event.position().y())


class LabeledSlider(QWidget):
    def __init__(self, title, minimum, maximum, value, suffix, on_change):
        super().__init__()
        self.setObjectName("sliderRow")
        self.title = title
        self.suffix = suffix
        self.on_change = on_change
        self.setFixedHeight(38)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(0)

        self.label = QLabel()
        self.label.setObjectName("fieldLabel")
        self.value_label = QLabel()
        self.value_label.setObjectName("valueLabel")
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setFixedHeight(17)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(value)

        layout.addWidget(self.label, 0, 0)
        layout.addWidget(self.value_label, 0, 1)
        layout.addWidget(self.slider, 1, 0, 1, 2)

        self.slider.valueChanged.connect(self.changed)
        self.changed(value)

    def changed(self, value):
        self.label.setText(self.title)
        self.value_label.setText(f"{value}{self.suffix}")
        self.on_change(value)


class AimTrainer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("点击训练参数")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedWidth(354)

        self.running = False
        self.color = "#ff3355"
        self.target_style = "dot"
        self.hit_mode = "move"
        self.practice_mode = "spawn"
        self.custom_image_path = None
        self.custom_pixmap = QPixmap()
        self.opacity = 80
        self.size = 24
        self.spawn_ms = 550
        self.life_ms = 1500
        self.track_speed = 360
        self.max_dots = 6
        self.hit_padding = 4
        self.hits = 0
        self.timeouts = 0
        self.tracking_seconds = 0.0
        self.last_spawn = 0.0
        self.last_tick = time.monotonic()
        self.really_quit = False
        self.boss_hotkey_down = False
        self.pause_hotkey_down = False
        self.training_region = "full"
        self.drag_offset = None
        self.dots: list[Dot] = []

        self.overlay = Overlay(self)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)

        self.build_ui()
        self.build_tray()
        self.hotkey_timer = QTimer(self)
        self.hotkey_timer.timeout.connect(self.check_boss_hotkey)
        self.hotkey_timer.start(50)
        self.move(80, 80)

    def build_ui(self):
        self.setStyleSheet(
            """
            QWidget {
                font-family: "Microsoft YaHei UI", "Segoe UI";
                font-size: 12px;
                color: #252a31;
                background: transparent;
            }
            QFrame#panel {
                background: #f7f8fa;
                border: 1px solid #d9dde4;
                border-radius: 12px;
            }
            QFrame#header {
                background: #24282f;
                border: 0;
                border-top-left-radius: 11px;
                border-top-right-radius: 11px;
            }
            QLabel#title {
                font-size: 15px;
                font-weight: 700;
                color: #ffffff;
            }
            QLabel#subtitle {
                color: #aeb5bf;
                font-size: 10px;
            }
            QLabel#footnote {
                color: #737b87;
                font-size: 11px;
            }
            QLabel#fieldLabel {
                color: #4c535e;
                font-weight: 600;
            }
            QLabel#valueLabel {
                color: #e05262;
                font-weight: 700;
            }
            QPushButton {
                min-height: 29px;
                padding: 0 10px;
                border: 1px solid #d5d9df;
                border-radius: 6px;
                background: #ffffff;
                color: #343a43;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #f1f3f5;
                border-color: #aeb5bf;
            }
            QPushButton:pressed {
                background: #e5e7eb;
            }
            QPushButton#startButton {
                background: #e05262;
                border-color: #e05262;
                color: #ffffff;
            }
            QPushButton#startButton[running="true"] {
                background: #2f9b73;
                border-color: #2f9b73;
                color: #ffffff;
            }
            QPushButton#dangerButton {
                background: #ffffff;
                border-color: #e2c4c7;
                color: #b84451;
            }
            QToolButton#windowButton {
                width: 25px;
                height: 25px;
                border: 0;
                border-radius: 5px;
                background: transparent;
                color: #c9ced6;
                font-size: 16px;
            }
            QToolButton#windowButton:hover {
                background: #3b414a;
                color: #ffffff;
            }
            QComboBox {
                min-height: 28px;
                padding: 0 7px;
                border: 1px solid #d1d5db;
                border-radius: 7px;
                background: #ffffff;
                color: #111827;
                selection-background-color: #e05262;
            }
            QComboBox::drop-down {
                border: 0;
                width: 20px;
            }
            QSlider::groove:horizontal {
                height: 5px;
                border-radius: 2px;
                background: #e5e7eb;
            }
            QSlider::sub-page:horizontal {
                border-radius: 2px;
                background: #e05262;
            }
            QSlider::handle:horizontal {
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
                background: #ffffff;
                border: 2px solid #e05262;
            }
            QFrame#preview {
                border: 1px solid #d1d5db;
                border-radius: 6px;
            }
            QTabWidget::pane {
                border: 1px solid #dde1e6;
                border-radius: 8px;
                background: #ffffff;
                top: -1px;
            }
            QTabBar::tab {
                min-width: 57px;
                min-height: 28px;
                padding: 0 5px;
                border: 0;
                border-bottom: 2px solid transparent;
                background: transparent;
                color: #707783;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                color: #e05262;
                border-bottom-color: #e05262;
            }
            QFrame#statsCard {
                background: #f0f2f5;
                border: 1px solid #dde1e6;
                border-radius: 7px;
            }
            QLabel#stats {
                color: #333943;
                font-size: 12px;
                font-weight: 700;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(0)

        panel = QFrame()
        panel.setObjectName("panel")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 75))
        panel.setGraphicsEffect(shadow)
        layout.addWidget(panel)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 10)
        panel_layout.setSpacing(8)

        header = QFrame()
        header.setObjectName("header")
        header.installEventFilter(self)
        header_layout = QGridLayout(header)
        header_layout.setContentsMargins(13, 8, 8, 8)
        header_layout.setHorizontalSpacing(5)
        header_layout.setVerticalSpacing(1)
        title = QLabel("点击训练参数")
        title.setObjectName("title")
        title.setAttribute(Qt.WA_TransparentForMouseEvents)
        header_layout.addWidget(title, 0, 0)
        hint = QLabel("轻量悬浮训练面板")
        hint.setObjectName("subtitle")
        hint.setAttribute(Qt.WA_TransparentForMouseEvents)
        header_layout.addWidget(hint, 1, 0)
        hide_button = QToolButton()
        hide_button.setObjectName("windowButton")
        hide_button.setText("—")
        hide_button.setToolTip("收进托盘")
        hide_button.clicked.connect(self.hide)
        header_layout.addWidget(hide_button, 0, 1, 2, 1)
        close_button = QToolButton()
        close_button.setObjectName("windowButton")
        close_button.setText("×")
        close_button.setToolTip("收进托盘")
        close_button.clicked.connect(self.hide)
        header_layout.addWidget(close_button, 0, 2, 2, 1)
        panel_layout.addWidget(header)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 0, 10, 0)
        content_layout.setSpacing(8)
        panel_layout.addWidget(content)

        button_row = QHBoxLayout()
        button_row.setSpacing(6)
        self.start_button = QPushButton("开始")
        self.start_button.setObjectName("startButton")
        self.start_button.setProperty("running", "false")
        self.start_button.clicked.connect(self.toggle)
        button_row.addWidget(self.start_button)

        clear_button = QPushButton("清空")
        clear_button.clicked.connect(self.clear_dots)
        button_row.addWidget(clear_button)

        quit_button = QPushButton("退出")
        quit_button.setObjectName("dangerButton")
        quit_button.clicked.connect(self.quit_app)
        button_row.addWidget(quit_button)
        content_layout.addLayout(button_row)

        tabs = QTabWidget()
        content_layout.addWidget(tabs)

        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        basic_layout.setContentsMargins(12, 12, 12, 12)
        basic_layout.setSpacing(8)
        tabs.addTab(basic_tab, "基础")

        target_tab = QWidget()
        target_layout = QVBoxLayout(target_tab)
        target_layout.setContentsMargins(12, 12, 12, 12)
        target_layout.setSpacing(8)
        tabs.addTab(target_tab, "目标")

        param_tab = QWidget()
        param_layout = QGridLayout(param_tab)
        param_layout.setContentsMargins(10, 10, 10, 10)
        param_layout.setHorizontalSpacing(14)
        param_layout.setVerticalSpacing(5)
        tabs.addTab(param_tab, "参数")

        status_tab = QWidget()
        status_layout = QVBoxLayout(status_tab)
        status_layout.setContentsMargins(12, 12, 12, 12)
        status_layout.setSpacing(8)
        tabs.addTab(status_tab, "状态")

        color_row = QHBoxLayout()
        color_row.setSpacing(6)
        color_label = QLabel("颜色")
        color_label.setObjectName("fieldLabel")
        color_row.addWidget(color_label)

        self.color_preview = QFrame()
        self.color_preview.setObjectName("preview")
        self.color_preview.setFixedSize(38, 24)
        self.update_preview()
        color_row.addWidget(self.color_preview)

        color_button = QPushButton("选择颜色")
        color_button.clicked.connect(self.choose_color)
        color_row.addWidget(color_button)
        target_layout.addLayout(color_row)

        style_row = QHBoxLayout()
        style_row.setSpacing(6)
        style_label = QLabel("样式")
        style_label.setObjectName("fieldLabel")
        style_row.addWidget(style_label)
        self.style_combo = QComboBox()
        self.style_combo.addItem("纯色圆点", "dot")
        self.style_combo.addItem("自定义图片", "custom")
        self.style_combo.currentIndexChanged.connect(self.change_style)
        style_row.addWidget(self.style_combo)
        load_button = QPushButton("选择图片")
        load_button.clicked.connect(self.choose_image)
        style_row.addWidget(load_button)
        target_layout.addLayout(style_row)

        practice_row = QHBoxLayout()
        practice_row.setSpacing(6)
        practice_label = QLabel("训练模式")
        practice_label.setObjectName("fieldLabel")
        practice_row.addWidget(practice_label)
        self.practice_combo = QComboBox()
        self.practice_combo.addItem("随机出现", "spawn")
        self.practice_combo.addItem("逐个点击", "sequence")
        self.practice_combo.addItem("移动目标", "tracking")
        self.practice_combo.currentIndexChanged.connect(self.change_practice_mode)
        practice_row.addWidget(self.practice_combo)
        basic_layout.addLayout(practice_row)

        region_row = QHBoxLayout()
        region_row.setSpacing(6)
        region_label = QLabel("训练区域")
        region_label.setObjectName("fieldLabel")
        region_row.addWidget(region_label)
        self.region_combo = QComboBox()
        self.region_combo.addItem("整个屏幕", "full")
        self.region_combo.addItem("中央 70%", "center70")
        self.region_combo.addItem("中央 45%", "center45")
        self.region_combo.currentIndexChanged.connect(self.change_training_region)
        region_row.addWidget(self.region_combo)
        basic_layout.addLayout(region_row)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        hit_label = QLabel("命中模式")
        hit_label.setObjectName("fieldLabel")
        mode_row.addWidget(hit_label)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("鼠标移动命中", "move")
        self.mode_combo.addItem("点击命中", "click")
        self.mode_combo.currentIndexChanged.connect(self.change_hit_mode)
        mode_row.addWidget(self.mode_combo)
        basic_layout.addLayout(mode_row)

        parameter_sliders = [
            LabeledSlider("透明度", 5, 100, self.opacity, "%", self.set_opacity),
            LabeledSlider("目标大小", 6, 80, self.size, "px", self.set_size),
            LabeledSlider("出现间隔", 60, 2500, self.spawn_ms, "ms", self.set_spawn_ms),
            LabeledSlider("自动消失", 100, 6000, self.life_ms, "ms", self.set_life_ms),
            LabeledSlider("移动速度", 80, 1200, self.track_speed, "px/s", self.set_track_speed),
            LabeledSlider("同时数量", 1, 40, self.max_dots, "个", self.set_max_dots),
            LabeledSlider("命中范围", 0, 30, self.hit_padding, "px", self.set_hit_padding),
        ]
        for index, slider in enumerate(parameter_sliders):
            param_layout.addWidget(slider, index // 2, index % 2)

        stats_card = QFrame()
        stats_card.setObjectName("statsCard")
        stats_layout = QVBoxLayout(stats_card)
        stats_layout.setContentsMargins(10, 8, 10, 8)
        self.stats = QLabel()
        self.stats.setObjectName("stats")
        self.update_stats()
        stats_layout.addWidget(self.stats)
        status_layout.addWidget(stats_card)
        footnote = QLabel("Ctrl+Alt+P：全局暂停 / 继续\nCtrl+Alt+Q：立即退出\nEsc 或关闭按钮：收进托盘")
        footnote.setObjectName("footnote")
        footnote.setWordWrap(True)
        status_layout.addWidget(footnote)
        status_layout.addStretch(1)

    def build_tray(self):
        self.tray = QSystemTrayIcon(self)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray.setIcon(icon if not icon.isNull() else QIcon())
        self.tray.setToolTip("点击训练参数")

        menu = QMenu()
        show_action = QAction("显示参数", self)
        show_action.triggered.connect(self.restore_from_tray)
        menu.addAction(show_action)

        hide_action = QAction("隐藏参数", self)
        hide_action.triggered.connect(self.hide)
        menu.addAction(hide_action)

        menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.restore_from_tray()

    def restore_from_tray(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def quit_app(self):
        self.really_quit = True
        self.clear_dots()
        self.overlay.close()
        self.tray.hide()
        QApplication.quit()

    def check_boss_hotkey(self):
        if sys.platform != "win32":
            return
        user32 = ctypes.windll.user32
        ctrl = user32.GetAsyncKeyState(0x11) & 0x8000
        alt = user32.GetAsyncKeyState(0x12) & 0x8000
        q_key = user32.GetAsyncKeyState(0x51) & 0x8000
        p_key = user32.GetAsyncKeyState(0x50) & 0x8000

        quit_pressed = bool(ctrl and alt and q_key)
        if quit_pressed and not self.boss_hotkey_down:
            self.boss_hotkey_down = True
            self.quit_app()
            return
        elif not quit_pressed:
            self.boss_hotkey_down = False

        pause_pressed = bool(ctrl and alt and p_key)
        if pause_pressed and not self.pause_hotkey_down:
            self.pause_hotkey_down = True
            self.toggle()
        elif not pause_pressed:
            self.pause_hotkey_down = False

    def update_preview(self):
        if hasattr(self, "color_preview"):
            self.color_preview.setStyleSheet(f"background: {self.color}; border: 1px solid #516077; border-radius: 6px;")

    def set_opacity(self, value):
        self.opacity = value
        self.overlay.update()

    def set_size(self, value):
        self.size = value
        self.overlay.update()

    def set_spawn_ms(self, value):
        self.spawn_ms = value

    def set_life_ms(self, value):
        self.life_ms = value

    def set_track_speed(self, value):
        self.track_speed = value

    def set_max_dots(self, value):
        self.max_dots = value

    def set_hit_padding(self, value):
        self.hit_padding = value

    def change_training_region(self):
        self.training_region = self.region_combo.currentData()
        self.clear_dots()
        if self.running:
            if self.practice_mode == "tracking":
                self.spawn_tracking_dot()
            else:
                self.spawn_dot()

    def training_bounds(self):
        full = self.overlay.rect()
        scale = {"center70": 0.70, "center45": 0.45}.get(self.training_region, 1.0)
        if scale == 1.0:
            return full
        width = max(1, int(full.width() * scale))
        height = max(1, int(full.height() * scale))
        return QRect((full.width() - width) // 2, (full.height() - height) // 2, width, height)

    def current_pixmap(self):
        if self.target_style == "custom" and self.custom_pixmap and not self.custom_pixmap.isNull():
            return self.custom_pixmap
        return QPixmap()

    def change_style(self):
        self.target_style = self.style_combo.currentData()
        if self.target_style == "custom" and self.custom_pixmap.isNull():
            self.choose_image()
            if self.custom_pixmap.isNull():
                self.style_combo.setCurrentIndex(0)
                self.target_style = "dot"
        self.overlay.update()

    def change_hit_mode(self):
        if self.practice_mode == "tracking" and self.mode_combo.currentData() == "click":
            move_index = self.mode_combo.findData("move")
            self.mode_combo.setCurrentIndex(move_index)
            return
        if self.practice_mode == "sequence" and self.mode_combo.currentData() != "click":
            click_index = self.mode_combo.findData("click")
            self.mode_combo.setCurrentIndex(click_index)
            return
        self.hit_mode = self.mode_combo.currentData()
        self.overlay.set_click_mode(self.hit_mode == "click")
        self.raise_()
        self.activateWindow()

    def change_practice_mode(self):
        self.practice_mode = self.practice_combo.currentData()
        self.clear_dots()
        self.tracking_seconds = 0.0
        self.update_stats()
        if self.practice_mode == "tracking":
            self.hit_mode = "move"
            move_index = self.mode_combo.findData("move")
            self.mode_combo.setCurrentIndex(move_index)
            self.overlay.set_click_mode(False)
            if self.running:
                self.spawn_tracking_dot()
        elif self.practice_mode == "sequence":
            self.hit_mode = "click"
            click_index = self.mode_combo.findData("click")
            self.mode_combo.setCurrentIndex(click_index)
            self.overlay.set_click_mode(True)
            if self.running:
                self.spawn_dot()
        self.mode_combo.setEnabled(self.practice_mode == "spawn")

    def choose_image(self):
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "选择目标图片",
            str(Path.home()),
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not path:
            return

        pixmap = QPixmap(path)
        if pixmap.isNull():
            return

        self.custom_image_path = path
        self.custom_pixmap = pixmap
        custom_index = self.style_combo.findData("custom")
        self.style_combo.setCurrentIndex(custom_index)
        self.target_style = "custom"
        self.overlay.update()

    def choose_color(self):
        color = QColorDialog.getColor(QColor(self.color), self, "选择小点颜色")
        if color.isValid():
            self.color = color.name()
            self.update_preview()
            self.overlay.update()

    def toggle(self):
        self.running = not self.running
        has_progress = self.hits > 0 or self.timeouts > 0 or self.tracking_seconds > 0
        self.start_button.setText("暂停" if self.running else ("继续" if has_progress else "开始"))
        self.start_button.setProperty("running", "true" if self.running else "false")
        self.start_button.style().unpolish(self.start_button)
        self.start_button.style().polish(self.start_button)
        self.last_spawn = 0.0
        if self.running and not self.dots:
            if self.practice_mode == "tracking":
                self.spawn_tracking_dot()
            else:
                self.spawn_dot()

    def clear_dots(self):
        self.dots.clear()
        self.overlay.update()

    def update_stats(self):
        self.stats.setText(f"命中: {self.hits}    超时: {self.timeouts}    跟随: {self.tracking_seconds:.1f}s")

    def spawn_dot(self):
        if len(self.dots) >= self.max_dots:
            return

        rect = self.training_bounds()
        radius = max(3, self.size // 2)
        margin = radius + 10
        x = random.randint(rect.left() + margin, max(rect.left() + margin, rect.right() - margin))
        y = random.randint(rect.top() + margin, max(rect.top() + margin, rect.bottom() - margin))
        self.dots.append(Dot(x=x, y=y, radius=radius, born=time.monotonic()))
        self.overlay.update()

    def spawn_tracking_dot(self):
        rect = self.training_bounds()
        radius = max(3, self.size // 2)
        margin = radius + 10
        x = random.randint(rect.left() + margin, max(rect.left() + margin, rect.right() - margin))
        y = random.randint(rect.top() + margin, max(rect.top() + margin, rect.bottom() - margin))
        speed = self.track_speed
        self.dots = [
            Dot(
                x=x,
                y=y,
                radius=radius,
                born=time.monotonic(),
                vx=speed * random.uniform(0.55, 0.95) * random.choice([-1, 1]) * abs(random.uniform(0.35, 1.0)),
                vy=speed * random.uniform(0.55, 0.95) * random.choice([-1, 1]) * abs(random.uniform(0.35, 1.0)),
            )
        ]
        if abs(self.dots[0].vx) < speed * 0.25:
            self.dots[0].vx = speed * 0.45
        if abs(self.dots[0].vy) < speed * 0.25:
            self.dots[0].vy = speed * 0.45
        self.overlay.update()

    def update_tracking_dot(self, dot, dt):
        rect = self.training_bounds()
        radius = max(3, self.size // 2)
        dot.radius = radius
        margin = radius + 4

        jitter = self.track_speed * 1.8
        dot.vx += random.uniform(-jitter, jitter) * dt
        dot.vy += random.uniform(-jitter, jitter) * dt

        max_speed = max(60, self.track_speed)
        speed = (dot.vx**2 + dot.vy**2) ** 0.5
        if speed > max_speed:
            scale = max_speed / speed
            dot.vx *= scale
            dot.vy *= scale
        elif speed < max_speed * 0.35:
            boost = (max_speed * 0.35) / max(1, speed)
            dot.vx *= boost
            dot.vy *= boost

        dot.x += dot.vx * dt
        dot.y += dot.vy * dt

        if dot.x < rect.left() + margin:
            dot.x = rect.left() + margin
            dot.vx = abs(dot.vx)
        elif dot.x > rect.right() - margin:
            dot.x = rect.right() - margin
            dot.vx = -abs(dot.vx)

        if dot.y < rect.top() + margin:
            dot.y = rect.top() + margin
            dot.vy = abs(dot.vy)
        elif dot.y > rect.bottom() - margin:
            dot.y = rect.bottom() - margin
            dot.vy = -abs(dot.vy)

    def eventFilter(self, watched, event):
        if watched.objectName() == "header":
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return True
            if event.type() == QEvent.MouseMove and self.drag_offset is not None:
                if event.buttons() & Qt.LeftButton:
                    self.move(event.globalPosition().toPoint() - self.drag_offset)
                    return True
            if event.type() == QEvent.MouseButtonRelease:
                self.drag_offset = None
                return True
        return super().eventFilter(watched, event)

    def try_click_hit(self, mx, my):
        next_dots = []
        hit_any = False
        for dot in self.dots:
            hit_radius = dot.radius + self.hit_padding
            hit = (mx - dot.x) ** 2 + (my - dot.y) ** 2 <= hit_radius**2
            if hit:
                self.hits += 1
                hit_any = True
            else:
                next_dots.append(dot)

        if hit_any:
            self.dots = next_dots
            if self.practice_mode == "sequence" and self.running:
                self.spawn_dot()
            self.update_stats()
            self.overlay.update()

    def tick(self):
        now = time.monotonic()
        dt = min(0.05, now - self.last_tick)
        self.last_tick = now

        if not self.running:
            return

        if self.practice_mode == "tracking":
            if not self.dots:
                self.spawn_tracking_dot()
            dot = self.dots[0]
            self.update_tracking_dot(dot, dt)

            rect = self.overlay.geometry()
            cursor = QCursor.pos()
            mx = cursor.x() - rect.left()
            my = cursor.y() - rect.top()
            hit_radius = dot.radius + self.hit_padding
            if (mx - dot.x) ** 2 + (my - dot.y) ** 2 <= hit_radius**2:
                self.tracking_seconds += dt
                self.update_stats()
            self.overlay.update()
            return

        if self.practice_mode == "sequence":
            if not self.dots:
                self.spawn_dot()
            return

        if (now - self.last_spawn) * 1000 >= self.spawn_ms:
            self.spawn_dot()
            self.last_spawn = now

        rect = self.overlay.geometry()
        cursor = QCursor.pos()
        mx = cursor.x() - rect.left()
        my = cursor.y() - rect.top()
        max_age = self.life_ms / 1000

        next_dots = []
        dirty = False
        for dot in self.dots:
            hit_radius = dot.radius + self.hit_padding
            hit = self.hit_mode == "move" and (mx - dot.x) ** 2 + (my - dot.y) ** 2 <= hit_radius**2
            expired = now - dot.born >= max_age

            if hit:
                self.hits += 1
                dirty = True
            elif expired:
                self.timeouts += 1
                dirty = True
            else:
                next_dots.append(dot)

        if dirty:
            self.dots = next_dots
            self.update_stats()
            self.overlay.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
        super().keyPressEvent(event)

    def closeEvent(self, event):
        if self.really_quit:
            self.overlay.close()
            event.accept()
            return
        event.ignore()
        self.hide()
        if self.tray.isVisible():
            self.tray.showMessage("点击训练参数", "已缩小到系统托盘。右键托盘图标可退出。", QSystemTrayIcon.Information, 1800)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    trainer = AimTrainer()
    trainer.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

