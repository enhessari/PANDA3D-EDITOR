from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    CollisionTraverser, CollisionNode, CollisionRay, CollisionHandlerQueue,
    BitMask32, CollisionSphere, Point3, Vec3
)
from direct.task import Task
import math

from direct.showbase.DirectObject import DirectObject
from QPanda3D.Panda3DWorld import Panda3DWorld

class GizmoDemo(DirectObject):
    def __init__(self, world: Panda3DWorld):
        super().__init__()
        
        # Disable default camera controls.
        world.disableMouse()
        world.camera.setPos(10, -20, 10)
        world.camera.lookAt(0, 0, 0)
        
        # Create a parent node for the gizmo.
        self.gizmo_root = render.attachNewNode("GizmoRoot")
        self.gizmo_root.setPos(0, 0, 0)
        
        # Load the gizmo model and attach three arrows.
        # We assume the model (gizmos.obj) is oriented along +Y by default.
        #
        # X-axis arrow (red): rotate to point along +X.
        self.gizmo_x = loader.loadModel("models/gizmos.obj")
        self.gizmo_x.reparentTo(self.gizmo_root)
        self.gizmo_x.setColor(1, 0, 0, 1)
        self.gizmo_x.setHpr(90, 0, 0)  # +Y -> +X
        
        # Y-axis arrow (green): default orientation (points along +Y).
        self.gizmo_y = loader.loadModel("models/gizmos.obj")
        self.gizmo_y.reparentTo(self.gizmo_root)
        self.gizmo_y.setColor(0, 1, 0, 1)
        
        # Z-axis arrow (blue): rotate so it points along +Z.
        # (Changing pitch from -90 to +90 flips it so it points upward.)
        self.gizmo_z = loader.loadModel("models/gizmos.obj")
        self.gizmo_z.reparentTo(self.gizmo_root)
        self.gizmo_z.setColor(0, 0, 1, 1)
        self.gizmo_z.setHpr(0, 90, 0)
        
        # Keep a dictionary for convenience.
        self.gizmos = {
            "x": self.gizmo_x,
            "y": self.gizmo_y,
            "z": self.gizmo_z
        }
        
        # --- Collision Setup for Picking ---
        # Attach a collision sphere to each arrow.
        self.pickerMask = BitMask32.bit(1)
        for axis, arrow in self.gizmos.items():
            # Compute tight bounds and create a collision sphere.
            min_bound, max_bound = arrow.getTightBounds()
            center = (min_bound + max_bound) * 0.5
            radius = (max_bound - min_bound).length() * 0.5
            cs = CollisionSphere(center, radius)
            
            cnode = CollisionNode('gizmo_' + axis)
            cnode.addSolid(cs)
            cnode.setIntoCollideMask(self.pickerMask)
            arrow.attachNewNode(cnode)
        
        # --- Picking Ray Setup ---
        self.picker = CollisionTraverser()
        self.pq = CollisionHandlerQueue()
        self.pickerNode = CollisionNode('mouseRay')
        self.pickerNode.setFromCollideMask(self.pickerMask)
        self.pickerNP = camera.attachNewNode(self.pickerNode)
        self.pickerRay = CollisionRay()
        self.pickerNode.addSolid(self.pickerRay)
        self.picker.addCollider(self.pickerNP, self.pq)
        
        # --- Dragging State Variables ---
        self.dragAxis = None           # Vec3: the axis along which movement is constrained
        self.initialGizmoPos = None    # Point3: gizmo_root's position at mouse down
        self.initialDragParam = None   # float: parameter along the drag line at mouse down
        
        # Accept mouse events.
        world.accept("mouse1", self.onMouseDown)
        world.accept("mouse1-up", self.onMouseUp)
        world.taskMgr.add(self.mouseTask, "mouseTask")
        
        # (Optional) Load an environment for reference.
        self.scene = loader.loadModel("models/environment")
        self.scene.reparentTo(render)
        self.scene.setScale(0.25)
        self.scene.setPos(-8, 42, 0)
        
        # --- Free-Fly Camera Setup ---
        self.camera_speed = 5.0
        self.mouse_sensitivity = 0.1
        self.keys = {
            "w": False,
            "s": False,
            "a": False,
            "d": False,
            "shift": False,
            "space": False
        }
        
        # Bind keys.
        self.accept("w", self.set_key, ["w", True])
        self.accept("w-up", self.set_key, ["w", False])
        self.accept("s", self.set_key, ["s", True])
        self.accept("s-up", self.set_key, ["s", False])
        self.accept("a", self.set_key, ["a", True])
        self.accept("a-up", self.set_key, ["a", False])
        self.accept("d", self.set_key, ["d", True])
        self.accept("d-up", self.set_key, ["d", False])
        self.accept("shift", self.set_key, ["shift", True])
        self.accept("shift-up", self.set_key, ["shift", False])
        self.accept("space", self.set_key, ["space", True])
        self.accept("space-up", self.set_key, ["space", False])
        
        # Add the camera update task.
        world.taskMgr.add(self.update_camera, "update_camera")
        
        # Center the mouse.
        if hasattr(world.win, "movePointer"):
            world.win.movePointer(0, int(world.win.getXSize() / 2), int(world.win.getYSize() / 2))
        else:
            print("Warning: movePointer not available on world.win")
    
    def set_key(self, key, value):
        self.keys[key] = value
    
    def update_camera(self, task):
        dt = globalClock.getDt()
        move_speed = self.camera_speed * dt
        
        # Calculate movement direction based on camera orientation.
        move_dir = Vec3(0, 0, 0)
        if self.keys["w"]:
            move_dir.y += 1  # Move forward.
        if self.keys["s"]:
            move_dir.y -= 1  # Move backward.
        if self.keys["a"]:
            move_dir.x -= 1  # Move left.
        if self.keys["d"]:
            move_dir.x += 1  # Move right.
        if self.keys["shift"]:
            move_dir.z -= 1  # Move down.
        if self.keys["space"]:
            move_dir.z += 1  # Move up.
        
        # Normalize the movement vector to prevent faster diagonal movement.
        if move_dir.length() > 0:
            move_dir.normalize()
        
        # Move the camera.
        self.camera.setPos(self.camera.getPos() + move_dir * move_speed)
        
        # Handle mouse look.
        if self.mouseWatcherNode.hasMouse():
            md = self.win.getPointer(0)
            x = md.getX()
            y = md.getY()
            
            # Calculate mouse movement delta.
            dx = (x - self.win.getXSize() / 2) * self.mouse_sensitivity
            dy = (y - self.win.getYSize() / 2) * self.mouse_sensitivity
            
            # Rotate the camera.
            self.camera.setH(self.camera.getH() - dx)
            self.camera.setP(self.camera.getP() - dy)
            
            # Center the mouse.
            self.win.movePointer(0, int(self.win.getXSize() / 2), int(self.win.getYSize() / 2))
        
        return Task.cont
    
    def computeDragParameter(self, r0, rdir, linePoint, lineDir):
        """
        Given a ray (r0, rdir) and a line defined by (linePoint, lineDir),
        compute the parameter t on the line such that the point (linePoint + t*lineDir)
        is the closest point to the ray.
        
        Returns t.
        """
        # Ensure the drag axis is normalized.
        d = lineDir.normalized()
        # rdir is assumed normalized.
        # Let w0 = linePoint - r0.
        w0 = linePoint - r0
        B = d.dot(rdir)
        # Denom: 1 - (d dot rdir)^2.
        denom = 1 - B * B
        # To avoid division by zero, check denominator.
        if math.fabs(denom) < 1e-5:
            return 0.0
        t = (-d.dot(w0) + B * rdir.dot(w0)) / denom
        return t
    
    def onMouseDown(self):
        """Handle left mouse button press: determine which arrow is clicked
        and initialize the drag state."""
        if not self.mouseWatcherNode.hasMouse():
            return
        
        mpos = self.mouseWatcherNode.getMouse()
        self.pickerRay.setFromLens(self.camNode, mpos.getX(), mpos.getY())
        self.picker.traverse(self.gizmo_root)
        
        if self.pq.getNumEntries() > 0:
            self.pq.sortEntries()
            entry = self.pq.getEntry(0)
            nodeName = entry.getIntoNode().getName()  # Expected "gizmo_x", "gizmo_y", or "gizmo_z"
            if nodeName.startswith("gizmo_"):
                axis = nodeName.split("_")[-1]
                if axis == "x":
                    self.dragAxis = Vec3(1, 0, 0)
                elif axis == "y":
                    self.dragAxis = Vec3(0, 1, 0)
                elif axis == "z":
                    self.dragAxis = Vec3(0, 0, 1)
                else:
                    self.dragAxis = None
                
                if self.dragAxis is not None:
                    # Record the object's initial position.
                    self.initialGizmoPos = self.gizmo_root.getPos(render)
                    
                    # Define the drag line: passes through the initial position and
                    # extends along the selected axis.
                    linePoint = self.initialGizmoPos
                    lineDir = self.dragAxis  # Already unit length
                    
                    # Get the mouse ray (we use the near point as the ray origin).
                    nearPoint = Point3()
                    farPoint = Point3()
                    self.camLens.extrude(mpos, nearPoint, farPoint)
                    r0 = render.getRelativePoint(self.camera, nearPoint)
                    rFar = render.getRelativePoint(self.camera, farPoint)
                    rdir = (rFar - r0).normalized()
                    
                    # Compute the parameter along the drag line.
                    self.initialDragParam = self.computeDragParameter(r0, rdir, linePoint, lineDir)
                    # Debug print.
                    print("Dragging axis:", axis, "initial param =", self.initialDragParam)
    
    def onMouseUp(self):
        """Reset the dragging state."""
        self.dragAxis = None
        self.initialGizmoPos = None
        self.initialDragParam = None
    
    def mouseTask(self, task):
        """If dragging is active, update the gizmo's position constrained along the selected axis."""
        if self.dragAxis is not None and self.initialDragParam is not None and self.mouseWatcherNode.hasMouse():
            mpos = self.mouseWatcherNode.getMouse()
            
            # Recompute the current mouse ray.
            nearPoint = Point3()
            farPoint = Point3()
            self.camLens.extrude(mpos, nearPoint, farPoint)
            r0 = render.getRelativePoint(self.camera, nearPoint)
            rFar = render.getRelativePoint(self.camera, farPoint)
            rdir = (rFar - r0).normalized()
            
            # The drag line is defined by the object's initial position and the drag axis.
            linePoint = self.initialGizmoPos
            lineDir = self.dragAxis
            
            # Compute the current parameter along the drag line.
            currentParam = self.computeDragParameter(r0, rdir, linePoint, lineDir)
            deltaParam = currentParam - self.initialDragParam
            
            # New position is offset along the drag axis.
            newPos = self.initialGizmoPos + self.dragAxis * deltaParam
            self.gizmo_root.setPos(render, newPos)
        return Task.cont

if __name__ == "__main__":
    # Run the demo.
    demo = GizmoDemo()
    demo.run()
