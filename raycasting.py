from panda3d.core import (
    CollisionTraverser, CollisionHandlerQueue, CollisionRay, CollisionNode,
    BitMask32, GeomNode, Point3
)
from direct.showbase.DirectObject import DirectObject
from QPanda3D.Panda3DWorld import Panda3DWorld
class Picker(DirectObject):
    def __init__(self, world: Panda3DWorld):
        self.base = world
        
        # Set up the collision traverser and handler.
        self.traverser = CollisionTraverser()
        self.traverser.showCollisions(base.render)  # Visualize collisions for debugging.
        self.handler = CollisionHandlerQueue()
        
        # Create a collision node for the picker ray.
        self.picker_ray = CollisionRay()
        self.picker_node = CollisionNode('mouse_ray')
        # Disable its into mask so it doesn't register collisions with itself.
        self.picker_node.set_from_collide_mask(BitMask32.bit(10))
        self.picker_node.set_into_collide_mask(BitMask32.bit(10))
        pickerNP = base.camera.attachNewNode(self.picker_node)
        
        self.traverser.addCollider(pickerNP, self.handler)
        # Attach the picker node to the camera.
        #self.picker_node.set_from_collide_mask(combined_mask)
        
        self.picker_node.addSolid(self.picker_ray)
        # Define collision masks for different categories.
        self.gizmo_mask  = BitMask32.bit(10)
        self.terrain_mask = BitMask32.bit(2)
        self.object_mask = BitMask32.bit(3)
        self.ui_mask = BitMask32.bit(4)
        combined_mask = self.gizmo_mask | self.terrain_mask | self.object_mask | self.ui_mask
        
        # Set the from collide mask on the picker.
        
        # Create and add the collision ray.
        
        # Add the picker node to the traverser.
        
        # Accept the mouse click event.
        self.base.accept("mouse1", self.on_mouse_click)
        self.base.accept("mouse1-up", self.stop_drag)
    
    def stop_drag(self, position):
        self.base.taskMgr.remove("drag_gizmo_task")
        
        
    def set_gizmos(self, gizmos_np):
        # This function shows how you could obtain all collision nodes from a container.
        # In your case, gizmos_np should be a NodePath containing all gizmo collision objects.
        collider_nodes = gizmos_np.findAllMatches("**/+CollisionNode")
        count = collider_nodes.getNumPaths()
        print("Number of gizmo colliders added:", count)
    
    def on_mouse_click(self, position):
        # Ensure mouse is within bounds
        if not base.mouseWatcherNode.hasMouse():
            print("Mouse not detected.")
            return
    
        # Get normalized mouse position
        pMouse = base.mouseWatcherNode.getMouse()
    
        # Debug: Check mouse position
        print(f"Normalized Mouse Position: {pMouse}")
    
        # Get near and far points in camera space
        pFrom = Point3()
        pTo = Point3()
        base.camLens.extrude(pMouse, pFrom, pTo)
    
        # Convert to world space
        pFrom = render.getRelativePoint(base.cam, pFrom)
        pTo = render.getRelativePoint(base.cam, pTo)
    
        # Debug: Check world space points
        print(f"World Space Ray Start: {pFrom}, End: {pTo}")
    
        # Update the ray's origin and direction
        self.picker_ray.set_origin(pFrom)
        self.picker_ray.set_direction((pTo - pFrom).normalized())  # Normalize direction
    
        
        # Traverse the scene graph (or your collision root node if you have one).
        self.handler.clear_entries()
        self.traverser.traverse(render)
        
        # Process the collision entries.
        if self.handler.getNumEntries() > 0:
            print("Click detected!")
            self.handler.sortEntries()
            entries = self.handler.getEntries()
            
            # Filter entries based on collision masks.
            gizmo_entries = [e for e in entries if e.getIntoNodePath().getCollideMask() & self.gizmo_mask]
            if gizmo_entries:
                gizmo_entry = gizmo_entries[0]
                print("Clicked on gizmos")
                self.base.animator_tab.start_gizmo_drag(gizmo_entry)
                return
            
            terrain_entries = [e for e in entries if e.getIntoNodePath().getCollideMask() & self.terrain_mask]
            if terrain_entries:
                terrain_entry = terrain_entries[0]
                print("Clicked on terrain")
                # Handle terrain collision...
                return
            
            object_entries = [e for e in entries if e.getIntoNodePath().getCollideMask() & self.object_mask]
            if object_entries:
                object_entry = object_entries[0]
                print("Clicked on object")
                # Handle object selection...
                return
            
            ui_entries = [e for e in entries if e.getIntoNodePath().getCollideMask() & self.ui_mask]
            if ui_entries:
                ui_entry = ui_entries[0]
                print("Clicked on UI element")
                # Handle UI selection...
                return
        else:
            print("No collision detected.")
            
# To use this in your application:
if __name__ == "__main__":
    from direct.showbase.ShowBase import ShowBase

    class MyApp(ShowBase):
        def __init__(self):
            ShowBase.__init__(self)
            self.picker = Picker(self)
            # In your scene setup, make sure to add your terrain, gizmos, objects, etc.,
            # as children of render (or another common node), and assign them the proper into masks.
            # For example, when creating a gizmo, do:
            #   gizmo_collision_node.setIntoCollideMask(self.picker.gizmo_mask)
            # or for an object:
            #   object_collision_node.setIntoCollideMask(self.picker.object_mask)
            # Also, ensure your animator_tab (if used) is set up accordingly.
    
    app = MyApp()
    app.run()
