# --- Add this to your imports ---
import pygame
import serial
import time
import os
from serial.tools import list_ports
import sys
import cv2
import numpy as np
import ctypes

# --- Utility functions for port detection ---
def find_arduino_port():
    ports = list_ports.comports()
    for port in ports:
        if ("Arduino" in port.description or 
            "CH340" in port.description or 
            "USB-SERIAL" in port.description or
            "wchusb" in port.device.lower() or
            "usbmodem" in port.device.lower() or
            "usbserial" in port.device.lower()):
            print(f"[INFO] Found potential Arduino on {port.device}: {port.description}")
            return port.device
    print("[ERROR] No Arduino-compatible device found.")
    return None

def try_reconnect():
    port = find_arduino_port()
    if port:
        try:
            ser = serial.Serial(port, BAUD, timeout=1)
            time.sleep(2)
            return ser, port
        except:
            return None, None
    return None, None

# --- Configurations ---
BAUD = 9600
PEAK_THRESHOLD = 30
VPP_FLATLINE_THRESHOLD = 0.5
CALIBRATION_TIME = 7
BPM_AVG_BEATS = 10
PEAK_REFRACTORY = 0.3
HORIZONTAL_SCALE_FACTOR = 15

pulse_wave_path = r"C:\Program Files\QuintaPulse Lab\beep.wav"
flatline_path = r"C:\Program Files\QuintaPulse Lab\flatline.wav"

ctypes.windll.user32.SetProcessDPIAware()

# --- Pygame Init ---
pygame.init()
pygame.mixer.init()

info = pygame.display.Info()
OLED_WIDTH, OLED_HEIGHT = info.current_w, info.current_h
screen = pygame.display.set_mode((OLED_WIDTH, OLED_HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("QuintaPulseLab - Virtual OLED - Heart Monitor")

# Load and set the custom icon
icon_path = r"C:\Program Files\QuintaPulse Lab\quintapulse.png"
try:
    icon = pygame.image.load(icon_path)
    pygame.display.set_icon(icon)
except Exception as e:
    print(f"Could not load icon: {e}")

font_small = pygame.font.SysFont("consolas", 16)
font_medium = pygame.font.SysFont("consolas", 20, bold=True)
font_large = pygame.font.SysFont("consolas", 32, bold=True)
skip_font = pygame.font.SysFont("consolas", 18, bold=True)

#--Video intro--#
def play_intro_inside_pygame(screen):
    video_path = r"C:\Program Files\QuintaPulse Lab\intro.mp4"
    audio_path = r"C:\Program Files\QuintaPulse Lab\intro.wav"

    if not os.path.exists(video_path) or not os.path.exists(audio_path):
        print("Intro video or audio not found.")
        return

    # Load audio
    pygame.mixer.init()
    intro_sound = pygame.mixer.Sound(audio_path)
    intro_sound.play()

    # Load video
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    delay = int(1000 / fps) if fps > 0 else 33

    video_done = False
    show_skip = False
    skip_text = skip_font.render("<Skip>", True, (255, 255, 255))
    skip_rect = skip_text.get_rect(topright=(screen.get_width() - 20, 20)) # Position of the skip text

    while cap.isOpened() and not video_done:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                cap.release()
                pygame.quit()
                exit()
            elif event.type == pygame.MOUSEMOTION:
                show_skip = True
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if show_skip and skip_rect.collidepoint(event.pos):
                    video_done = True
                    pygame.mixer.stop() # Stop the intro sound
                    break # Exit the video loop
            elif event.type == pygame.KEYDOWN: # Allow skipping with a key press as well (optional)
                if event.key == pygame.K_SPACE or event.key == pygame.K_ESCAPE:
                    video_done = True
                    pygame.mixer.stop()
                    break

        ret, frame = cap.read()
        if not ret:
            video_done = True
            break

        # Resize and convert frame to RGB
        frame = cv2.resize(frame, (screen.get_width(), screen.get_height()))
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = cv2.flip(frame, 1)  # Flip the frame horizontally (1 = horizontal flip)
        surface = pygame.surfarray.make_surface(np.rot90(frame))

        screen.blit(surface, (0, 0))

        # Draw the skip text only if the mouse has moved
        if show_skip:
            screen.blit(skip_text, skip_rect)

        pygame.display.update()
        pygame.time.delay(delay)

    cap.release()
    pygame.mixer.stop()

# --- Splash Screen ---
def show_splash_screen():
    start_time = time.time()
    dot_count = 0
    dot_timer = 0
    while time.time() - start_time < 2:
        current_width, current_height = screen.get_size()
        screen.fill((0, 0, 0))
        title = font_large.render("QuintaPulseLab", True, (0, 255, 180))
        screen.blit(title, (current_width // 2 - title.get_width() // 2, current_height // 2 - 40))

        if time.time() - dot_timer > 0.4:
            dot_count = (dot_count + 1) % 4
            dot_timer = time.time()

        loading_text = "Loading" + "." * dot_count
        loading_render = font_small.render(loading_text, True, (180, 180, 255))
        screen.blit(loading_render, (current_width // 2 - loading_render.get_width() // 2, current_height // 2 + 10))

        pygame.display.flip()
        pygame.time.delay(30)

# --- Run startup ---
screen = pygame.display.set_mode((OLED_WIDTH, OLED_HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("QuintaPulseX - Virtual Heart Monitor")
play_intro_inside_pygame(screen)
show_splash_screen()

# --- Try connecting initially ---
ser = None
PORT = None
connected_message_time = 0
ser, PORT = try_reconnect()

# --- Load Sounds ---
beep_sound = pygame.mixer.Sound(pulse_wave_path)
flatline_sound = pygame.mixer.Sound(flatline_path)
flatline_channel = None

def draw_faded_icon_background():
    if icon_image:
        faded_icon = icon_image.copy()
        faded_icon.set_alpha(40)  # Adjust transparency: 0 (invisible) to 255 (fully visible)

        icon_size = (int(current_width * 0.4), int(current_height * 0.4))  # Resize to 40% of screen
        faded_icon = pygame.transform.smoothscale(faded_icon, icon_size)

        icon_rect = faded_icon.get_rect(center=(current_width // 2, current_height // 2))  # Center it
        screen.blit(faded_icon, icon_rect)

# --- Variables ---
raw_values = []
max_val, min_val = 0, 1023
vpp = 0
last_update = time.time()
last_raw = None
flatline_playing = False
flash_toggle = False
flash_timer = time.time()
calibrating = False
calibration_start = None
calibration_vpps = []
VPP_BEEP_THRESHOLD = None
peak_times = []
last_peak_time = 0
running = True
icon_image = pygame.image.load(r"C:\Program Files\QuintaPulse Lab\quintapulse.png").convert_alpha()

# --- Main Loop ---
while running:
    current_width, current_height = screen.get_size()
    x_scale = current_width / OLED_WIDTH
    y_scale = current_height / OLED_HEIGHT
    screen.fill((10, 10, 30))
    draw_faded_icon_background()

    # Check Events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.VIDEORESIZE:
            new_width, new_height = max(event.w, OLED_WIDTH), max(event.h, OLED_HEIGHT)
            screen = pygame.display.set_mode((new_width, new_height), pygame.RESIZABLE)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            calib_button = pygame.Rect(current_width - 340, current_height - 45, 100, 35)
            reset_button = pygame.Rect(current_width - 230, current_height - 45, 100, 35)
            quit_button = pygame.Rect(current_width - 120, current_height - 45, 100, 35)
            if calib_button.collidepoint(event.pos):
                calibrating = True
                calibration_start = time.time()
                calibration_vpps = []
                VPP_BEEP_THRESHOLD = None
                peak_times.clear()
            elif reset_button.collidepoint(event.pos):
                raw_values.clear()
                peak_times.clear()
                VPP_BEEP_THRESHOLD = None
                calibration_vpps = []
                calibrating = False
            elif quit_button.collidepoint(event.pos):
                running = False

    # Try reading from serial if connected
    if ser:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode(errors='ignore').strip()
                raw = int(line)
                raw_values.append(raw)
                max_visible_points = int(current_width / (x_scale * HORIZONTAL_SCALE_FACTOR)) # Calculate max visible points
                if len(raw_values) > max_visible_points:
                    raw_values.pop(0)

                now = time.time()
                if now - last_update > 1:
                    vpp = (max_val - min_val) * 5.0 / 1023.0
                    max_val, min_val = 0, 1023
                    last_update = now

                    if calibrating:
                        calibration_vpps.append(vpp)
                        if now - calibration_start >= CALIBRATION_TIME and calibration_vpps:
                            VPP_BEEP_THRESHOLD = sum(calibration_vpps) / len(calibration_vpps) * 0.7
                            calibrating = False

                max_val = max(max_val, raw)
                min_val = min(min_val, raw)

                is_peak = False
                if last_raw is not None and VPP_BEEP_THRESHOLD:
                    time_since_last_peak = now - last_peak_time
                    if (time_since_last_peak > PEAK_REFRACTORY and
                        raw < last_raw and
                        abs(raw - last_raw) > PEAK_THRESHOLD and
                        vpp > VPP_BEEP_THRESHOLD):
                        is_peak = True
                        last_peak_time = now

                if is_peak:
                    peak_times.append(now)
                    if len(peak_times) > BPM_AVG_BEATS + 1:
                        peak_times.pop(0)
                    if not pygame.mixer.get_busy():
                        beep_sound.play()

                if VPP_BEEP_THRESHOLD and vpp < VPP_FLATLINE_THRESHOLD:
                    if not flatline_playing:
                        flatline_channel = flatline_sound.play(loops=-1)
                        flatline_playing = True
                else:
                    if flatline_playing:
                        if flatline_channel:
                            flatline_channel.stop()
                        flatline_playing = False

                last_raw = raw
        except:
            # Disconnected
            ser = None
            connected_message_time = time.time()

    else:
        # Attempt reconnection every second
        if time.time() - connected_message_time > 1:
            ser, PORT = try_reconnect()
            if ser:
                connected_message_time = time.time()

    if len(raw_values) >= 2:
        for i in range(1, len(raw_values)):
            prev_raw = raw_values[i-1]
            current_raw = raw_values[i]
            prev_y = current_height - int((prev_raw / 1023) * current_height)
            current_y = current_height - int((current_raw / 1023) * current_height)
            x_prev = (i-1) * x_scale * HORIZONTAL_SCALE_FACTOR
            x_current = i * x_scale * HORIZONTAL_SCALE_FACTOR
            pygame.draw.line(screen, (135, 206, 250), (x_prev, prev_y), (x_current, current_y), 2)

    pygame.draw.rect(screen, (20, 20, 40), (0, current_height - 50, current_width, 50))
    vpp_surface = font_medium.render(f"Vpp: {vpp:.2f} V", True, (200, 200, 255))
    bpm_surface = font_medium.render(f"BPM: {int(60 / ((sum([peak_times[i] - peak_times[i-1] for i in range(1, len(peak_times))][-BPM_AVG_BEATS:]) / len(peak_times[-BPM_AVG_BEATS:]))) if len(peak_times) > 1 else 0)}", True, (180, 255, 180))
    screen.blit(vpp_surface, (10, current_height - 40))
    screen.blit(bpm_surface, (10 + vpp_surface.get_width() + 20, current_height - 40))

    if VPP_BEEP_THRESHOLD:
        calib_info = font_small.render(f"Threshold: {VPP_BEEP_THRESHOLD:.2f} V", True, (255, 180, 100))
        screen.blit(calib_info, (current_width // 2 - calib_info.get_width() // 2- 50, current_height - 40))
    elif calibrating:
        calib_info = font_small.render("Calibrating...", True, (255, 255, 0))
        screen.blit(calib_info, (current_width // 2 - calib_info.get_width() // 2 - 50, current_height - 40))

    # Draw Buttons
    calib_button = pygame.Rect(current_width - 340, current_height - 45, 100, 35)
    reset_button = pygame.Rect(current_width - 230, current_height - 45, 100, 35)
    quit_button = pygame.Rect(current_width - 120, current_height - 45, 100, 35)
    pygame.draw.rect(screen, (70, 70, 120), calib_button)
    pygame.draw.rect(screen, (120, 70, 70), reset_button)
    pygame.draw.rect(screen, (180, 60, 60), quit_button)
    screen.blit(font_small.render("Calibrate", True, (255, 255, 255)), (calib_button.x + 10, calib_button.y + 8))
    screen.blit(font_small.render("Reset", True, (255, 255, 255)), (reset_button.x + 25, reset_button.y + 8))
    screen.blit(font_small.render("Quit", True, (255, 255, 255)), (quit_button.x + 30, quit_button.y + 8))

    if not ser:
        alert = font_large.render("Arduino Disconnected", True, (255, 0, 0))
        screen.blit(alert, (current_width // 2 - alert.get_width() // 2, 20))
    elif time.time() - connected_message_time < 2:
        alert = font_large.render("Arduino Connected", True, (0, 255, 100))
        screen.blit(alert, (current_width // 2 - alert.get_width() // 2, 20))

    if flatline_playing:
        if time.time() - flash_timer > 0.5:
            flash_toggle = not flash_toggle
            flash_timer = time.time()
        if flash_toggle:
            banner = pygame.Surface((current_width, 40))
            banner.fill((255, 0, 0))
            alert = font_large.render("ARE YOU DEAD!!", True, (255, 255, 255))
            banner.blit(alert, (current_width // 2 - alert.get_width() // 2, 2))
            screen.blit(banner, (0, 0))

    pygame.display.flip()

# --- Cleanup ---
if ser:
    ser.close()
pygame.quit()
sys.exit()
