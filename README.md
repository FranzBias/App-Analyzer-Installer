# 📦 App Analyzer Installer

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Debian)
![Author](https://img.shields.io/badge/made%20with-%E2%9D%A4%EF%B8%8F%20by%20FranzBias-blueviolet)

---

Hey everyone! 👋 Welcome to this page — here you'll find a handy little tool to snapshot your installed apps and bring your setup back to life on a new machine, no sweat. Hope you find it useful!

---

A Python/Tkinter GUI app to **analyze** your installed applications and **quickly recreate** your setup on another PC.

Supports apps installed via **APT** and **Flatpak**.

## ⚙️ Requirements

- Python 3 (pre-installed on Ubuntu/Debian)
- Tkinter (usually included, otherwise: `sudo apt install python3-tk`)

## 🚀 Getting Started

```bash
python3 app-analyzer-installer.py
```

---

## ✨ Features

### 💾 Save

Choose a destination folder and click **Start Scan**: the app will analyze your system and automatically save two files:

- `apps-YYYY-MM-DD_HHMMSS.manifest` — unified APT + Flatpak + Snap list
- `flatpak-YYYY-MM-DD_HHMMSS` — separate Flatpak list (for convenience)

The APT list is cleaned up automatically, no questions asked.

### 📥 Install

Select one or both previously saved files and click **Start Installation**.

Before installing any package, the app automatically runs:
```
sudo apt update
sudo apt upgrade -y
```

Packages are then installed **one at a time**: if a package is not found or throws an error, it is skipped and the process continues with the next one. A summary of skipped packages is shown at the end.

If the `.manifest` file contains Flatpak apps but `flatpak` is not installed on the system, the app will install it automatically via APT before proceeding.

---

## 🧹 APT List Cleanup

APT lists often contain packages that are not suitable for transfer to another PC:
- kernel, bootloader, system modules
- libraries (`lib*`), `-dev`, `-dbg` packages
- toolchains (gcc, make, cmake…)
- automatically installed dependencies

The app automatically applies a filter based on `apt-mark showmanual` and a set of regex rules to remove anything that might cause issues. It's still a good idea to review the manifest before installing on a new system.

---

## 📄 File Format

### `.manifest`
```
# App Analyzer Installer manifest
# created: 2026-06-08T14:30:22
# host: my-pc

[APT]
gimp
vlc
...

[FLATPAK]
org.libreoffice.LibreOffice
...

[SNAP]
spotify
...
```

### `flatpak-*`
```
# App Analyzer Installer - Flatpak List
# created: 2026-06-08T14:30:22
# host: my-pc

org.libreoffice.LibreOffice
com.spotify.Client
...
```

---

## 🔄 Typical Workflow

1. On the **source PC**: launch the app, choose a folder, click **Start Scan**
2. Copy the folder to a USB drive or cloud storage
3. On the **destination PC**: launch the app, select the saved files, click **Start Installation**
