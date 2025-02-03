#!/usr/bin/env python3
import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QSlider,
    QPushButton, QListWidget, QLabel, QComboBox, QLineEdit, QFileDialog
)
from PyQt5.QtCore import Qt, QTimer

# Import your QPanda3D widget – note that it requires a reference to the Panda3D world.
from QPanda3D.QPanda3DWidget import QPanda3DWidget

from direct.actor.Actor import Actor
from direct.interval.IntervalGlobal import Sequence, Parallel, LerpPosInterval, LerpHprInterval, LerpScaleInterval
from panda3d.core import Vec3, CollisionTraverser, CollisionNode, CollisionRay, CollisionHandlerQueue, BitMask32

def lerp_tuple(start, end, t):
    """Linearly interpolates between two tuples element‐wise."""
    return tuple(s * (1 - t) + e * t for s, e in zip(start, end))


class SequenceEditorTab(QWidget):
    def __init__(self, panda3DWorld, parent=None):
        """
        :param panda3DWorld: The Panda3D world instance (e.g., your PandaTest object)
        """
        # Create gizmos for translation control.
        self.gizmo_active = False
        self.current_drag_axis = None
        super(SequenceEditorTab, self).__init__(parent)
        self.panda3DWorld = panda3DWorld

        # Main horizontal layout: left = 3D viewport, right = controls panel.
        main_layout = QHBoxLayout(self)
        
        # --- 3D Viewport (QPanda3D widget) ---
        # Pass the required panda3DWorld to the QPanda3DWidget.
        self.panda_widget = QPanda3DWidget(panda3DWorld)
        main_layout.addWidget(self.panda_widget, 3)
        
        # --- Controls Panel ---
        controls_panel = QWidget()
        controls_layout = QVBoxLayout(controls_panel)
        main_layout.addWidget(controls_panel, 1)
        
        # Timeline slider and label
        self.timeline_label = QLabel("Time: 0.00")
        controls_layout.addWidget(self.timeline_label)
        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setMinimum(0)
        self.timeline_slider.setMaximum(1500)  # 0–1500 represents 0.0 to 15.0 seconds
        self.timeline_slider.setValue(0)
        self.timeline_slider.valueChanged.connect(self.on_slider_change)
        controls_layout.addWidget(self.timeline_slider)
        
        # Buttons for keyframe management
        self.add_keyframe_btn = QPushButton("Add Keyframe")
        self.add_keyframe_btn.clicked.connect(self.add_keyframe)
        controls_layout.addWidget(self.add_keyframe_btn)
        
        self.remove_keyframe_btn = QPushButton("Remove Last Keyframe")
        self.remove_keyframe_btn.clicked.connect(self.remove_last_keyframe)
        controls_layout.addWidget(self.remove_keyframe_btn)
        
        self.play_btn = QPushButton("Play Sequence")
        self.play_btn.clicked.connect(self.play_sequence)
        controls_layout.addWidget(self.play_btn)
        
        # List widget to display keyframes
        self.keyframe_list = QListWidget()
        controls_layout.addWidget(QLabel("Keyframes"))
        controls_layout.addWidget(self.keyframe_list)
        
        # --- Model Selection Section ---
        self.select_model_btn = QPushButton("Select Model")
        self.select_model_btn.clicked.connect(self.select_model)
        controls_layout.addWidget(self.select_model_btn)
        
        # --- Joint/Bone Control Section ---
        self.joint_control_label = QLabel("Joint Control:")
        controls_layout.addWidget(self.joint_control_label)
        
        self.joint_combo = QComboBox()
        controls_layout.addWidget(self.joint_combo)
        self.joint_combo.currentIndexChanged.connect(self.on_joint_selected)
        
        # Joint Position fields
        self.joint_pos_label = QLabel("Joint Pos (x,y,z):")
        controls_layout.addWidget(self.joint_pos_label)
        self.joint_pos_x = QLineEdit("0.0")
        self.joint_pos_y = QLineEdit("0.0")
        self.joint_pos_z = QLineEdit("0.0")
        joint_pos_layout = QHBoxLayout()
        joint_pos_layout.addWidget(self.joint_pos_x)
        joint_pos_layout.addWidget(self.joint_pos_y)
        joint_pos_layout.addWidget(self.joint_pos_z)
        controls_layout.addLayout(joint_pos_layout)
        
        # Joint Rotation fields
        self.joint_rot_label = QLabel("Joint Rot (h,p,r):")
        controls_layout.addWidget(self.joint_rot_label)
        self.joint_rot_h = QLineEdit("0.0")
        self.joint_rot_p = QLineEdit("0.0")
        self.joint_rot_r = QLineEdit("0.0")
        joint_rot_layout = QHBoxLayout()
        joint_rot_layout.addWidget(self.joint_rot_h)
        joint_rot_layout.addWidget(self.joint_rot_p)
        joint_rot_layout.addWidget(self.joint_rot_r)
        controls_layout.addLayout(joint_rot_layout)
        
        # Joint Scale fields
        self.joint_scale_label = QLabel("Joint Scale (x,y,z):")
        controls_layout.addWidget(self.joint_scale_label)
        self.joint_scale_x = QLineEdit("1.0")
        self.joint_scale_y = QLineEdit("1.0")
        self.joint_scale_z = QLineEdit("1.0")
        joint_scale_layout = QHBoxLayout()
        joint_scale_layout.addWidget(self.joint_scale_x)
        joint_scale_layout.addWidget(self.joint_scale_y)
        joint_scale_layout.addWidget(self.joint_scale_z)
        controls_layout.addLayout(joint_scale_layout)
        
        self.apply_joint_transform_btn = QPushButton("Apply Joint Transform")
        self.apply_joint_transform_btn.clicked.connect(self.apply_joint_transform)
        controls_layout.addWidget(self.apply_joint_transform_btn)
        
        # --- Gizmo Controls Section (for visual interactive joint manipulation) ---
        self.gizmo_toggle_btn = QPushButton("Toggle Translation Gizmo")
        self.gizmo_toggle_btn.setCheckable(True)
        self.gizmo_toggle_btn.clicked.connect(self.toggle_gizmo)
        controls_layout.addWidget(self.gizmo_toggle_btn)
        
        controls_layout.addStretch()
        
        # --- Scene Setup ---
        self.setup_scene()
        
        # --- Keyframe Data ---
        self.keyframes = []
        self.timeline_duration = 15.0  # seconds
        self.sequence = None
        
        # Timer for updating UI during playback (optional)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_playback)
        self.playing = False

        # Setup collision traverser and handler for gizmo picking.
        self.setup_gizmo_collision()

        self.create_translation_gizmos()

    def setup_scene(self):
        """
        Initializes the Panda3D scene.
        Loads an Actor (using a default model) and reparents it to the world's render node.
        Also sets up controlled joints for full joint/bone control.
        """
        # Load a default actor.
        self.actor = Actor("models/panda-model")
        self.actor.reparentTo(self.panda3DWorld.render)
        self.actor.setScale(0.005)
        self.actor.setPos(0, 10, 0)
        self.actor.setHpr(0, 0, 0)
        self.setup_joints()

    def setup_joints(self):
        """
        Sets up controlled joints so that each joint can be manipulated.
        Populates self.controlled_joints and fills the joint selection combo box.
        """
        self.controlled_joints = {}
        self.joint_combo.clear()
        for joint in self.actor.getJoints():
            name = joint.getName()
            controlled = self.actor.controlJoint(None, 'modelRoot', name)
            self.controlled_joints[name] = controlled
            self.joint_combo.addItem(name)
        if self.joint_combo.count() > 0:
            self.joint_combo.setCurrentIndex(0)
            self.on_joint_selected(0)

    def select_model(self):
        """
        Opens a file dialog to select a model file and loads it as the actor.
        """
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Model", "", "Model Files (*.egg *.bam *.obj)")
        if fileName:
            self.load_actor_model(fileName)

    def load_actor_model(self, model_path):
        """
        Loads a new actor from the given model path, reparents it to the world's render,
        and sets up joints for full joint control.
        """
        if hasattr(self, "actor") and self.actor:
            self.actor.removeNode()
        self.actor = Actor(model_path)
        self.actor.reparentTo(self.panda3DWorld.render)
        self.actor.setScale(0.005)
        self.actor.setPos(0, 10, 0)
        self.actor.setHpr(0, 0, 0)
        self.setup_joints()
        print(f"Loaded model: {model_path}")

    def on_joint_selected(self, index):
        """
        When a joint is selected from the combo box, update the joint editing fields
        and (if gizmos are active) reposition the gizmo group.
        """
        joint_name = self.joint_combo.currentText()
        if joint_name in self.controlled_joints:
            joint_np = self.controlled_joints[joint_name]
            pos = joint_np.getPos()
            hpr = joint_np.getHpr()
            scale = joint_np.getScale()
            self.joint_pos_x.setText(f"{pos[0]:.2f}")
            self.joint_pos_y.setText(f"{pos[1]:.2f}")
            self.joint_pos_z.setText(f"{pos[2]:.2f}")
            self.joint_rot_h.setText(f"{hpr[0]:.2f}")
            self.joint_rot_p.setText(f"{hpr[1]:.2f}")
            self.joint_rot_r.setText(f"{hpr[2]:.2f}")
            self.joint_scale_x.setText(f"{scale[0]:.2f}")
            self.joint_scale_y.setText(f"{scale[1]:.2f}")
            self.joint_scale_z.setText(f"{scale[2]:.2f}")
            if self.gizmo_active:
                self.update_gizmos_position(joint_np)

    def apply_joint_transform(self):
        """
        Reads the joint editing fields and applies the transform to the selected joint.
        """
        joint_name = self.joint_combo.currentText()
        if joint_name in self.controlled_joints:
            try:
                pos = (float(self.joint_pos_x.text()),
                       float(self.joint_pos_y.text()),
                       float(self.joint_pos_z.text()))
                hpr = (float(self.joint_rot_h.text()),
                       float(self.joint_rot_p.text()),
                       float(self.joint_rot_r.text()))
                scale = (float(self.joint_scale_x.text()),
                         float(self.joint_scale_y.text()),
                         float(self.joint_scale_z.text()))
            except ValueError:
                print("Invalid joint transform values.")
                return
            joint_np = self.controlled_joints[joint_name]
            joint_np.setPos(pos)
            joint_np.setHpr(hpr)
            joint_np.setScale(scale)
            print(f"Applied transform to joint '{joint_name}': pos={pos}, hpr={hpr}, scale={scale}")
            if self.gizmo_active:
                self.update_gizmos_position(joint_np)

    def on_slider_change(self, value):
        """
        Called when the timeline slider is moved.
        The slider value is interpreted as time in hundredths of a second.
        """
        current_time = value / 100.0
        self.timeline_label.setText(f"Time: {current_time:.2f}")
        self.preview_at_time(current_time)

    def add_keyframe(self):
        """
        Adds a keyframe capturing the actor’s current transform and all joint transforms.
        """
        t = self.timeline_slider.value() / 100.0
        keyframe = {
            "time": t,
            "pos": tuple(self.actor.getPos()),
            "hpr": tuple(self.actor.getHpr()),
            "scale": tuple(self.actor.getScale()),
            "joints": {}
        }
        for name, joint_np in self.controlled_joints.items():
            keyframe["joints"][name] = {
                "pos": tuple(joint_np.getPos()),
                "hpr": tuple(joint_np.getHpr()),
                "scale": tuple(joint_np.getScale())
            }
        self.keyframes.append(keyframe)
        self.keyframes.sort(key=lambda k: k["time"])
        self.update_keyframe_list()
        print(f"Added keyframe at time {t:.2f}")

    def remove_last_keyframe(self):
        """Removes the last keyframe, if any."""
        if self.keyframes:
            removed = self.keyframes.pop()
            self.update_keyframe_list()
            print(f"Removed keyframe at time {removed['time']:.2f}")
        else:
            print("No keyframes to remove.")

    def update_keyframe_list(self):
        """Updates the QListWidget with the list of keyframes."""
        self.keyframe_list.clear()
        for kf in self.keyframes:
            self.keyframe_list.addItem(f"t: {kf['time']:.2f} | pos: {kf['pos']}")

    def preview_at_time(self, current_time):
        """
        Interpolates between keyframes to preview the actor's and joints' transforms at the given time.
        """
        if not self.keyframes:
            return

        # Global actor transform
        if current_time <= self.keyframes[0]["time"]:
            kf = self.keyframes[0]
            self.actor.setPos(kf["pos"])
            self.actor.setHpr(kf["hpr"])
            self.actor.setScale(kf["scale"])
            for name, trans in kf.get("joints", {}).items():
                if name in self.controlled_joints:
                    self.controlled_joints[name].setPos(trans["pos"])
                    self.controlled_joints[name].setHpr(trans["hpr"])
                    self.controlled_joints[name].setScale(trans["scale"])
            return

        if current_time >= self.keyframes[-1]["time"]:
            kf = self.keyframes[-1]
            self.actor.setPos(kf["pos"])
            self.actor.setHpr(kf["hpr"])
            self.actor.setScale(kf["scale"])
            for name, trans in kf.get("joints", {}).items():
                if name in self.controlled_joints:
                    self.controlled_joints[name].setPos(trans["pos"])
                    self.controlled_joints[name].setHpr(trans["hpr"])
                    self.controlled_joints[name].setScale(trans["scale"])
            return

        for i in range(len(self.keyframes) - 1):
            start_kf = self.keyframes[i]
            end_kf = self.keyframes[i + 1]
            if start_kf["time"] <= current_time <= end_kf["time"]:
                t = (current_time - start_kf["time"]) / (end_kf["time"] - start_kf["time"])
                new_pos = lerp_tuple(start_kf["pos"], end_kf["pos"], t)
                new_hpr = lerp_tuple(start_kf["hpr"], end_kf["hpr"], t)
                new_scale = lerp_tuple(start_kf["scale"], end_kf["scale"], t)
                self.actor.setPos(new_pos)
                self.actor.setHpr(new_hpr)
                self.actor.setScale(new_scale)
                # Interpolate joints.
                for name in self.controlled_joints.keys():
                    if name in start_kf["joints"] and name in end_kf["joints"]:
                        start_joint = start_kf["joints"][name]
                        end_joint = end_kf["joints"][name]
                        joint_pos = lerp_tuple(start_joint["pos"], end_joint["pos"], t)
                        joint_hpr = lerp_tuple(start_joint["hpr"], end_joint["hpr"], t)
                        joint_scale = lerp_tuple(start_joint["scale"], end_joint["scale"], t)
                        self.controlled_joints[name].setPos(joint_pos)
                        self.controlled_joints[name].setHpr(joint_hpr)
                        self.controlled_joints[name].setScale(joint_scale)
                break

    def play_sequence(self):
        """
        Creates and plays a Panda3D Sequence that interpolates the actor’s and joints' transforms
        through all keyframes.
        """
        if not self.keyframes:
            print("No keyframes to play.")
            return
        
        if self.sequence:
            self.sequence.finish()

        intervals = []
        if self.keyframes[0]["time"] > 0:
            duration = self.keyframes[0]["time"]
            intervals.append(Parallel(
                LerpPosInterval(self.actor, duration, self.keyframes[0]["pos"], startPos=self.actor.getPos()),
                LerpHprInterval(self.actor, duration, self.keyframes[0]["hpr"], startHpr=self.actor.getHpr()),
                LerpScaleInterval(self.actor, duration, self.keyframes[0]["scale"], startScale=self.actor.getScale())
            ))
        for i in range(len(self.keyframes) - 1):
            start_kf = self.keyframes[i]
            end_kf = self.keyframes[i + 1]
            duration = end_kf["time"] - start_kf["time"]
            intervals.append(Parallel(
                LerpPosInterval(self.actor, duration, end_kf["pos"], startPos=start_kf["pos"]),
                LerpHprInterval(self.actor, duration, end_kf["hpr"], startHpr=start_kf["hpr"]),
                LerpScaleInterval(self.actor, duration, end_kf["scale"], startScale=start_kf["scale"])
            ))
        if self.keyframes[-1]["time"] < self.timeline_duration:
            duration = self.timeline_duration - self.keyframes[-1]["time"]
            intervals.append(Parallel(
                LerpPosInterval(self.actor, duration, self.keyframes[-1]["pos"]),
                LerpHprInterval(self.actor, duration, self.keyframes[-1]["hpr"]),
                LerpScaleInterval(self.actor, duration, self.keyframes[-1]["scale"])
            ))
        
        self.sequence = Sequence(*intervals)
        self.sequence.start()
        self.playing = True
        self.timer.start(100)

    def update_playback(self):
        """Stops the timer when the sequence finishes."""
        if self.sequence and not self.sequence.isPlaying():
            self.timer.stop()
            self.playing = False

    # === Gizmo Functionality for Joint Translation ===
    def create_translation_gizmos(self):
        """
        Creates simple arrow gizmos (one per axis) for translation.
        For this example, we load an arrow model and color it appropriately.
        """
        self.gizmo_arrows = {}
        axes = ["x", "y", "z"]
        colors = {"x": (1,0,0,1), "y": (0,1,0,1), "z": (0,0,1,1)}
        hpr_values = {"x": (0,0,-90), "y": (0,0,0), "z": (90,0,0)}
        for axis in axes:
            arrow = loader.loadModel("./editor_models/arrow")
            arrow.setColor(*colors[axis])
            arrow.setScale(0.2)
            arrow.setHpr(hpr_values[axis])
            arrow.reparentTo(self.panda3DWorld.render)
            arrow.hide()
            # Tag the gizmo with its axis for picking.
            arrow.setTag("gizmo_axis", axis)
            self.gizmo_arrows[axis] = arrow

    def update_gizmos_position(self, joint_np):
        """
        Positions the gizmos at the selected joint's world position.
        """
        pos = joint_np.getPos(self.panda3DWorld.render)
        for arrow in self.gizmo_arrows.values():
            arrow.setPos(pos)
            arrow.show()

    def setup_gizmo_collision(self):
        """
        Sets up a collision traverser and queue for gizmo picking.
        (A full implementation would attach collision solids to the gizmo models.)
        """
        self.cTrav = CollisionTraverser()
        self.gizmoPickerQueue = CollisionHandlerQueue()
        self.gizmoPickerRay = CollisionRay()
        ray_node = CollisionNode('gizmoRay')
        ray_node.addSolid(self.gizmoPickerRay)
        ray_node.setFromCollideMask(BitMask32.bit(1))
        ray_node.setIntoCollideMask(BitMask32.allOff())
        self.gizmoPickerNP = self.panda3DWorld.render.attachNewNode(ray_node)
        self.cTrav.addCollider(self.gizmoPickerNP, self.gizmoPickerQueue)
        # Accept mouse click events on the QPanda3DWidget.
        self.panda3DWorld.accept("mouse1", self._on_gizmo_click)
        self.panda3DWorld.accept("mouse1-up", self._on_gizmo_click_up)
        
    def _on_gizmo_click(self, position):
        self.mx, self.my = position['x'], position['y']
        self.is_moving = True
        self.on_gizmo_click()
        self.panda3DWorld.add_task(self.drag_gizmo_task, "on_mouse_click", appendTask=True)
    def _on_gizmo_click_up(self, position):
        self.mx, self.my = position['x'], position['y']
        self.is_moving = False

    def on_gizmo_click(self):
        """
        Called when the user clicks in the 3D viewport.
        Uses the collision system to check if a gizmo was clicked.
        """
        if not self.panda3DWorld.mouseWatcherNode.hasMouse():
            return
        mpos = self.panda3DWorld.mouseWatcherNode.getMouse()
        self.gizmoPickerRay.setFromLens(self.panda3DWorld.camNode, mpos.getX(), mpos.getY())
        self.cTrav.traverse(self.panda3DWorld.render)
        if self.gizmoPickerQueue.getNumEntries() > 0:
            self.gizmoPickerQueue.sortEntries()
            picked = self.gizmoPickerQueue.getEntry(0).getIntoNodePath()
            axis = picked.findNetTag("gizmo_axis").getTag("gizmo_axis")
            if axis:
                print(f"Clicked gizmo for axis: {axis}")
                self.current_drag_axis = axis
                # Start tracking mouse movement.
                self.panda3DWorld.accept("mouse1-up", self.end_gizmo_drag)
                self.task = self.panda3DWorld.taskMgr.add(self.drag_gizmo_task, "DragGizmoTask")

    def drag_gizmo_task(self, task):
        """
        Called every frame while dragging a gizmo.
        Updates the selected joint's position along the gizmo's axis.
        (This is a simplified example that moves the joint along one axis based on mouse X delta.)
        """
        if not self.panda3DWorld.mouseWatcherNode.hasMouse():
            return task.cont
        if self.is_moving == False:
            task.remove(task)
        mpos = self.panda3DWorld.mouseWatcherNode.getMouse()
        # Compute a simple delta value (this is a simplistic implementation).
        delta = mpos.getX() * 0.1  # scale factor for movement
        joint_name = self.joint_combo.currentText()
        if joint_name in self.controlled_joints:
            joint_np = self.controlled_joints[joint_name]
            pos = joint_np.getPos()
            if self.current_drag_axis == "x":
                new_pos = (pos[0] + delta, pos[1], pos[2])
                joint_np.setPos(new_pos)
                self.joint_pos_x.setText(f"{new_pos[0]:.2f}")
                self.joint_pos_y.setText(f"{new_pos[1]:.2f}")
                self.joint_pos_z.setText(f"{new_pos[2]:.2f}")
            elif self.current_drag_axis == "y":
                new_pos = (pos[0], pos[1] + delta, pos[2])
                joint_np.setPos(new_pos)
                self.joint_pos_x.setText(f"{new_pos[0]:.2f}")
                self.joint_pos_y.setText(f"{new_pos[1]:.2f}")
                self.joint_pos_z.setText(f"{new_pos[2]:.2f}")
            elif self.current_drag_axis == "z":
                new_pos = (pos[0], pos[1], pos[2] + delta)
                joint_np.setPos(new_pos)
                # Also update the joint position fields.
                self.joint_pos_x.setText(f"{new_pos[0]:.2f}")
                self.joint_pos_y.setText(f"{new_pos[1]:.2f}")
                self.joint_pos_z.setText(f"{new_pos[2]:.2f}")
        return task.cont

    def end_gizmo_drag(self):
        """
        Called when the user releases the mouse button to end gizmo dragging.
        """
        self.current_drag_axis = None
        self.panda_widget.ignore("mouse1-up")
        if hasattr(self, "task"):
            self.panda3DWorld.taskMgr.remove(self.task)

    def toggle_gizmo(self, checked):
        """
        Toggles the visibility (and active status) of the translation gizmos.
        When turned on, the gizmos are repositioned at the currently selected joint.
        """
        self.gizmo_active = checked
        joint_name = self.joint_combo.currentText()
        if joint_name in self.controlled_joints:
            self.update_gizmos_position(self.controlled_joints[joint_name])
        else:
            for arrow in self.gizmo_arrows.values():
                arrow.hide()

    def play_sequence(self):
        """
        Creates and plays a Panda3D Sequence that interpolates the actor’s and joints' transforms
        through all keyframes.
        """
        if not self.keyframes:
            print("No keyframes to play.")
            return
        
        if self.sequence:
            self.sequence.finish()

        intervals = []
        if self.keyframes[0]["time"] > 0:
            duration = self.keyframes[0]["time"]
            intervals.append(Parallel(
                LerpPosInterval(self.actor, duration, self.keyframes[0]["pos"], startPos=self.actor.getPos()),
                LerpHprInterval(self.actor, duration, self.keyframes[0]["hpr"], startHpr=self.actor.getHpr()),
                LerpScaleInterval(self.actor, duration, self.keyframes[0]["scale"], startScale=self.actor.getScale())
            ))
        for i in range(len(self.keyframes) - 1):
            start_kf = self.keyframes[i]
            end_kf = self.keyframes[i + 1]
            duration = end_kf["time"] - start_kf["time"]
            intervals.append(Parallel(
                LerpPosInterval(self.actor, duration, end_kf["pos"], startPos=start_kf["pos"]),
                LerpHprInterval(self.actor, duration, end_kf["hpr"], startHpr=start_kf["hpr"]),
                LerpScaleInterval(self.actor, duration, end_kf["scale"], startScale=start_kf["scale"])
            ))
        if self.keyframes[-1]["time"] < self.timeline_duration:
            duration = self.timeline_duration - self.keyframes[-1]["time"]
            intervals.append(Parallel(
                LerpPosInterval(self.actor, duration, self.keyframes[-1]["pos"]),
                LerpHprInterval(self.actor, duration, self.keyframes[-1]["hpr"]),
                LerpScaleInterval(self.actor, duration, self.keyframes[-1]["scale"])
            ))
        
        self.sequence = Sequence(*intervals)
        self.sequence.start()
        self.playing = True
        self.timer.start(100)

    def update_playback(self):
        """Stops the timer when the sequence finishes."""
        if self.sequence and not self.sequence.isPlaying():
            self.timer.stop()
            self.playing = False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # When instantiating, pass a Panda3D world object. For testing, create a dummy world.
    from QPanda3D.Panda3DWorld import Panda3DWorld
    dummy_world = Panda3DWorld(1024, 768)
    editor_tab = SequenceEditorTab(dummy_world)
    editor_tab.setWindowTitle("QPanda3D Sequence Editor Tab with Gizmos")
    editor_tab.resize(1200, 800)
    editor_tab.show()
    sys.exit(app.exec_())
