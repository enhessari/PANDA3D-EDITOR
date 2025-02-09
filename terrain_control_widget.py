from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QSlider, QPushButton
from PyQt5.QtCore import Qt

class TerrainControlWidget(QWidget):
    def __init__(self, terrain_painter_app):
        super().__init__()
        self.terrain_painter_app = terrain_painter_app

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Brush size control
        self.brush_size_label = QLabel("Brush Size: 10")
        self.brush_size_slider = QSlider(Qt.Horizontal)
        self.brush_size_slider.setMinimum(1)
        self.brush_size_slider.setMaximum(100)
        self.brush_size_slider.setValue(10)
        self.brush_size_slider.valueChanged.connect(self.update_brush_size)
        layout.addWidget(self.brush_size_label)
        layout.addWidget(self.brush_size_slider)

        # Brush intensity control
        self.brush_intensity_label = QLabel("Brush Intensity: 1.0")
        self.brush_intensity_slider = QSlider(Qt.Horizontal)
        self.brush_intensity_slider.setMinimum(1)
        self.brush_intensity_slider.setMaximum(100)
        self.brush_intensity_slider.setValue(10)
        self.brush_intensity_slider.valueChanged.connect(self.update_brush_intensity)
        layout.addWidget(self.brush_intensity_label)
        layout.addWidget(self.brush_intensity_slider)

        # Terrain height control
        self.terrain_height_label = QLabel("Terrain Height: 1.0")
        self.terrain_height_slider = QSlider(Qt.Horizontal)
        self.terrain_height_slider.setMinimum(1)
        self.terrain_height_slider.setMaximum(100)
        self.terrain_height_slider.setValue(10)
        self.terrain_height_slider.valueChanged.connect(self.update_terrain_height)
        layout.addWidget(self.terrain_height_label)
        layout.addWidget(self.terrain_height_slider)

        # Apply button
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_changes)
        layout.addWidget(self.apply_button)

        self.setLayout(layout)

    def update_brush_size(self, value):
        self.brush_size_label.setText(f"Brush Size: {value}")
        self.terrain_painter_app.brush_size = value

    def update_brush_intensity(self, value):
        intensity = value / 10.0
        self.brush_intensity_label.setText(f"Brush Intensity: {intensity}")
        self.terrain_painter_app.brush_intensity = intensity

    def update_terrain_height(self, value):
        height = value / 10.0
        self.terrain_height_label.setText(f"Terrain Height: {height}")
        self.terrain_painter_app.terrain_height = height

    def apply_changes(self):
        # Apply changes to the terrain painter app
        self.terrain_painter_app.apply_changes()