#!/usr/bin/python3
# -*- coding: utf-8 -*-
import sys, os
from base64 import b64encode
import tempfile
import itertools  # for a counter

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, QPoint, QPointF, QLine, QRectF, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QFont, QBrush, QPalette, QPen, QPolygon, QPainterPath, QPixmap
from PyQt5.QtWidgets import QWidget, QFrame, QScrollArea, QVBoxLayout

# Global style settings
__textColor__ = QColor(187, 187, 187)
__backgroudColor__ = QColor(60, 63, 65)
__font__ = QFont('Decorative', 10)

class VideoSample:
    def __init__(self, duration, color=Qt.darkYellow, picture=None, audio=None):
        self.duration = duration
        self.color = color            # Floating color
        self.defColor = color         # Default color
        if picture is not None:
            self.picture = picture.scaledToHeight(45)
        else:
            self.picture = None
        self.startPos = 0             # Initial position (in pixels)
        self.endPos = self.duration   # End position (in seconds)

# A global counter for key frame IDs (used if parent does not supply one).
_keyframe_id_counter = itertools.count()

class KeyFrame:
    """A simple key frame class that holds a time (in seconds), associated data, and an ID.
    
    If the provided data dictionary contains an "id" key, that ID is used.
    Otherwise, a new unique ID is generated.
    """
    def __init__(self, time, data=None):
        if data is not None and "id" in data:
            self.id = data["id"]
        else:
            self.id = next(_keyframe_id_counter)
        self.time = time
        self.data = data if data is not None else {}
        # Always store the id in the data dictionary.
        self.data["id"] = self.id

class QTimeLine(QWidget):
    positionChanged = pyqtSignal(int)
    selectionChanged = pyqtSignal(VideoSample)
    # Signal emits the key frame's id (int) and the new time (float) when changed.
    keyFrameChanged = pyqtSignal(int, float)
    keyFrameCreated = pyqtSignal(int, float)
    # Signal emits the removed key frame's id (int) when a key frame is removed.
    keyFrameRemoved = pyqtSignal(int)
    
    timelineSliderMoved = pyqtSignal(float)

    def __init__(self, duration, length):
        super(QWidget, self).__init__()
        self.duration = duration
        self.length = length

        # Timeline appearance variables
        self.backgroundColor = __backgroudColor__
        self.textColor = __textColor__
        self.font = __font__
        self.pos = None               # Latest mouse position
        self.pointerPos = None        # Latest pointer (x) position (in pixels)
        self.pointerTimePos = None    # Corresponding timeline time (in seconds)
        self.selectedSample = None
        self.clicking = False         # True if left mouse button is held
        self.is_in = False            # True if mouse is inside the widget
        self.videoSamples = []        # List of video samples

        # --- Key frame variables ---
        self.keyFrames = []           # List of key frame objects (instances of KeyFrame)
        self.kfTolerance = 7          # Tolerance (in pixels) to detect if a key frame is near the pointer
        self.selectedKeyFrameIndex = None  # Index of the currently selected key frame

        # Playback-related variables
        self.playing = False          # Whether timeline playback is active
        self.play_timer = QtCore.QTimer(self)
        self.play_timer.timeout.connect(self.playbackStep)  # call playbackStep on each timer tick

        self.setMouseTracking(True)   # Enable mouse move events even when not clicking
        self.setAutoFillBackground(True)  # Enable widget background filling

        self.initUI()
        
    def initUI(self):
        self.setGeometry(300, 300, self.length, 200)
        self.setWindowTitle("Timeline Editor (Key Frames: Select/Move/Delete)")
        pal = QPalette()
        pal.setColor(QPalette.Background, self.backgroundColor)
        self.setPalette(pal)
        # Enable focus to capture key events.
        self.setFocusPolicy(Qt.StrongFocus)

    def paintEvent(self, event):
        qp = QPainter()
        qp.begin(self)
        qp.setPen(self.textColor)
        qp.setFont(self.font)
        qp.setRenderHint(QPainter.Antialiasing)
        scale = self.getScale()

        # Draw time labels along the timeline
        w = 0
        while w <= self.width():
            qp.drawText(w - 50, 0, 100, 100, Qt.AlignHCenter, self.get_time_string(w * scale))
            w += 100

        # Draw the main timeline line
        qp.setPen(QPen(Qt.darkCyan, 5, Qt.SolidLine))
        qp.drawLine(0, 40, self.width(), 40)

        # Draw dashed guide lines along the timeline
        point = 0
        qp.setPen(QPen(self.textColor))
        while point <= self.width():
            if point % 30 != 0:
                qp.drawLine(3 * point, 40, 3 * point, 30)
            else:
                qp.drawLine(3 * point, 40, 3 * point, 20)
            point += 10

        # Draw key frame markers as circles on the timeline
        for i, kf in enumerate(self.keyFrames):
            x = kf.time / scale  # Convert key frame time (seconds) to x coordinate (pixels)
            if i == self.selectedKeyFrameIndex:
                qp.setPen(QPen(Qt.yellow, 2, Qt.SolidLine))
                qp.setBrush(QBrush(Qt.yellow))
            else:
                qp.setPen(QPen(Qt.red, 2, Qt.SolidLine))
                qp.setBrush(QBrush(Qt.red))
            qp.drawEllipse(QPointF(x, 40), 5, 5)

        # Draw vertical line at mouse pointer if inside the widget
        if self.pos is not None and self.is_in:
            qp.drawLine(self.pos.x(), 0, self.pos.x(), 40)

        # Prepare pointer marker (triangle and vertical line)
        if self.pointerPos is not None:
            pointer_x = self.pointerTimePos / scale if self.pointerTimePos is not None else 0
            line = QLine(QPoint(pointer_x, 40), QPoint(pointer_x, self.height()))
            poly = QPolygon([QPoint(pointer_x - 10, 20),
                             QPoint(pointer_x + 10, 20),
                             QPoint(pointer_x, 40)])
        else:
            line = QLine(QPoint(0, 0), QPoint(0, self.height()))
            poly = QPolygon([QPoint(-10, 20), QPoint(10, 20), QPoint(0, 40)])

        # Draw video samples on the timeline
        t = 0
        for sample in self.videoSamples:
            path = QPainterPath()
            path.addRoundedRect(QRectF(t / scale, 50, sample.duration / scale, 200), 10, 10)
            qp.setClipPath(path)
            path = QPainterPath()
            qp.setPen(sample.color)
            path.addRoundedRect(QRectF(t / scale, 50, sample.duration / scale, 50), 10, 10)
            sample.startPos = t / scale
            sample.endPos = t / scale + sample.duration / scale
            qp.fillPath(path, sample.color)
            qp.drawPath(path)
            if sample.picture is not None:
                if sample.picture.size().width() < sample.duration / scale:
                    path = QPainterPath()
                    path.addRoundedRect(QRectF(t / scale, 52.5, sample.picture.size().width(), 45), 10, 10)
                    qp.setClipPath(path)
                    qp.drawPixmap(QRectF(t / scale, 52.5, sample.picture.size().width(), 45).toRect(), sample.picture)
                else:
                    path = QPainterPath()
                    path.addRoundedRect(QRectF(t / scale, 52.5, sample.duration / scale, 45), 10, 10)
                    qp.setClipPath(path)
                    pic = sample.picture.copy(0, 0, int(sample.duration / scale), 45)
                    qp.drawPixmap(QRectF(t / scale, 52.5, sample.duration / scale, 45).toRect(), pic)
            t += sample.duration

        # Reset clip path
        path = QPainterPath()
        path.addRect(QRectF(self.rect()))
        qp.setClipPath(path)

        qp.setPen(Qt.darkCyan)
        qp.setBrush(QBrush(Qt.darkCyan))
        qp.drawPolygon(poly)
        qp.drawLine(line)
        qp.end()

    def mouseMoveEvent(self, e):
        self.pos = e.pos()
        if self.clicking and self.selectedKeyFrameIndex is not None:
            new_time = e.pos().x() * self.getScale()
            new_time = max(0, min(new_time, self.duration))  # Clamp to timeline bounds
            kf = self.keyFrames[self.selectedKeyFrameIndex]
            kf.time = new_time
            if isinstance(kf.data, dict):
                kf.data["time"] = new_time
            self.keyFrameChanged.emit(kf.id, new_time)
            self.pointerPos = e.pos().x()
            self.pointerTimePos = self.pointerPos * self.getScale()
            self.positionChanged.emit(e.pos().x())
        elif self.clicking:
            x = e.pos().x()
            self.pointerPos = x
            self.pointerTimePos = self.pointerPos * self.getScale()
            self.positionChanged.emit(x)
        self.update()
        self.on_slider_changed(0)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            x = e.pos().x()
            self.pointerPos = x
            self.pointerTimePos = x * self.getScale()
            self.positionChanged.emit(x)
            idx = self.getKeyFrameAtPos(x)
            if idx is not None:
                self.selectedKeyFrameIndex = idx
            else:
                self.selectedKeyFrameIndex = None
            self.checkSelection(x)
            self.update()
            self.on_slider_changed(0)
            self.clicking = True

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicking = False
            self.update()

    def enterEvent(self, e):
        self.is_in = True

    def leaveEvent(self, e):
        self.is_in = False
        self.update()

    def keyPressEvent(self, e):
        # Toggle playback on space press.
        if e.key() == Qt.Key_Space:
            if self.playing:
                self.stopPlayback()
            else:
                self.startPlayback()
        # Delete/backspace to remove key frame.
        elif e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            if self.selectedKeyFrameIndex is not None:
                removed_kf = self.keyFrames[self.selectedKeyFrameIndex]
                print(f"Deleted key frame at time: {removed_kf.time:.2f} seconds (id: {removed_kf.id})")
                self.keyFrameRemoved.emit(removed_kf.id)
                del self.keyFrames[self.selectedKeyFrameIndex]
                self.selectedKeyFrameIndex = None
                self.update()
        else:
            super().keyPressEvent(e)

    # We no longer need to override keyReleaseEvent for space toggling.
    # def keyReleaseEvent(self, e):
    #     super().keyReleaseEvent(e)

    def startPlayback(self):
        """Begin automatic dragging/updating of the timeline pointer."""
        self.playing = True
        # For example, update every 50ms (adjust interval as needed).
        self.play_timer.start(50)
        
        print("Playback started...")

    def stopPlayback(self):
        """Stop automatic timeline playback."""
        if self.playing:
            self.play_timer.stop()
            self.playing = False
            print("Playback stopped.")

    def playbackStep(self):
        """
        This function is called repeatedly by the timer.
        It advances the pointerTimePos (and pointerPos) to simulate playback.
        """
        dt = 0.1  # Increase time by 0.1 seconds per step (adjust as needed)
        if self.pointerTimePos is None:
            self.pointerTimePos = 0
        else:
            self.pointerTimePos += dt
            if self.pointerTimePos > self.duration:
                self.pointerTimePos = self.duration
                self.stopPlayback()
        # Calculate pointer position in pixels.
        self.pointerPos = self.pointerTimePos / self.getScale()
        self.update()
        self.on_slider_changed(0)
        # Optionally, you can emit a signal here to inform others that time has advanced.
        # self.timelineSliderMoved.emit(self.pointerTimePos)

    def checkSelection(self, x):
        for sample in self.videoSamples:
            if sample.startPos < x < sample.endPos:
                sample.color = Qt.darkCyan
                if self.selectedSample is not sample:
                    self.selectedSample = sample
                    self.selectionChanged.emit(sample)
            else:
                sample.color = sample.defColor

    def get_time_string(self, seconds):
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return "%02d:%02d:%02d" % (h, m, s)
    
    def on_slider_changed(self, value):
        """
        Slot connected to the QSlider's valueChanged signal.
        Converts the slider value to a time (in seconds) and emits our custom signal.
        """
        # For example, if the slider value is scaled by 100:
        x = self.pointerTimePos if self.pointerTimePos is not None else 0
        new_time = x * 100  # Adjust scaling as needed.
        self.timelineSliderMoved.emit(new_time)

    def getScale(self):
        return float(self.duration) / float(self.width())

    def getDuration(self):
        return self.duration

    def getSelectedSample(self):
        return self.selectedSample

    def setBackgroundColor(self, color):
        self.backgroundColor = color

    def setTextColor(self, color):
        self.textColor = color

    def setTextFont(self, font):
        self.font = font

    # --- Key Frame Methods ---
    def addKeyFrame(self, time_position, data=None):
        if 0 <= time_position <= self.duration:
            tolerance = self.kfTolerance * self.getScale()
            if not any(abs(kf.time - time_position) < tolerance for kf in self.keyFrames):
                new_kf = KeyFrame(time_position, data)
                self.keyFrames.append(new_kf)
                self.keyFrames.sort(key=lambda kf: kf.time)
                self.keyFrameCreated.emit(new_kf.id, time_position)
                self.update()
                return new_kf.time
        return None

    def removeKeyFrame(self, time_position, tolerance=0.1):
        self.keyFrames = [kf for kf in self.keyFrames if abs(kf.time - time_position) > tolerance]
        self.update()

    def clearKeyFrames(self):
        self.keyFrames = []
        self.selectedKeyFrameIndex = None
        self.update()

    def triggerAddKeyFrame(self, data):
        self.time_to_add = self.pointerTimePos if self.pointerTimePos is not None else 0
        self.addKeyFrame(self.time_to_add, data=data)
        print(f"Added key frame at time: {self.time_to_add:.2f} seconds")
        return self.time_to_add

    def getKeyFrameAtPos(self, x_pos):
        scale = self.getScale()
        for i, kf in enumerate(self.keyFrames):
            marker_x = kf.time / scale
            if abs(x_pos - marker_x) <= self.kfTolerance:
                return i
        return None

# --- Example usage ---
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    timeline = QTimeLine(duration=300, length=800)

    timeline.videoSamples.append(VideoSample(60, color=Qt.darkYellow))
    timeline.videoSamples.append(VideoSample(90, color=Qt.blue))
    timeline.videoSamples.append(VideoSample(150, color=Qt.green))

    # Connect the keyFrameChanged signal.
    def on_keyframe_changed(kf_id, new_time):
        print(f"Parent: KeyFrame id {kf_id} changed to time {new_time:.2f} seconds")
    timeline.keyFrameChanged.connect(on_keyframe_changed)
    
    # Connect the keyFrameRemoved signal.
    def on_keyframe_removed(kf_id):
        print(f"Parent: KeyFrame id {kf_id} was removed.")
    timeline.keyFrameRemoved.connect(on_keyframe_removed)

    timeline.show()

    # A button to add a key frame.
    btn = QtWidgets.QPushButton("Add Key Frame")
    btn.resize(150, 40)
    btn.move(820, 50)
    btn.show()
    btn.clicked.connect(lambda: timeline.triggerAddKeyFrame({
        "id": 1001, 
        "time": 0, 
        "pos": (0, 0, 0),
        "hpr": (0, 0, 0),
        "scale": (1, 1, 1),
        "joints": {}
    }))

    sys.exit(app.exec_())
