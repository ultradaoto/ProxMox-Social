import sys
import os

# Ensure src directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from vision_controller import VisionController

def main():
    print("--- Testing Vision Controller ---")
    
    try:
        vc = VisionController()
        
        # 1. Test Capture
        print("\n1. Testing Screen Capture...")
        img = vc.capture_screen("vision_test_capture.png")
        print(f"   Capture success. Shape: {img.shape}")
        
        # 2. Test Analysis
        print("\n2. Testing AI Analysis...")
        prompt = "What application is currently visible? Is there a browser open? Be concise."
        print(f"   Prompt: {prompt}")
        result = vc.analyze_screen(prompt, image_array=img)
        print(f"   Response: {result}")
        
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
