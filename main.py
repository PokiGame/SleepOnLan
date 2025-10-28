#!/usr/bin/env python3
# wol_tray_agent.py
import socket
import subprocess
import platform
import threading
import time
import sys
import os
from datetime import datetime
import psutil

# бібліотеки для іконки в треї
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

PORT = 4100
BUF_SIZE = 4096
LOG_PATH = os.path.join(os.path.dirname(__file__), "wol_tray_agent.log")



# прапорець для зупинки треда
running = True

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    print(line, end="")

def shutdown_now():
    """Виконати вимкнення Windows (потрібні адмін-права)."""
    os_name = platform.system()
    log(f"Shutdown requested (OS={os_name})")
    if os_name == "Windows":
        # Викликаємо команду вимкнення
        try:
            subprocess.run(["shutdown", "/s", "/t", "0"], check=False)
        except Exception as e:
            log(f"Failed to run shutdown cmd: {e}")
    else:
        try:
            subprocess.run(["systemctl", "poweroff", "-i"], check=False)
        except Exception as e:
            log(f"Failed to run poweroff: {e}")

def get_local_mac() -> str:
    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == psutil.AF_LINK:
                mac = addr.address
                if mac and mac != "00-00-00-00-00-00":
                    # замінюємо тире на двокрапку
                    return mac.replace("-", ":").upper()
    return None

ALLOWED_MACS = [get_local_mac()]
print("Allowed MAC:", ALLOWED_MACS)

def is_magic_packet(data: bytes) -> bool:
    """Перевіряє структуру WOL-пакету та MAC."""
    ff = b'\xff' * 6
    try:
        start = data.index(ff)
    except ValueError:
        return False
    payload = data[start + 6:]
    if len(payload) < 16*6:
        return False
    mac = payload[:6]
    # конвертуємо в стандартний формат AA:BB:CC:DD:EE:FF
    mac_str = ":".join(f"{b:02X}" for b in mac)
    if mac_str not in ALLOWED_MACS:
        return False
    # перевіряємо повтори MAC
    for i in range(0, 16*6, 6):
        if payload[i:i+6] != mac:
            return False
    return True


def udp_listener(host: str = "", port: int = PORT):
    """Фоновий UDP-слухач; виходить коли global running = False."""
    global running
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # broadcast, на випадок якщо прилетить
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.bind((host, port))
    except Exception as e:
        log(f"Bind error on {host}:{port} -> {e}")
        return

    sock.settimeout(1.0)  # щоб можна було періодично перевіряти running
    log(f"Listening UDP on {host or '0.0.0.0'}:{port}")
    try:
        while running:
            try:
                data, addr = sock.recvfrom(BUF_SIZE)
            except socket.timeout:
                continue
            except OSError:
                # сокет закритий з іншого потоку
                break
            if not running:
                break
            # логнемо коротко — будь-який пакет запускає shutdown
            if is_magic_packet(data):
                log(f"Magic packet accepted from {addr} — executing shutdown")
                shutdown_now()
            else:
                log(f"Packet from {addr} ignored (not allowed MAC)")
            # після shutdown-команди процес може і не продовжити роботу,
            # але якщо тестуєш — можна просто продовжити слухати
    finally:
        try:
            sock.close()
        except Exception:
            pass
        log("UDP listener stopped")

def create_image(width=64, height=64, color1=(0, 0, 0), color2=(255, 0, 0)):
    """Генерує просту квадратну іконку PIL (можна замінити на файл .ico)."""
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    # фон
    draw.rectangle((0, 0, width, height), fill=(30, 30, 30, 255))
    # простий символ — блискавка/трикут
    points = [
        (width*0.35, height*0.15),
        (width*0.6, height*0.45),
        (width*0.5, height*0.45),
        (width*0.65, height*0.85),
        (width*0.4, height*0.5),
        (width*0.5, height*0.5),
    ]
    draw.polygon(points, fill=color2)
    return image

# --- Tray/menu callbacks ---
listener_thread = None
icon = None

def on_show_log(icon, item):
    # просто відкриває лог-файл у блокноті (якщо існує)
    if os.path.exists(LOG_PATH):
        try:
            subprocess.Popen(["notepad.exe", LOG_PATH])
        except Exception as e:
            log(f"Failed to open log: {e}")
    else:
        log("Log file not found")

def stop(icon, item):
    global running, listener_thread
    log("Exit requested from tray")
    running = False
    # зупинити іконку (вона повертає run())
    try:
        icon.stop()
    except Exception:
        pass
    # закрити слушач: створимо UDP-з'єднання до самого себе, щоб швидше вийшов recvfrom
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(b"stop", ("127.0.0.1", PORT))
        s.close()
    except Exception:
        pass
    # дочекаємось завершення треда (макс 3 с)
    if listener_thread and listener_thread.is_alive():
        listener_thread.join(timeout=3)
    log("Agent stopped")
    # після цього процес завершиться звичайно

def start_tray():
    global icon
    image = create_image()
    menu = (item('Open log', on_show_log), item('Exit', stop))
    icon = pystray.Icon("WOL Shutdown Agent", image, "WOL Shutdown", menu)
    icon.run()

def main():
    global listener_thread, running
    # чистимо старий лог щоб було видно останні події (опціонально)
    # with open(LOG_PATH, "w", encoding="utf-8") as f: f.write("")

    running = True
    # стартуєм фоновий слухач
    listener_thread = threading.Thread(target=udp_listener, args=("", PORT), daemon=True)
    listener_thread.start()

    # запускаємо трей (блокує). Меню дозволяє зупинити процедуру.
    try:
        start_tray()
    except KeyboardInterrupt:
        log("KeyboardInterrupt")
    finally:
        running = False
        # надсилаємо пустий пакет щоб розблокувати recvfrom
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(b"stop", ("127.0.0.1", PORT))
            s.close()
        except Exception:
            pass
        if listener_thread and listener_thread.is_alive():
            listener_thread.join(timeout=3)
        log("Exiting main")

if __name__ == "__main__":
    main()
