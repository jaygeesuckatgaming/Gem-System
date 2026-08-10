import cv2

def identify_cameras_interactive():
    """
    An interactive tool to visually identify cameras.
    
    - Opens a single window.
    - Press 'n' to cycle to the NEXT camera index.
    - Press 'q' to QUIT the program at any time.
    - The current index is displayed on the video feed.
    """
    
    indices_to_test = [8] # The indices you found
    current_index_pos = 0
    
    cap = None
    window_name = "Camera Identification Tool (n = Next, q = Quit)"
    cv2.namedWindow(window_name)

    print("\n=======================================================")
    print("--- INTERACTIVE Camera Identification Tool ---")
    print(f"Testing indices: {indices_to_test}")
    print(" -> Press 'n' to switch to the next camera.")
    print(" -> Press 'q' to quit.")
    print("=======================================================\n")

    while True:
        # --- Release the previous camera if it exists ---
        if cap is not None:
            cap.release()

        # --- Get the next camera index to test ---
        index = indices_to_test[current_index_pos]
        print(f"--- Now testing Index {index} ---")
        
        # --- Try to open the new camera ---
        cap = cv2.VideoCapture(index)
        
        if not cap.isOpened():
            print(f"Could not open camera at Index {index}. Press 'n' to try the next one.")
            # We need to wait for a keypress to move on
            while True:
                key = cv2.waitKey(0) & 0xFF
                if key == ord('n'):
                    current_index_pos = (current_index_pos + 1) % len(indices_to_test)
                    break
                elif key == ord('q'):
                    print("Quitting.")
                    cv2.destroyAllWindows()
                    return
            continue # Go to the top of the main while loop

        # --- Loop to display frames from the CURRENT camera ---
        while True:
            ret, frame = cap.read()
            if not ret:
                print(f"Could not read frame from Index {index}. It may be in use.")
                break # Break from this inner loop to try the next camera

            # --- Add text to the frame to show the current index ---
            font = cv2.FONT_HERSHEY_SIMPLEX
            text = f"Index: {index}"
            cv2.putText(frame, text, (20, 40), font, 1.2, (0, 0, 255), 2, cv2.LINE_AA)
            
            # --- Display the frame ---
            cv2.imshow(window_name, frame)
            
            # --- Wait for user input ---
            key = cv2.waitKey(20) & 0xFF
            
            if key == ord('q'): # Quit the entire script
                print("Quitting.")
                if cap is not None:
                    cap.release()
                cv2.destroyAllWindows()
                return # Exit the function
            
            elif key == ord('n'): # Go to the next camera
                current_index_pos = (current_index_pos + 1) % len(indices_to_test)
                break # Break from the inner loop to load the next camera

    # --- Final cleanup ---
    if cap is not None:
        cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    identify_cameras_interactive()