# ⚡ WOL Shutdown Tray Agent

A small Python utility that runs in the system tray and listens for a specific **Wake-on-LAN (WOL) Magic Packet**.

**Instead of waking the system, this agent is designed to execute a graceful system shutdown when it receives a WOL packet matching its own MAC address on UDP port 4100.**

This can be useful for scenarios where you want to remotely trigger a shutdown using a standard WOL mechanism from another device.

---

## 🚀 Features

* **UDP Listener:** Runs a background thread listening for UDP packets on port `4100`.
* **WOL Packet Validation:** Checks if the received packet is a standard WOL "Magic Packet".
* **MAC Address Filter:** Only responds to a Magic Packet containing the **agent's own MAC address**.
* **System Tray Icon:** Provides a tray icon for easy access to the log file and a clean exit mechanism.
* **Graceful Shutdown:** Executes the native system shutdown command on Windows (`shutdown /s /t 0`) or Linux (`systemctl poweroff -i`).

---

## 🛠️ Requirements

* Python 3.x
* The following Python libraries (install via pip):
    ```bash
    pip install pystray Pillow psutil
    ```

---

## 💡 How to Use

1.  **Install Dependencies:**
    ```bash
    pip install pystray Pillow psutil
    ```

2.  **Run the Agent:**
    ```bash
    python wol_tray_agent.py
    ```
    The agent will start, print its allowed MAC address, begin listening, and appear as an icon in your system tray.

3.  **Trigger Shutdown:**
    * Use any standard Wake-on-LAN utility (e.g., a mobile app or a command-line tool) to send a Magic Packet.
    * The packet **must target the agent's own MAC address** (the one printed on startup).
    * The packet must be sent to the IP address of the machine running the agent, usually on **UDP port 4100**.

4.  **Exit:**
    * Right-click the tray icon and select "**Exit**" to gracefully stop the agent.

---

## 📝 Logging

All activities (startup, incoming packets, shutdown requests) are logged to a file named `wol_tray_agent.log` in the same directory as the script. You can view the log by selecting "**Open log**" from the tray menu.

---

## ⚠️ Note on Permissions

On **Windows**, executing the system shutdown command (`shutdown /s /t 0`) typically requires the script to be run with **Administrator privileges**. Ensure you run the script as an administrator if the shutdown functionality is critical.
