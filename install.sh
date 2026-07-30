#!/data/data/com.termux/files/usr/bin/bash
# One-time setup for frame60 on Termux.
set -e

pkg update -y
pkg install -y python ffmpeg

echo
echo "Optional (enables battery-temp lag protection as a fallback when"
echo "/sys/class/thermal isn't readable on your device):"
echo "  pkg install termux-api   (and install the Termux:API app from F-Droid)"
echo
echo "Setup complete. Run from inside this project folder with:"
echo "  python -m frame60 IN.mp4 OUT.mp4 --profile battery-saver"
