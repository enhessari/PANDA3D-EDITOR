#!/usr/bin/env python3
from direct.showbase.ShowBase import ShowBase
from direct.actor.Actor import Actor
from direct.gui.DirectGui import (
    DirectFrame, DirectButton, DirectSlider, DirectLabel,
    DirectOptionMenu, DirectEntry
)
from direct.interval.IntervalGlobal import (
    Sequence, Parallel, LerpPosInterval, LerpHprInterval, LerpScaleInterval
)
from panda3d.core import TextNode
import sys

# List of UI module names for later replacement/integration with PyQt.
UI_MODULES = [
    "TimelineUI",         # Handles the timeline display and scrubbing.
    "TrackUI",            # Manages the display of multiple tracks (actors, cameras, etc).
    "KeyframeUI",         # Provides keyframe editing and dragging.
    "PlaybackControlUI",  # Contains play/pause/rewind/fast-forward controls.
    "JointSelectorUI"     # Joint selection and details viewing.
]

def lerp_tuple(start_tuple, end_tuple, t):
    """Linearly interpolates between two tuples."""
    return tuple(s * (1 - t) + e * t for s, e in zip(start_tuple, end_tuple))

class SequenceEditor(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)
        
        # Disable the default mouse-based camera control.
        self.disableMouse()
        
        # --- Load a rigged Actor for full bone control ---
        # Replace "models/panda-model" with the path to your rigged model.
        self.actor = Actor("models/panda-model")
        self.actor.reparentTo(self.render)
        self.actor.setScale(0.005)
        self.actor.setPos(0, 10, 0)
        self.actor.setHpr(0, 0, 0)
        
        # --- Create controlled joints dictionary ---
        # This will allow manual control over each bone.
        self.controlled_joints = {}
        for joint in self.actor.getJoints():
            joint_name = joint.getName()
            controlled = self.actor.controlJoint(None, 'modelRoot', joint_name)
            self.controlled_joints[joint_name] = controlled
        
        # For joint selection UI.
        self.selected_joint = None
        
        # --- Sequence Data ---
        # Each keyframe stores the actor's global transform and each bone's transform.
        self.keyframes = []
        self.timeline_duration = 15.0
        self.sequence = None
        
        self.create_ui()
        
        # Add a task to update joint details continuously (e.g., during timeline scrubbing).
        self.taskMgr.add(self.update_joint_task, "UpdateJointTask")
        
    def create_ui(self):
        # Main UI frame.
        self.ui_frame = DirectFrame(
            frameColor=(0, 0, 0, 0.5),
            frameSize=(-1, 1, -0.8, 0.8),
            pos=(0, 0, 0)
        )
        
        # ---- Timeline Slider (for scrubbing) ----
        self.timeline_slider = DirectSlider(
            parent=self.ui_frame,
            range=(0, self.timeline_duration),
            value=0,
            pos=(-0.8, 0, -0.7),
            scale=0.5,
            command=self.on_slider_update
        )
        self.slider_label = DirectLabel(
            text="Time: 0.00",
            scale=0.05,
            pos=(-0.1, 0, -0.7),
            parent=self.ui_frame,
            text_align=TextNode.ALeft
        )
        
        # ---- Control Buttons ----
        self.add_keyframe_button = DirectButton(
            text="Add Keyframe",
            scale=0.05,
            pos=(-0.8, 0, 0.7),
            command=self.add_keyframe
        )
        self.remove_keyframe_button = DirectButton(
            text="Remove Last Keyframe",
            scale=0.05,
            pos=(-0.8, 0, 0.6),
            command=self.remove_last_keyframe
        )
        self.play_button = DirectButton(
            text="Play Sequence",
            scale=0.05,
            pos=(-0.8, 0, 0.5),
            command=self.play_sequence
        )
        self.keyframes_label = DirectLabel(
            text=self.get_keyframes_text(),
            scale=0.04,
            pos=(-0.8, 0, 0.3),
            parent=self.ui_frame,
            text_align=TextNode.ALeft
        )
        
        # ---- Joint Selection & Viewing UI ----
        # Dropdown menu to select a joint from the controlled joints.
        joint_names = list(self.controlled_joints.keys())
        self.joint_selector = DirectOptionMenu(
            parent=self.ui_frame,
            text="Select Joint",
            scale=0.05,
            items=joint_names,
            initialitem=0,
            pos=(0.6, 0, 0.7),
            command=self.on_joint_select
        )
        # Automatically select the first joint (if available).
        if joint_names:
            self.selected_joint = joint_names[0]
        
        # Label to display the selected joint's details.
        self.joint_details_label = DirectLabel(
            parent=self.ui_frame,
            text="Joint Details:",
            scale=0.05,
            pos=(0.6, 0, 0.6),
            text_align=TextNode.ALeft
        )
        
        # A visual marker to indicate the selected joint.
        self.joint_marker = self.loader.loadModel("models/misc/sphere")
        self.joint_marker.setScale(0.2)
        self.joint_marker.setColor(1, 0, 0, 1)
        self.joint_marker.reparentTo(self.render)
        self.joint_marker.hide()
        
        # ---- Joint Transform Editing UI ----
        # Label for the editing section.
        self.edit_label = DirectLabel(
            parent=self.ui_frame,
            text="Edit Joint Transform:",
            scale=0.05,
            pos=(0.6, 0, 0.45),
            text_align=TextNode.ALeft
        )
        # Position editing entries.
        self.pos_label = DirectLabel(
            parent=self.ui_frame,
            text="Pos (x, y, z):",
            scale=0.04,
            pos=(0.6, 0, 0.4),
            text_align=TextNode.ALeft
        )
        self.pos_x_entry = DirectEntry(
            parent=self.ui_frame,
            initialText="0.0",
            scale=0.04,
            pos=(0.6, 0, 0.35),
            numLines=1,
            focus=0
        )
        self.pos_y_entry = DirectEntry(
            parent=self.ui_frame,
            initialText="0.0",
            scale=0.04,
            pos=(0.8, 0, 0.35),
            numLines=1,
            focus=0
        )
        self.pos_z_entry = DirectEntry(
            parent=self.ui_frame,
            initialText="0.0",
            scale=0.04,
            pos=(1.0, 0, 0.35),
            numLines=1,
            focus=0
        )
        
        # Rotation editing entries.
        self.rot_label = DirectLabel(
            parent=self.ui_frame,
            text="Rot (h, p, r):",
            scale=0.04,
            pos=(0.6, 0, 0.3),
            text_align=TextNode.ALeft
        )
        self.rot_h_entry = DirectEntry(
            parent=self.ui_frame,
            initialText="0.0",
            scale=0.04,
            pos=(0.6, 0, 0.25),
            numLines=1,
            focus=0
        )
        self.rot_p_entry = DirectEntry(
            parent=self.ui_frame,
            initialText="0.0",
            scale=0.04,
            pos=(0.8, 0, 0.25),
            numLines=1,
            focus=0
        )
        self.rot_r_entry = DirectEntry(
            parent=self.ui_frame,
            initialText="0.0",
            scale=0.04,
            pos=(1.0, 0, 0.25),
            numLines=1,
            focus=0
        )
        
        # Scale editing entries.
        self.scale_label = DirectLabel(
            parent=self.ui_frame,
            text="Scale (x, y, z):",
            scale=0.04,
            pos=(0.6, 0, 0.2),
            text_align=TextNode.ALeft
        )
        self.scale_x_entry = DirectEntry(
            parent=self.ui_frame,
            initialText="1.0",
            scale=0.04,
            pos=(0.6, 0, 0.15),
            numLines=1,
            focus=0
        )
        self.scale_y_entry = DirectEntry(
            parent=self.ui_frame,
            initialText="1.0",
            scale=0.04,
            pos=(0.8, 0, 0.15),
            numLines=1,
            focus=0
        )
        self.scale_z_entry = DirectEntry(
            parent=self.ui_frame,
            initialText="1.0",
            scale=0.04,
            pos=(1.0, 0, 0.15),
            numLines=1,
            focus=0
        )
        
        # Button to apply the edited transform to the selected joint.
        self.apply_transform_button = DirectButton(
            parent=self.ui_frame,
            text="Apply Transform",
            scale=0.05,
            pos=(0.6, 0, 0.05),
            command=self.apply_transform
        )
    
    def on_slider_update(self):
        """Called when the timeline slider is moved."""
        current_time = self.timeline_slider['value']
        self.slider_label['text'] = f"Time: {current_time:.2f}"
        self.preview_at_time(current_time)
    
    def on_joint_select(self, joint_name):
        """Called when a joint is selected from the dropdown."""
        self.selected_joint = joint_name
        # Attach the marker to the selected joint to highlight it.
        joint_np = self.controlled_joints[joint_name]
        self.joint_marker.reparentTo(joint_np)
        self.joint_marker.setPos(0, 0, 0)  # Position marker at the joint's origin.
        self.joint_marker.show()
        self.update_joint_details()
        self.update_transform_entries()  # Update the edit fields with current transform.
    
    def update_joint_details(self):
        """Updates the joint details label with the current transform of the selected joint."""
        if self.selected_joint:
            joint_np = self.controlled_joints[self.selected_joint]
            pos = joint_np.getPos()
            hpr = joint_np.getHpr()
            scale = joint_np.getScale()
            details = (f"Joint: {self.selected_joint}\n"
                       f"Pos: ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})\n"
                       f"Hpr: ({hpr[0]:.2f}, {hpr[1]:.2f}, {hpr[2]:.2f})\n"
                       f"Scale: ({scale[0]:.2f}, {scale[1]:.2f}, {scale[2]:.2f})")
            self.joint_details_label['text'] = details
    
    def update_transform_entries(self):
        """Populates the transform editing fields with the current transform of the selected joint."""
        if self.selected_joint:
            joint_np = self.controlled_joints[self.selected_joint]
            pos = joint_np.getPos()
            hpr = joint_np.getHpr()
            scale = joint_np.getScale()
            self.pos_x_entry.enterText(f"{pos[0]:.2f}")
            self.pos_y_entry.enterText(f"{pos[1]:.2f}")
            self.pos_z_entry.enterText(f"{pos[2]:.2f}")
            self.rot_h_entry.enterText(f"{hpr[0]:.2f}")
            self.rot_p_entry.enterText(f"{hpr[1]:.2f}")
            self.rot_r_entry.enterText(f"{hpr[2]:.2f}")
            self.scale_x_entry.enterText(f"{scale[0]:.2f}")
            self.scale_y_entry.enterText(f"{scale[1]:.2f}")
            self.scale_z_entry.enterText(f"{scale[2]:.2f}")
    
    def apply_transform(self):
        """Reads values from the editing fields and applies them to the selected joint."""
        if self.selected_joint:
            try:
                new_pos = (
                    float(self.pos_x_entry.get()),
                    float(self.pos_y_entry.get()),
                    float(self.pos_z_entry.get())
                )
                new_hpr = (
                    float(self.rot_h_entry.get()),
                    float(self.rot_p_entry.get()),
                    float(self.rot_r_entry.get())
                )
                new_scale = (
                    float(self.scale_x_entry.get()),
                    float(self.scale_y_entry.get()),
                    float(self.scale_z_entry.get())
                )
                joint_np = self.controlled_joints[self.selected_joint]
                joint_np.setPos(new_pos)
                joint_np.setHpr(new_hpr)
                joint_np.setScale(new_scale)
                print(f"Applied new transform to {self.selected_joint}: pos={new_pos}, hpr={new_hpr}, scale={new_scale}")
                self.update_joint_details()
            except ValueError:
                print("Invalid transform values. Please enter numeric values.")
    
    def update_joint_task(self, task):
        """Task that continuously updates the selected joint details."""
        if self.selected_joint:
            self.update_joint_details()
        return task.cont
    
    def add_keyframe(self):
        """
        Adds a keyframe at the current slider time. Captures:
          - Actor's global transform.
          - Each controlled joint's (bone's) transform.
        """
        current_time = self.timeline_slider['value']
        keyframe = {
            "time": current_time,
            "pos": tuple(self.actor.getPos()),
            "hpr": tuple(self.actor.getHpr()),
            "scale": tuple(self.actor.getScale()),
            "bones": {}
        }
        for bone_name, joint in self.controlled_joints.items():
            keyframe["bones"][bone_name] = {
                "pos": tuple(joint.getPos()),
                "hpr": tuple(joint.getHpr()),
                "scale": tuple(joint.getScale())
            }
        self.keyframes.append(keyframe)
        self.keyframes.sort(key=lambda k: k["time"])
        self.update_keyframes_display()
        print(f"Added keyframe at t={current_time:.2f}")
    
    def remove_last_keyframe(self):
        """Removes the last keyframe, if any."""
        if self.keyframes:
            removed = self.keyframes.pop()
            self.update_keyframes_display()
            print(f"Removed keyframe at t={removed['time']:.2f}")
        else:
            print("No keyframes to remove.")
    
    def update_keyframes_display(self):
        """Updates the keyframes display label."""
        self.keyframes_label['text'] = self.get_keyframes_text()
    
    def get_keyframes_text(self):
        """Returns a string listing all keyframes (global transform and controlled bone keys)."""
        if not self.keyframes:
            return "No keyframes."
        text = "Keyframes:\n"
        for kf in self.keyframes:
            bones_list = list(kf["bones"].keys())
            text += (f"t: {kf['time']:.2f} | pos: ({kf['pos'][0]:.2f}, {kf['pos'][1]:.2f}, {kf['pos'][2]:.2f})"
                     f" | hpr: ({kf['hpr'][0]:.2f}, {kf['hpr'][1]:.2f}, {kf['hpr'][2]:.2f})"
                     f" | scale: ({kf['scale'][0]:.2f}, {kf['scale'][1]:.2f}, {kf['scale'][2]:.2f})"
                     f" | bones: {bones_list}\n")
        return text
    
    def play_sequence(self):
        """
        Builds and plays a Panda3D Sequence from keyframes.
        For each segment between keyframes, a Parallel interval is created that interpolates
        both the actor's global transform and every controlled bone's transform.
        """
        if not self.keyframes:
            print("No keyframes to play.")
            return
        
        if self.sequence:
            self.sequence.finish()
        
        intervals = []
        self.keyframes.sort(key=lambda k: k["time"])
        
        # Helper function to create a hold interval for a keyframe.
        def create_hold_interval(kf, duration):
            global_hold = Parallel(
                LerpPosInterval(self.actor, duration, kf["pos"]),
                LerpHprInterval(self.actor, duration, kf["hpr"]),
                LerpScaleInterval(self.actor, duration, kf["scale"])
            )
            bone_intervals = []
            for bone_name, bone_tf in kf["bones"].items():
                joint = self.controlled_joints[bone_name]
                bone_interval = Parallel(
                    LerpPosInterval(joint, duration, bone_tf["pos"]),
                    LerpHprInterval(joint, duration, bone_tf["hpr"]),
                    LerpScaleInterval(joint, duration, bone_tf["scale"])
                )
                bone_intervals.append(bone_interval)
            return Parallel(global_hold, *bone_intervals)
        
        # If the first keyframe isn’t at time 0, hold its transform.
        if self.keyframes[0]["time"] > 0:
            duration = self.keyframes[0]["time"]
            intervals.append(create_hold_interval(self.keyframes[0], duration))
        
        # Create intervals between consecutive keyframes.
        for i in range(len(self.keyframes) - 1):
            start_kf = self.keyframes[i]
            end_kf = self.keyframes[i+1]
            duration = end_kf["time"] - start_kf["time"]
            
            global_interval = Parallel(
                LerpPosInterval(self.actor, duration, end_kf["pos"], startPos=start_kf["pos"]),
                LerpHprInterval(self.actor, duration, end_kf["hpr"], startHpr=start_kf["hpr"]),
                LerpScaleInterval(self.actor, duration, end_kf["scale"], startScale=start_kf["scale"])
            )
            bone_intervals = []
            for bone_name, start_bone in start_kf["bones"].items():
                end_bone = end_kf["bones"].get(bone_name)
                if end_bone is not None:
                    joint = self.controlled_joints[bone_name]
                    bone_interval = Parallel(
                        LerpPosInterval(joint, duration, end_bone["pos"], startPos=start_bone["pos"]),
                        LerpHprInterval(joint, duration, end_bone["hpr"], startHpr=start_bone["hpr"]),
                        LerpScaleInterval(joint, duration, end_bone["scale"], startScale=start_bone["scale"])
                    )
                    bone_intervals.append(bone_interval)
            segment_interval = Parallel(global_interval, *bone_intervals)
            intervals.append(segment_interval)
        
        # If the last keyframe is before the end of the timeline, hold its transform.
        if self.keyframes[-1]["time"] < self.timeline_duration:
            duration = self.timeline_duration - self.keyframes[-1]["time"]
            intervals.append(create_hold_interval(self.keyframes[-1], duration))
        
        self.sequence = Sequence(*intervals)
        print("Playing sequence.")
        self.sequence.start()
    
    def preview_at_time(self, current_time):
        """
        Updates the actor's and all bones' transforms based on linear interpolation
        between keyframes. This provides a live preview as the user scrubs the timeline.
        """
        if not self.keyframes:
            return
        
        if current_time <= self.keyframes[0]["time"]:
            kf = self.keyframes[0]
            self.actor.setPos(kf["pos"])
            self.actor.setHpr(kf["hpr"])
            self.actor.setScale(kf["scale"])
            for bone_name, bone_tf in kf["bones"].items():
                self.controlled_joints[bone_name].setPos(bone_tf["pos"])
                self.controlled_joints[bone_name].setHpr(bone_tf["hpr"])
                self.controlled_joints[bone_name].setScale(bone_tf["scale"])
            return
        
        if current_time >= self.keyframes[-1]["time"]:
            kf = self.keyframes[-1]
            self.actor.setPos(kf["pos"])
            self.actor.setHpr(kf["hpr"])
            self.actor.setScale(kf["scale"])
            for bone_name, bone_tf in kf["bones"].items():
                self.controlled_joints[bone_name].setPos(bone_tf["pos"])
                self.controlled_joints[bone_name].setHpr(bone_tf["hpr"])
                self.controlled_joints[bone_name].setScale(bone_tf["scale"])
            return
        
        for i in range(len(self.keyframes) - 1):
            start_kf = self.keyframes[i]
            end_kf = self.keyframes[i+1]
            if start_kf["time"] <= current_time <= end_kf["time"]:
                t = (current_time - start_kf["time"]) / (end_kf["time"] - start_kf["time"])
                new_pos = lerp_tuple(start_kf["pos"], end_kf["pos"], t)
                new_hpr = lerp_tuple(start_kf["hpr"], end_kf["hpr"], t)
                new_scale = lerp_tuple(start_kf["scale"], end_kf["scale"], t)
                self.actor.setPos(new_pos)
                self.actor.setHpr(new_hpr)
                self.actor.setScale(new_scale)
                for bone_name in start_kf["bones"]:
                    start_bone = start_kf["bones"][bone_name]
                    end_bone = end_kf["bones"].get(bone_name)
                    if end_bone is not None:
                        bone_pos = lerp_tuple(start_bone["pos"], end_bone["pos"], t)
                        bone_hpr = lerp_tuple(start_bone["hpr"], end_bone["hpr"], t)
                        bone_scale = lerp_tuple(start_bone["scale"], end_bone["scale"], t)
                        self.controlled_joints[bone_name].setPos(bone_pos)
                        self.controlled_joints[bone_name].setHpr(bone_hpr)
                        self.controlled_joints[bone_name].setScale(bone_scale)
                break

if __name__ == "__main__":
    app = SequenceEditor()
    app.run()
