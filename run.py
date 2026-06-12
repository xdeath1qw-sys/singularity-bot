import subprocess
import sys
import os

print("🚀 Запуск бота...")

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
