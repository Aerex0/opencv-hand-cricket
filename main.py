import cv2 as cv
import random
import imageio
import os
import pygame
import tkinter as tk
import numpy as np

# Try to import mediapipe with the new Tasks API
try:
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    MEDIAPIPE_AVAILABLE = True
except ImportError as e:
    print(f"MediaPipe import error: {e}")
    print("Please install/upgrade mediapipe: pip install --upgrade mediapipe")
    MEDIAPIPE_AVAILABLE = False


def load_sounds():
    """Load all game sound effects"""
    try:
        pygame.mixer.init()
    except Exception as e:
        print(f"Error initializing pygame mixer: {e}")
        return {}
    
    sounds = {}
    sound_files = {
        'out': "assets/out.wav",
        'run': "assets/score.wav", 
        'win': "assets/Win.wav",
        'lose': "assets/lose.wav",
        'tie': "assets/tie.wav"
    }
    
    for sound_name, file_path in sound_files.items():
        try:
            if os.path.exists(file_path):
                sounds[sound_name] = pygame.mixer.Sound(file_path)
            else:
                print(f"Warning: {file_path} not found")
                sounds[sound_name] = None
        except Exception as e:
            print(f"Error loading {sound_name} sound: {e}")
            sounds[sound_name] = None
    
    return sounds


def load_gif_frames(gif_path, gif_name):
    """Load and process GIF frames for animations"""
    try:
        if not os.path.exists(gif_path):
            print(f"Warning: {gif_path} not found")
            return []
            
        gif_data = imageio.mimread(gif_path)
        frames = []
        for frame in gif_data:
            if frame.shape[2] == 4:  # Has alpha channel
                frames.append(cv.cvtColor(frame, cv.COLOR_RGBA2BGRA))
            else:  # RGB only
                frames.append(cv.cvtColor(frame, cv.COLOR_RGB2BGR))
        return frames
    except Exception as e:
        print(f"Error loading {gif_name} gif: {e}")
        return []


def load_animations():
    """Load all game animations"""
    animations = {}
    
    gif_files = {
        'victory': "assets/Victory.gif",
        'game_over': "assets/game-over-game.gif"
    }
    
    for anim_name, file_path in gif_files.items():
        animations[anim_name] = load_gif_frames(file_path, anim_name)
    
    return animations


def get_screen_dimensions():
    """Get screen resolution for fullscreen display"""
    try:
        root = tk.Tk()
        root.withdraw()  # Hide the window
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        root.destroy()
        return screen_width, screen_height
    except Exception as e:
        print(f"Error getting screen dimensions: {e}")
        return 1920, 1080  # Default fallback


def download_hand_landmarker_model():
    """Download the hand landmarker model if it doesn't exist"""
    model_path = "hand_landmarker.task"
    
    if os.path.exists(model_path):
        return model_path
    
    print("Downloading hand landmarker model...")
    import urllib.request
    
    model_url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
    
    try:
        urllib.request.urlretrieve(model_url, model_path)
        print(f"Model downloaded successfully to {model_path}")
        return model_path
    except Exception as e:
        print(f"Error downloading model: {e}")
        return None


def get_hand_run(hand_landmarks, handedness):
    """
    Improved finger counting with better thumb detection based on hand orientation
    """
    lm = hand_landmarks
    
    # Determine if it's left or right hand
    is_right_hand = handedness == "Right"

    # Finger tip and pip landmarks
    tip_ids = [4, 8, 12, 16, 20]  # Thumb, Index, Middle, Ring, Pinky
    pip_ids = [3, 6, 10, 14, 18]  # Better joints for comparison
    # mcp_ids = [2, 5, 9, 13, 17]   # Knuckle landmarks

    fingers = []

    # Thumb detection (horizontal check based on hand orientation)
    # thumb_tip = lm[tip_ids[0]]
    # thumb_mcp = lm[mcp_ids[0]]
    
    # Thumb (special case - check x coordinate)
    if (lm[tip_ids[0]].y < lm[pip_ids[0]].y and 
        lm[tip_ids[0]].y < lm[tip_ids[1]].y and 
        lm[tip_ids[0]].y < lm[tip_ids[2]].y and 
        lm[tip_ids[0]].y < lm[tip_ids[3]].y):
        fingers.append(6)
    else:
        fingers.append(0)
    
    # Other fingers (check y coordinate)
    for i in range(1, 5):
        if lm[tip_ids[i]].y < lm[pip_ids[i]].y:
            fingers.append(1)
        else:
            fingers.append(0)
    
    finger_count = sum(fingers)
    
    # Map to 1-6 range (if 0 fingers, return 1)
    return max(1, min(6, finger_count))


def apply_gif_overlay(frame, gif_frame, screen_width, screen_height, alpha=0.7):
    """Apply GIF frame overlay to the main frame with proper blending"""
    gif_frame = cv.resize(gif_frame, (screen_width, screen_height))
    
    # Check if frame has alpha channel
    if gif_frame.shape[2] == 4:
        b, g, r, a = cv.split(gif_frame)
        overlay_rgb = cv.merge((b, g, r))
        alpha_mask = a / 255.0 * alpha  # Apply alpha parameter
        
        # Blend each channel
        for c in range(3):
            frame[:, :, c] = (alpha_mask * overlay_rgb[:, :, c] +
                              (1 - alpha_mask) * frame[:, :, c]).astype(np.uint8)
    else:
        # Simple overlay without alpha blending
        frame = cv.addWeighted(frame, 0.3, gif_frame, alpha, 0)
    
    return frame


def draw_game_ui(frame, clock, gameresult, gametext, player_score, computer_score, 
                round_num, innings, screen_width, screen_height, is_out, target=None):
    """Draw all game UI elements with enhanced visuals"""
    
    # Semi-transparent overlay for better text visibility
    overlay = frame.copy()
    cv.rectangle(overlay, (0, 0), (screen_width, 450), (0, 0, 0), -1)
    frame = cv.addWeighted(overlay, 0.4, frame, 0.6, 0)
    
    # Game title at top center with shadow effect
    title_text = "HAND CRICKET"
    title_font_scale = min(screen_width / 800, screen_height / 600) * 2
    title_size = cv.getTextSize(title_text, cv.FONT_HERSHEY_DUPLEX, int(title_font_scale), 4)[0]
    title_x = (screen_width - title_size[0]) // 2
    # Shadow
    cv.putText(frame, title_text, (title_x + 4, 124), cv.FONT_HERSHEY_DUPLEX, int(title_font_scale), (0, 0, 0), 4)
    # Main text
    cv.putText(frame, title_text, (title_x, 120), cv.FONT_HERSHEY_DUPLEX, int(title_font_scale), (200, 255, 200), 4)
    
    # Game info
    cv.putText(frame, f"Clock: {clock}", (50, 200), cv.FONT_HERSHEY_PLAIN, 3, (255, 255, 255), 3)
    
    # Display target in second innings
    if innings == 2 and target is not None:
        target_text = f"Target: {target + 1}"
        cv.putText(frame, target_text, (50, 250), cv.FONT_HERSHEY_PLAIN, 3, (255, 200, 100), 3)
        cv.putText(frame, gameresult, (50, 300), cv.FONT_HERSHEY_PLAIN, 3, (200, 255, 200), 3)
        cv.putText(frame, gametext, (50, 350), cv.FONT_HERSHEY_PLAIN, 3, (200, 255, 200), 3)
    else:
        cv.putText(frame, gameresult, (50, 250), cv.FONT_HERSHEY_PLAIN, 3, (200, 255, 200), 3)
        cv.putText(frame, gametext, (50, 300), cv.FONT_HERSHEY_PLAIN, 3, (200, 255, 200), 3)
    
    # Score display with better formatting
    score_text = f"You: {player_score} | Computer: {computer_score}"
    score_y = 400 if innings == 2 and target is not None else 350
    cv.putText(frame, score_text, (50, score_y), cv.FONT_HERSHEY_PLAIN, 3, (100, 200, 255), 3)
    
    # Round and Innings text
    round_innings_text = f"Round: {round_num} | Innings: {innings}"
    round_innings_size = cv.getTextSize(round_innings_text, cv.FONT_HERSHEY_PLAIN, 3, 3)[0]
    round_innings_x = screen_width - round_innings_size[0] - 50
    cv.putText(frame, round_innings_text, (round_innings_x, 200), 
               cv.FONT_HERSHEY_PLAIN, 3, (255, 255, 255), 3)

    # Bottom instruction bar with better visibility
    bar_height = int(screen_height * 0.1)
    bar_y = int(screen_height * 0.9)
    
    cv.rectangle(frame, (0, bar_y), (screen_width, screen_height), (50, 50, 50), -1)
    cv.rectangle(frame, (0, bar_y), (screen_width, bar_y + 5), (200, 255, 200), -1)
    
    if innings == 2 and is_out:
        instruction_text = "Press 'N' to Restart Game | Press 'Q' to Quit"
    else:
        instruction_text = "Auto Next Round | Press 'Q' to Quit"
    
    text_size = cv.getTextSize(instruction_text, cv.FONT_HERSHEY_SIMPLEX, 1.5, 3)[0]
    text_x = (screen_width - text_size[0]) // 2
    cv.putText(frame, instruction_text, (text_x, bar_y + 60), 
               cv.FONT_HERSHEY_SIMPLEX, 1.5, (200, 255, 200), 3)
    
    return frame


def play_hand_cricket():
    """Main game function using MediaPipe Tasks API"""
    
    # Check if MediaPipe is available
    if not MEDIAPIPE_AVAILABLE:
        print("\n" + "="*60)
        print("ERROR: MediaPipe is not properly installed!")
        print("="*60)
        print("\nPlease run: pip install --upgrade mediapipe")
        print("="*60 + "\n")
        return
    
    # Download model if needed
    model_path = download_hand_landmarker_model()
    if not model_path:
        print("Failed to load hand landmarker model")
        return
    
    # Load resources
    sounds = load_sounds()
    animations = load_animations()
    screen_width, screen_height = get_screen_dimensions()
    
    # Setup audio channels
    run_channel = None
    event_channel = None
    try:
        run_channel = pygame.mixer.Channel(1)
        event_channel = pygame.mixer.Channel(2)
    except:
        print("Warning: Could not initialize audio channels")
    
    # Video setup
    vid = cv.VideoCapture(0)
    if not vid.isOpened():
        print("Error: Could not open camera")
        return
        
    vid.set(cv.CAP_PROP_FRAME_WIDTH, 1280)
    vid.set(cv.CAP_PROP_FRAME_HEIGHT, 720)

    # Create fullscreen window
    cv.namedWindow('frame', cv.WINDOW_NORMAL)
    cv.setWindowProperty('frame', cv.WND_PROP_FULLSCREEN, cv.WINDOW_FULLSCREEN)
    
    # Game state variables
    clock = 0
    player_move = None
    computer_move = None
    gametext = "Press 'S' to Start the Game!"
    success = True
    gameresult = ""
    player_score = 0
    computer_score = 0
    scored_this_round = False
    is_player_batting = True
    is_out = False
    innings = 1
    round_num = 0
    game_started = False
    celebration_frame_idx = 0
    celebrating_win = False
    celebrating_lose = False
    gif_played_win = False
    gif_played_lose = False
    run_sound_playing = False
    target = None
    game_over = False
    
    # Initialize MediaPipe Hand Landmarker with the new API
    try:
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            num_hands=1,
            min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.6
        )
        hand_landmarker = vision.HandLandmarker.create_from_options(options)
    except Exception as e:
        print(f"Error initializing Hand Landmarker: {e}")
        vid.release()
        return
    
    print("\n✓ Game started successfully!")
    print("✓ Hand detection initialized")
    print("\nControls:")
    print("  Press 'S' to start playing")
    print("  Press 'Q' to quit\n")
    
    try:
        while True:
            ret, frame = vid.read()
            if not ret:
                print("Error: Could not read frame from camera")
                break

            # Flip frame for mirror effect
            frame = cv.flip(frame, 1)
            
            # Create RGB frame for MediaPipe processing
            rgb_frame = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
            
            # Create MediaPipe Image
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            
            # Detect hands
            detection_result = hand_landmarker.detect(mp_image)
            
            # Resize frame to fill screen FIRST before drawing UI
            frame = cv.resize(frame, (screen_width, screen_height))

            # Check for animation triggers
            if "You Won the Game!" in gametext and not celebrating_win and not gif_played_win:
                celebrating_win = True
                celebration_frame_idx = 0
            elif "You Lost the Game!" in gametext and not celebrating_lose and not gif_played_lose:
                celebrating_lose = True
                celebration_frame_idx = 0

            # WINNING CELEBRATION
            if celebrating_win and not gif_played_win and animations.get('victory'):
                if celebration_frame_idx < len(animations['victory']):
                    frame = apply_gif_overlay(frame, animations['victory'][celebration_frame_idx], 
                                            screen_width, screen_height, alpha=0.8)
                    celebration_frame_idx += 1
                else:
                    gif_played_win = True
                    celebrating_win = False

            # LOSING CELEBRATION
            if celebrating_lose and not gif_played_lose and animations.get('game_over'):
                if celebration_frame_idx < len(animations['game_over']):
                    frame = apply_gif_overlay(frame, animations['game_over'][celebration_frame_idx], 
                                            screen_width, screen_height, alpha=0.8)
                    celebration_frame_idx += 1
                else:
                    gif_played_lose = True
                    celebrating_lose = False

            # Game logic
            if clock == 0 and game_started:
                round_num += 1
                scored_this_round = False
                gameresult = ""

            # Sound management
            if game_started and 10 <= clock <= 30 and not run_sound_playing and not game_over:
                if sounds.get('run') and run_channel:
                    run_channel.play(sounds['run'], loops=-1)
                run_sound_playing = True
            elif (clock < 10 or clock > 30 or game_over) and run_sound_playing:
                if run_channel:
                    run_channel.stop()
                run_sound_playing = False

            # Game state logic
            if not game_started:
                gametext = "Press 'S' to Start the Game!"
            elif game_started:
                if 0 <= clock < 5:
                    success = True
                    gametext = "Get Ready..."
                elif 5 <= clock < 15:
                    current_batter = "You" if is_player_batting else "Computer"
                    gametext = f"{current_batter} batting - Show your hand!"
                elif clock == 15:
                    # Check if hands are detected
                    if detection_result.hand_landmarks and len(detection_result.hand_landmarks) > 0:
                        hand_landmarks = detection_result.hand_landmarks[0]
                        handedness = detection_result.handedness[0][0].category_name
                        
                        player_move = get_hand_run(hand_landmarks, handedness)
                        computer_move = random.choice([1, 2, 3, 4, 6])
                    else:
                        success = False
                elif 15 < clock < 25:
                    if success:
                        gameresult = f"You: {player_move}  |  Computer: {computer_move}"

                        if not scored_this_round:
                            if player_move == computer_move:
                                gametext = f"OUT! Both showed {player_move}!"
                                is_out = True
                                game_over = innings == 2
                                
                                # Stop run sound on out
                                if run_sound_playing and run_channel:
                                    run_channel.stop()
                                    run_sound_playing = False
                                
                                if sounds.get('out') and event_channel:
                                    event_channel.play(sounds['out'])
                            else:
                                run = player_move if is_player_batting else computer_move
                                
                                if is_player_batting:
                                    player_score += run
                                    gametext = f"You scored {run} run(s)!"
                                else:
                                    computer_score += run
                                    gametext = f"Computer scored {run} run(s)!"
                                    
                                    # Check if computer wins in second innings
                                    if innings == 2 and computer_score > player_score:
                                        gametext = f"Computer Won! They chased the target of {player_score + 1}!"
                                        is_out = True
                                        game_over = True
                            
                            scored_this_round = True
                    else:
                        gametext = "Hand not detected! Please show your hand clearly."
                elif clock == 25:
                    if is_out:
                        if innings == 1:
                            target = player_score
                            is_player_batting = False
                            is_out = False
                            gametext = f"Innings Over! Computer needs {player_score + 1} to win."
                            innings += 1
                            game_over = False
                        else:
                            # Game Over - Stop all sounds
                            if run_sound_playing and run_channel:
                                run_channel.stop()
                                run_sound_playing = False
                            
                            game_over = True
                            
                            if player_score > computer_score:
                                gametext = "You Won the Game! Press 'N' to restart"
                                if sounds.get('win') and event_channel:
                                    event_channel.play(sounds['win'])
                            elif computer_score > player_score:
                                gametext = "You Lost the Game! Press 'N' to restart"
                                if sounds.get('lose') and event_channel:
                                    event_channel.play(sounds['lose'])
                            else:
                                gametext = "It's a Tie! Press 'N' to restart"
                                if sounds.get('tie') and event_channel:
                                    event_channel.play(sounds['tie'])
                elif clock > 25:
                    # Auto-restart for next round if not game over
                    if not game_over:
                        clock = -1  # Will become 0 after increment
                        gametext = ""
                        gameresult = ""
                        player_move = None
                        computer_move = None
                        success = True

            # Always draw game UI (even before game starts)
            frame = draw_game_ui(frame, clock, gameresult, gametext, player_score, computer_score, 
                        round_num, innings, screen_width, screen_height, is_out, target)
            
            # Debug output every 30 frames
            if clock % 30 == 0 and game_started:
                print(f"Clock: {clock}, Text: {gametext[:30]}..., Score: {player_score}-{computer_score}")
            
            # Show the frame
            cv.imshow('frame', frame)

            key = cv.waitKey(1) & 0xFF
            if key == ord('q'):
                print("Quit key pressed")
                break
            elif key == ord('s') and not game_started:
                print("Starting game...")
                game_started = True
                clock = 0
                gametext = ""
            elif key == ord('n') and game_over:
                print("Restarting game...")
                # Reset everything
                player_score = 0
                computer_score = 0
                is_player_batting = True
                innings = 1
                round_num = 0
                clock = 0
                gametext = ""
                gameresult = ""
                player_move = None
                computer_move = None
                is_out = False
                success = True
                scored_this_round = False
                game_started = False
                target = None
                game_over = False
                
                # Reset animation flags
                gif_played_win = False
                gif_played_lose = False
                celebrating_win = False
                celebrating_lose = False
                celebration_frame_idx = 0
                
                # Stop all sounds
                if run_channel:
                    run_channel.stop()
                if event_channel:
                    event_channel.stop()
                run_sound_playing = False

            # Clock increment
            if game_started and not game_over:
                clock += 1
            elif game_started and game_over and clock <= 50:
                clock += 1
    
    except KeyboardInterrupt:
        print("\nGame interrupted by user")
    except Exception as e:
        print(f"\nError during game execution: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        hand_landmarker.close()
        vid.release()
        cv.destroyAllWindows()
        try:
            pygame.mixer.quit()
        except:
            pass
        print("Game closed successfully")


if __name__ == "__main__":
    play_hand_cricket()