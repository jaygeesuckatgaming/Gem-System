import cv2

def list_available_cameras_v2():
    """
    Probes for connected video devices using OpenCV's default backend.
    
    This version REMOVES the `cv2.CAP_DSHOW` flag, which can prevent the script
    from hanging if there are issues with the DirectShow drivers on Windows.
    """
    
    print("Searching for available cameras (v2 - Default Backend)...")
    
    index = 0
    found_cameras = []
    
    # Try up to 10 indices
    while index < 10:
        # Using the default backend which is more stable
        cap = cv2.VideoCapture(index)

        if cap.isOpened():
            print(f"  - Found a device at Index {index}. Releasing it.")
            # We must release the camera immediately after finding it.
            cap.release()
            found_cameras.append(index)
        
        index += 1

    print("-" * 30)
    if not found_cameras:
        print("No cameras were found. Please check:")
        print("  1. Is OBS Virtual Camera *running*?")
        print("  2. Do you have camera permissions enabled in Windows Settings?")
    else:
        print("Summary: The following camera indices are available for use:")
        for idx in found_cameras:
            print(f"  -> Index {idx}")
    print("-" * 30)
    
if __name__ == "__main__":
    list_available_cameras_v2()