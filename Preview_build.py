import os

import sys

import toml
from direct.showbase.ShowBase import ShowBase
from Entity import load_all_entities_from_folder
from input_manager import InputManager, NetworkManager  # Import InputManager & NetworkManager

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor

class GamePreviewApp(ShowBase):
    def __init__(self, network_manager=None):
        super().__init__()
        self.disableMouse()
        if network_manager is None:
            from input_manager import NetworkManager
            network_manager = NetworkManager()  # or however you want to create a default instance
        
        # Initialize systems
        self.network_manager = network_manager
        self.network_manager.connect_to_server()  # Connect to existing server
        
        # Initialize the input manager here
        from input_manager import InputManager
        self.input_manager = InputManager(network_manager)  # Pass network_manager if needed

        # Load game content
        self.load_game_assets()
        
    def load_game_assets(self):
        """Load game content without editor references"""
        data_folder = "saves"
        self.entities = load_all_entities_from_folder(
            data_folder, 
            self.render,      # Use THIS ShowBase's render
            self.network_manager,
            self.input_manager
        )
        

    def setup_camera(self):
        self.camera.setPos(0, -50, 20)
        self.camera.lookAt(0, 0, 0)

    def setup_networking(self):
        """Determines if networking should be enabled in preview mode."""
        try:
            with open("input_config.toml", "r") as f:
                config = toml.load(f)
                networking_enabled = any(cat in ["udp", "tcp"] for cat in config.get("input_categories", {}).values())
        except FileNotFoundError:
            networking_enabled = False  # Default to local-only

        return NetworkManager() if networking_enabled else None
    

    def update(self, task):
        """Live updates input settings dynamically during preview mode."""
        self.input_manager.update()
        return task.cont

    def recreate_entities(self):
        """Reload all entities when required (e.g., if settings change)."""
        for entity in self.entities:
            entity.node.removeNode()
        self.entities.clear()
        self.entities = load_all_entities_from_folder("saves", self.render, self.network_manager, self.input_manager)
        
    

if __name__ == "__main__":
    if "--server" in sys.argv:
        print("Starting dedicated server...")
        from input_manager import NetworkManager
        
        network_manager = NetworkManager()
        network_manager.connect_to_server()
        
        # Run server without rendering the game
        while True:
            reactor.run(installSignalHandlers=False)
    elif "--client" in sys.argv:
        server_ip = "127.0.0.1"
        if "--connect" in sys.argv:
            idx = sys.argv.index("--connect") + 1
            if idx < len(sys.argv):
                server_ip = sys.argv[idx]
        from input_manager import NetworkManager
        network_manager = NetworkManager(server_address=(server_ip, 9000), is_client=True)
        app = GamePreviewApp(network_manager=network_manager)
        app.run()
    else:
        from input_manager import NetworkManager
        network_manager = NetworkManager()  # Create a default NetworkManager instance
        app = GamePreviewApp(network_manager=network_manager)
        app.run()
