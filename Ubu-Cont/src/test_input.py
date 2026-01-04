import sys
import os
import time

# Ensure src directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Need to make sure dependencies are found for virtual_mouse_controller -> human_mouse
# human_mouse is in src/input. We need src/input in sys.path BEFORE importing input_controller
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'input'))

from input_controller import InputController

def main():
    print("--- Testing Input Controller ---")
    
    try:
        ic = InputController()
        print("Connecting to input devices...")
        ic.connect()
        
        if not ic.mouse.connected:
            print("WARNING: Mouse not connected! (Is the server running on 192.168.100.1?)")
        else:
            print("Mouse connected.")
            
        if not ic.keyboard.connected:
            print("WARNING: Keyboard not connected! (Is the server running on 192.168.100.1?)")
        else:
            print("Keyboard connected.")
            
        # Test Move
        print("Moving to 100, 100...")
        ic.move_to(100, 100)
        time.sleep(1)
        
        print("Moving to 500, 500...")
        ic.move_to(500, 500)
        time.sleep(1)
        
        # Test Click
        # print("Clicking (right click to avoid accidental interaction)...")
        # ic.click('right')
        
        print("Test Complete.")
        
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
