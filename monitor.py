import asyncio
import json
import os
import re
from datetime import datetime
from playwright.async_api import async_playwright
import requests

# ============ НАСТРОЙКИ ============
URL = "https://tb.by/individuals/crediting/top/kreditnyy-produkt--milyy-dom-/"
import os
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
STATE_FILE = "state.json"  # файл, где хранится предыдущее значение
# ===================================

def send_telegram(message):
    """Отправляет сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        response = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=10
        )
        if response.status_code == 200:
            print(f"[{datetime.now():%H:%M:%S}] Уведомление отправлено в Telegram")
        else:
            print(f"[{datetime.now():%H:%M:%S}] Ошибка Telegram: {response.status_code} — {response.text}")
    except Exception as e:
        print(f"[{datetime.now():%H:%M:%S}] Ошибка отправки в Telegram: {e}")

def load_previous():
    """Загружает предыдущее значение из файла"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_current(data):
    """Сохраняет текущее значение в файл"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def get_rate():
    """Заходит на сайт через настоящий браузер и вытаскивает цифры"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print(f"[{datetime.now():%H:%M:%S}] Открываю страницу...")
        await page.goto(URL, wait_until="networkidle", timeout=60000)

        # Ждём, пока появятся элементы с классом deposit-banner__feature-title
        try:
            await page.wait_for_selector(".deposit-banner__feature-title", timeout=30000)
        except Exception:
            print(f"[{datetime.now():%H:%M:%S}] Не дождался появления элементов. Возможно, сайт изменился.")
            await browser.close()
            return None

        # Забираем все три значения (сумма, ставка, срок)
        elements = await page.query_selector_all(".deposit-banner__feature-title")
        values = []
        for el in elements:
            text = await el.inner_text()
            values.append(text.strip())

        await browser.close()

        if len(values) >= 3:
            # Обычно: [0] = сумма, [1] = ставка, [2] = срок
            result = {
                "сумма": values[0],
                "ставка": values[1],
                "срок": values[2],
            }
            return result
        else:
            print(f"[{datetime.now():%H:%M:%S}] Нашёл {len(values)} элементов вместо 3")
            return None

async def main():
    print(f"\n[{datetime.now():%H:%M:%S}] === Проверка ставки ===")
    current = await get_rate()

    if not current:
        print(f"[{datetime.now():%H:%M:%S}] Не удалось получить данные.")
        return

    print(f"[{datetime.now():%H:%M:%S}] Текущие значения:")
    for k, v in current.items():
        print(f"    {k}: {v}")

    previous = load_previous()

    if previous:
        print(f"[{datetime.now():%H:%M:%S}] Предыдущие значения:")
        for k, v in previous.items():
            print(f"    {k}: {v}")

        # Проверяем изменения
        changes = []
        for key in current:
            if key in previous and previous[key] != current[key]:
                changes.append(f"{key}: {previous[key]} → {current[key]}")

        if changes:
            msg = "🔔 ИЗМЕНЕНИЕ НА САЙТЕ БАНКА!\n\n" + "\n".join(changes)
            send_telegram(msg)
            print(f"[{datetime.now():%H:%M:%S}] Отправлено: {msg}")
        else:
            print(f"[{datetime.now():%H:%M:%S}] Изменений нет.")
    else:
        print(f"[{datetime.now():%H:%M:%S}] Первый запуск — сохраняю значения.")
        send_telegram("✅ Мониторинг запущен!\n\nТекущие значения:\n" +
                      "\n".join([f"{k}: {v}" for k, v in current.items()]))

    save_current(current)
    print(f"[{datetime.now():%H:%M:%S}] === Готово ===\n")

if __name__ == "__main__":
    asyncio.run(main())
