import json
import os
import requests
from bs4 import BeautifulSoup


DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")


def load_comics():
    with open("comics.json", "r", encoding="utf-8") as file:
        return json.load(file)


def get_latest_chapter(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    # Nanti bagian ini disesuaikan
    # dengan struktur HTML halaman Baozi.
    chapters = soup.select("#chapter-items a.comics-chapters__item")

    if not chapters:
        return None

    return chapters[0].get_text(strip=True)


def send_discord(name, chapter, url):
    message = {
        "content": (
            f"🔔 **Komik Update!**\n\n"
            f"📖 **{name}**\n"
            f"🆕 **{chapter}**\n"
            f"🔗 {url}"
        )
    }

    response = requests.post(
        DISCORD_WEBHOOK,
        json=message,
        timeout=30
    )

    response.raise_for_status()


def main():
    comics = load_comics()

    for comic in comics:
        name = comic["name"]
        url = comic["url"]

        try:
            latest = get_latest_chapter(url)

            print(
                f"{name}: {latest}"
            )

        except Exception as error:
            print(
                f"Gagal mengecek {name}: {error}"
            )


if __name__ == "__main__":
    main()
