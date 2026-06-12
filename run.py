import subprocess
import sys
import os

print("🚀 Запуск бота...")

# Устанавливаем ffmpeg если его нет
if not os.path.exists("/usr/bin/ffmpeg") and not os.path.exists("/usr/local/bin/ffmpeg"):
    print("📦 Устанавливаем ffmpeg...")
    subprocess.run(["apt-get", "install", "-y", "-qq", "ffmpeg"], check=False)
    if not os.path.exists("/usr/bin/ffmpeg"):
        subprocess.run(["apt-get", "update", "-qq"], check=False)
        subprocess.run(["apt-get", "install", "-y", "-qq", "ffmpeg"], check=False)
    print("✅ ffmpeg установлен")

while True:
    # Запускаем бота
    result = subprocess.run([sys.executable, "bot.py"], cwd=os.path.dirname(os.path.abspath(__file__)))

    # Код 42 = сигнал перезапуска от кнопки
    if result.returncode == 42:
        print("🔄 Перезапуск бота...")
        continue
    else:
        print(f"🛑 Бот остановлен (код {result.returncode})")
        break
