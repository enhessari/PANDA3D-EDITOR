#!/usr/bin/env python3
import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QSlider,
    QPushButton, QListWidget, QLabel, QComboBox, QLineEdit, QFileDialog 
)
from PyQt5.QtCore import Qt, QTimer

import qtimeline


# Import your QPanda3D widget – it must accept a world reference.
from QPanda3D.QPanda3DWidget import QPanda3DWidget

from direct.actor.Actor import Actor
from direct.interval.IntervalGlobal import Sequence, Parallel, LerpPosInterval, LerpHprInterval, LerpScaleInterval
from panda3d.core import (
    Vec3, Point3, CollisionTraverser, CollisionNode, CollisionRay,
    CollisionHandlerQueue, BitMask32, CollisionTube, CollisionSphere, GeomNode
)

def lerp_tuple(start, end, t):
    """Linearly interpolates between two tuples element‐wise."""
    return tuple(s * (1 - t) + e * t for s, e in zip(start, end))

class SequenceEditorTab(QWidget):
    def __init__(self, panda3DWorld, parent=None):
        """
        :param panda3DWorld: The Panda3D world instance (e.g., your PandaTest object)
        """
        
        
        
        
        
        # Gizmo state variables.
        self.gizmo_active = False
        self.current_drag_axis = None
        self.last_mouse_pos = None
        
        self.gizmotask = True
        
        

        super(SequenceEditorTab, self).__init__(parent)
        self.panda3DWorld = panda3DWorld


        main_vlayout = QVBoxLayout(self)
        
        # --- Set up the main layout ---
        main_layout = QHBoxLayout(self)
        
        
        
        
        
        # --- 3D Viewport ---
        self.panda_widget = QPanda3DWidget(panda3DWorld)
        main_layout.addWidget(self.panda_widget, 3)
        
        # --- Controls Panel ---
        controls_panel = QWidget()
        controls_layout = QVBoxLayout(controls_panel)
        main_layout.addWidget(controls_panel)
        
        # Timeline slider and label.
        self.timeline_label = QLabel("Time: 0.00")
        controls_layout.addWidget(self.timeline_label)
        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setMinimum(0)
        self.timeline_slider.setMaximum(1500)  # Represents 0.0 to 15.0 seconds (scaled by 100)
        self.timeline_slider.setValue(0)
        self.timeline_slider.valueChanged.connect(self.on_slider_change)
        controls_layout.addWidget(self.timeline_slider)
        
        # Keyframe management buttons.
        self.add_keyframe_btn = QPushButton("Add Keyframe")
        self.add_keyframe_btn.clicked.connect(self.add_keyframe)
        controls_layout.addWidget(self.add_keyframe_btn)
        
        self.remove_keyframe_btn = QPushButton("Remove Last Keyframe")
        self.remove_keyframe_btn.clicked.connect(self.remove_last_keyframe)
        controls_layout.addWidget(self.remove_keyframe_btn)
        
        self.play_btn = QPushButton("Play Sequence")
        self.play_btn.clicked.connect(self.play_sequence)
        controls_layout.addWidget(self.play_btn)
        
        # Keyframe list.
        self.keyframe_list = QListWidget()
        controls_layout.addWidget(QLabel("Keyframes"))
        controls_layout.addWidget(self.keyframe_list)
        
        # Model selection section.
        self.select_model_btn = QPushButton("Select Model")
        self.select_model_btn.clicked.connect(self.select_model)
        controls_layout.addWidget(self.select_model_btn)
        
        # Joint/Bone control section.
        self.joint_control_label = QLabel("Joint Control:")
        controls_layout.addWidget(self.joint_control_label)
        self.joint_combo = QComboBox()
        controls_layout.addWidget(self.joint_combo)
        self.joint_combo.currentIndexChanged.connect(self.on_joint_selected)
        
        # Joint position fields.
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
        
        # Joint rotation fields.
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
        
        # Joint scale fields.
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
        
        # Gizmo toggle button.
        self.gizmo_toggle_btn = QPushButton("Toggle Translation Gizmo")
        self.gizmo_toggle_btn.setCheckable(True)
        self.gizmo_toggle_btn.clicked.connect(self.toggle_gizmo)
        controls_layout.addWidget(self.gizmo_toggle_btn)
        
        controls_layout.addStretch()
        # ✅ Add the main content area (3D viewport + controls)
        
        
        content_container = QWidget()
        content_layout = QHBoxLayout(content_container)
        main_vlayout.addWidget(content_container)  # Make it take up most of the space

        # ✅ Create a container for the timeline (so it sits at the bottom)
        timeline_container = QWidget()
        timeline_layout = QHBoxLayout(timeline_container)

        # ✅ Create the custom QTimeLine widget
        self.timeline = qtimeline.QTimeLine(15, 1000)  # 15 seconds, 1000 frames
        
        self.timeline.keyFrameChanged.connect(lambda kf_id, new_time: self.keyframe_change(kf_id, new_time))
        self.timeline.keyFrameRemoved.connect(lambda kf_id: self.keyframe_remove(kf_id))
        self.timeline.timelineSliderMoved.connect(lambda time: self.on_slider_change(time))

        
        
        # ✅ Add the timeline widget
        timeline_layout.addWidget(self.timeline)

        # ✅ Add the timeline container at the bottom
        main_vlayout.addLayout(main_layout)
        main_vlayout.addLayout(timeline_layout)
        main_vlayout.addWidget(timeline_container, 3)  # Make it sit at the bottom
        
        # --- Scene Setup ---
        self.setup_scene()
        
        # --- Keyframe Data ---
        self.keyframes = []
        self.timeline_duration = 15.0  # seconds.
        self.sequence = None
        
        # Timer for playback updates.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_playback)
        self.playing = False

        # --- Gizmo Setup ---
        self.create_translation_gizmos()

        # Accept mouse1 events from the Panda3D world.
        #self.panda3DWorld.accept("mouse1", self._on_gizmo_click)

    def keyframe_change(self, kf_id, new_time):
        # Loop through the parent's keyframes list and update the keyframe with the matching id.
        for kf in self.keyframes:
            if kf.get("id") == kf_id:
                kf["time"] = new_time
                print(f"Updated keyframe id {kf_id} to new time {new_time:.2f}")
                break
        # Refresh the keyframe list widget to reflect the changes.
        self.update_keyframe_list()
    
    def keyframe_remove(self, kf_id):
        # Loop through the parent's keyframes list and update the keyframe with the matching id.
        for kf in self.keyframes:
            if kf.get("id") == kf_id:
                print(f"deleted keyframe id {kf_id}")
                self.keyframes.remove(kf)
                break
        # Refresh the keyframe list widget to reflect the changes.
        self.update_keyframe_list()
        
    def setup_scene(self):
        """Loads a default actor and sets up joints."""
        self.actor = Actor("models/panda-model")
        self.actor.reparentTo(self.panda3DWorld.render)
        self.actor.setScale(0.005)
        self.actor.setPos(0, 10, 0)
        self.actor.setHpr(0, 0, 0)
        self.setup_joints()

    def setup_joints(self):
        """Controls all joints and populates the joint selection combo."""
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
        """Opens a file dialog and loads a new model."""
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Model", "", "Model Files (*.egg *.bam *.obj)")
        if fileName:
            self.load_actor_model(fileName)

    def load_actor_model(self, model_path):
        """Loads and sets up a new actor."""
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
        """Updates the joint transform fields and gizmo positions."""
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
        """Applies the transform values from the UI to the selected joint."""
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
        """Called when the timeline slider changes."""
        current_time = value / 100.0
        self.timeline_label.setText(f"Time: {current_time:.2f}")
        self.preview_at_time(current_time)

    def add_keyframe(self):
        t = self.timeline_slider.value() / 100.0
        # Ensure default values are used if needed.
        pos = tuple(self.actor.getPos()) if self.actor.getPos() is not None else (0, 0, 0)
        hpr = tuple(self.actor.getHpr()) if self.actor.getHpr() is not None else (0, 0, 0)
        scale = tuple(self.actor.getScale()) if self.actor.getScale() is not None else (1, 1, 1)

        keyframe = {
            "time": t,
            "pos": pos,
            "hpr": hpr,
            "scale": scale,
            "joints": {}
        }
        for name, joint_np in self.controlled_joints.items():
            keyframe["joints"][name] = {
                "pos": tuple(joint_np.getPos()) if joint_np.getPos() is not None else (0, 0, 0),
                "hpr": tuple(joint_np.getHpr()) if joint_np.getHpr() is not None else (0, 0, 0),
                "scale": tuple(joint_np.getScale()) if joint_np.getScale() is not None else (1, 1, 1)
            }
        t = self.timeline.triggerAddKeyFrame(keyframe)
        keyframe["time"] = t
        self.keyframes.append(keyframe)
        self.keyframes.sort(key=lambda k: k["time"])
        self.update_keyframe_list()
        print(f"Added keyframe at time {t:.2f}")

    def remove_last_keyframe(self):
        """Removes the last keyframe."""
        if self.keyframes:
            removed = self.keyframes.pop()
            self.update_keyframe_list()
            print(f"Removed keyframe at time {removed['time']:.2f}")
        else:
            print("No keyframes to remove.")

    def update_keyframe_list(self):
        """Updates the keyframe list widget."""
        self.keyframe_list.clear()
        for kf in self.keyframes:
            self.keyframe_list.addItem(f"t: {kf['time']:.2f} | pos: {kf['pos']}")

    def preview_at_time(self, current_time):
        """
        Interpolates transforms between keyframes and applies them to the actor and joints.
        """
        if not self.keyframes:
            return

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
        Plays a sequence interpolating the actor’s and joints' transforms.
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
        """Stops the timer when playback is finished, and updates gizmo positions."""
        if self.sequence and not self.sequence.isPlaying():
            self.timer.stop()
            self.playing = False
        elif self.gizmo_active:
            current_joint_name = self.joint_combo.currentText()
            if current_joint_name in self.controlled_joints:
                self.update_gizmos_position(self.controlled_joints[current_joint_name])

    def create_translation_gizmos(self):
        """
        Creates arrow gizmos with collision geometry.
        """
        self.gizmo_parent = self.panda3DWorld.render.attachNewNode("gizmo_parent")
        self.gizmo_arrows = {}
        axes = ["x", "y", "z"]
        colors = {"x": (1, 0, 0, 1), "y": (0, 1, 0, 1), "z": (0, 0, 1, 1)}
        hpr_values = {"x": (0, 0, -90), "y": (0, 0, 0), "z": (90, 0, 0)}

        # Try to load the arrow model from a custom path.
        try:
            arrow_model = self.panda3DWorld.loader.loadModel("./editor_models/arrow")
            arrow_model.setTag("arrow", "1")
        except Exception as e:
            print("Error loading arrow model, using fallback sphere:", e)
            arrow_model = self.panda3DWorld.loader.loadModel("models/misc/sphere")

        # Clear pre-existing nodes.
        arrow_model.clearModelNodes()


        for axis in axes:
            arrow = arrow_model.copyTo(self.panda3DWorld.render)
            arrow.reparentTo(self.panda3DWorld.render)
            arrow.setColor(*colors[axis])
            arrow.setScale(0.5)  # Increase scale for visibility.
            arrow.setHpr(hpr_values[axis])
            arrow.hide()
            # Tag the arrow so we can identify its axis.
            arrow.setTag("gizmo_axis", axis)
            arrow.setTag("arrow", axis)
            self.gizmo_arrows[axis] = arrow
            arrow_model.set_collide_mask(BitMask32.bit(10))
            arrow.set_collide_mask(BitMask32.bit(10))
            print(f"Created gizmo for axis: {axis}")
            bounds = arrow.getBounds()  # This returns a bounding volume (usually a sphere).
            center = bounds.getCenter()  # Center in the arrow's coordinate space.
            radius = bounds.getRadius()
            if arrow.find("**/+CollisionNode").isEmpty():
                print("is empty")
                cn = CollisionNode(f"gizmo_{axis}_col")
                cn.addSolid(CollisionSphere(0.5, 0, 0, radius))
                

                cn.setFromCollideMask(BitMask32.bit(10))
                cn.setIntoCollideMask(BitMask32.bit(10))
                
                cn.setCollideMask(BitMask32.bit(10))
                cn.setTag("arrow", axis)
                arrow.attachNewNode(cn)

    def update_gizmos_position(self, joint_np):
        """
        Parents the gizmos to the selected joint so that they automatically follow it.
        """
        if not joint_np:
            return
        for arrow in self.gizmo_arrows.values():
            # Here you can adjust the arrow's offset relative to the joint.
            arrow.setPos(0, 0, 0)
            arrow.setScale(1)
            arrow.show()

    def _on_gizmo_click(self, axis):
        print(f"Clicked gizmo axis: {axis}")
        self.current_drag_axis = axis
        self.last_mouse_pos = self.panda3DWorld.mouseWatcherNode.getMouse()
        self.panda3DWorld.taskMgr.add(self.drag_gizmo_task, "DragGizmoTask")


    def _on_gizmo_click_up(self):
        """
        Called on mouse release; stops gizmo dragging.
        """
        self.current_drag_axis = None
        self.panda3DWorld.ignore("mouse1-up")
        if self.panda3DWorld.taskMgr.hasTaskNamed("DragGizmoTask"):
            self.panda3DWorld.taskMgr.remove("DragGizmoTask")
            
    def start_gizmo_drag(self, collision_entry):
        # You can use the collision_entry if you want to know which gizmo was hit.
        picked_np = collision_entry.getIntoNodePath()
        print("it doesn't")
        if picked_np and not picked_np.hasTag("arrow"):
            picked_np = picked_np.getParent()
            print("it does")
        if picked_np:
            axis = picked_np.getTag("gizmo_axis")
            print(f"Global picker reports gizmo axis hit: {axis}")
            self.current_drag_axis = axis
            self.last_mouse_pos = self.panda3DWorld.mouseWatcherNode.getMouse()
            # Add your drag task. For example:
            self.gizmotask = True
            self.panda3DWorld.taskMgr.add(self.drag_gizmo_task, "drag_gizmo_task", appendTask=True)
            
    def stop_gizmo_task(self):
        self.gizmotask = False

    def drag_gizmo_task(self, task):
        """
        Called each frame while dragging a gizmo.
        Computes the mouse delta and moves the joint along the selected axis.
        """
        if self.gizmotask:
            current_mouse = self.panda3DWorld.mouseWatcherNode.getMouse()
            delta = current_mouse - self.last_mouse_pos
            self.last_mouse_pos = current_mouse

            move_speed = 1.0  # Adjust as necessary.
            movement = Vec3(0, 0, 0)
            if self.current_drag_axis == "x":
                movement = Vec3(delta.x * move_speed, 0, 0)
            elif self.current_drag_axis == "y":
                movement = Vec3(0, delta.x * move_speed, 0)
            elif self.current_drag_axis == "z":
                movement = Vec3(0, 0, delta.x * move_speed)

            joint_name = self.joint_combo.currentText()
            if joint_name in self.controlled_joints:
                joint_np = self.controlled_joints[joint_name]
                new_pos = joint_np.getPos() + movement
                joint_np.setPos(new_pos)
                self.joint_pos_x.setText(f"{new_pos[0]:.2f}")
                self.joint_pos_y.setText(f"{new_pos[1]:.2f}")
                self.joint_pos_z.setText(f"{new_pos[2]:.2f}")
                self.update_gizmos_position(joint_np)
            print("dragging gizmo")
            return task.cont
        else:
            return task.done

    def toggle_gizmo(self, checked):
        """
        Toggles gizmo visibility and updates its position.
        """
        self.gizmo_active = checked
        joint_name = self.joint_combo.currentText()
        if joint_name in self.controlled_joints:
            self.update_gizmos_position(self.controlled_joints[joint_name])
        else:
            for arrow in self.gizmo_arrows.values():
                arrow.hide()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    from QPanda3D.Panda3DWorld import Panda3DWorld
    dummy_world = Panda3DWorld(1024, 768)
    editor_tab = SequenceEditorTab(dummy_world)
    editor_tab.setWindowTitle("QPanda3D Sequence Editor Tab with Gizmos")
    editor_tab.resize(1200, 800)
    editor_tab.show()
    sys.exit(app.exec_())
