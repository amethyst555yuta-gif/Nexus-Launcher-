# NEXUS LAUNCHER

A lightweight, custom Minecraft Java Edition multi-instance launcher built completely from scratch in Python. It features a modern Cyberpunk UI powered by `customtkinter`.

## 🚨 Current Critical Issue (Asset Loading Failure)

The launcher successfully synchronizes game jars, native libraries, and executes the game subprocess. However, the game client fails to load core assets (textures, languages, and audio streams correctly). 

### Symptoms:
- **Modern Versions (1.13 up to 1.20.1+):** The game starts but is stuck on a **solid grey fallback background** (formerly missing textures pattern). Audio is completely muted with continuous `Missing sound for event` warnings spamming the console stream.
- **Legacy Versions (1.12.2 and below):** The textures and main menu panorama **load perfectly**, but the game is still **completely muted** (no sound).

### Root Cause Suspect:
The issue lies heavily within the asset index directories and the launch arguments generation. Modern Minecraft versions expect strict Hash Object parsing (`assets/objects/`), while legacy versions require a virtual structure mapping (`assets/virtual/legacy/`). Our current implementation is failing to bridge the `--assetsDir` and `--assetIndex` arguments properly across different version generations, causing the game to look in the wrong paths for resources.

## 🛠️ Project Structure & Tech Stack
- **Language:** Python 3.12+
- **GUI Framework:** CustomTkinter (flat widgets, modern theme)
- **Core Logic:** Native Python `urllib` (downloader), `threading` (non-blocking UI), and `subprocess` (JVM execution handler).

## 🤝 How to Help
If you are a Python developer or have experience writing Minecraft Launchers (using tools like `minecraft-launcher-lib` or raw launch string building), please check out `NEXUSLAUNCHER.py`. 

We need help fixing the **asset folder structuring algorithm** and **JVM argument formatting** so that all versions can fetch and read their assets properly.
