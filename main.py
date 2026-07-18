import json
import os
import re
import requests
from bs4 import BeautifulSoup


# =========================================================
# KONFIGURASI
# =========================================================

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")

COMICS_FILE = "comics.json"
STATE_FILE = "state.json"


# =========================================================
# MEMBACA DAFTAR KOMIK
# =========================================================

def load_comics():
    with open(COMICS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


# =========================================================
# MEMBACA STATE / CHAPTER TERAKHIR
# =========================================================

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}

    with open(STATE_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


# =========================================================
# MENYIMPAN STATE / CHAPTER TERBARU
# =========================================================

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(
            state,
            file,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# MENGAMBIL CHAPTER TERBESAR DARI BAOZI
# =========================================================

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

    # Mengambil semua item chapter
    chapter_items = soup.select(
        "a.comics-chapters__item"
    )

    if not chapter_items:
        raise Exception(
            "Tidak menemukan daftar chapter di halaman Baozi."
        )

    chapters = []

    for item in chapter_items:
        # Mengambil teks chapter
        text = item.get_text(
            " ",
            strip=True
        )

        # Mencari nomor episode/chapter
        # Contoh:
        # Episode 24: Judul Chapter
        match = re.search(
            r"(?:Episode|Chapter|Bab)\s*(\d+)",
            text,
            re.IGNORECASE
        )

        if not match:
            continue

        chapter_number = int(
            match.group(1)
        )

        # Mengambil link chapter
        chapter_url = item.get(
            "href"
        )

        # Jika URL masih relatif
        if chapter_url and chapter_url.startswith("/"):
            from urllib.parse import urljoin

            chapter_url = urljoin(
                url,
                chapter_url
            )

        chapters.append({
            "number": chapter_number,
            "title": text,
            "url": chapter_url
        })

    if not chapters:
        raise Exception(
            "Tidak menemukan nomor chapter/episode."
        )

    # Mencari chapter dengan nomor terbesar
    latest = max(
        chapters,
        key=lambda chapter: chapter["number"]
    )

    return latest


# =========================================================
# MENGIRIM NOTIFIKASI KE DISCORD
# =========================================================

def send_discord(
    comic_name,
    chapter,
    comic_url
):

    if not DISCORD_WEBHOOK:
        raise Exception(
            "DISCORD_WEBHOOK belum diatur."
        )

    message = {
        "embeds": [
            {
                "title": "🔔 Komik Update!",
                "description": (
                    f"**{comic_name}**\n\n"
                    f"🆕 **{chapter['title']}**"
                ),
                "url": comic_url,
                "color": 5814783,
                "fields": [
                    {
                        "name": "Chapter",
                        "value": str(
                            chapter["number"]
                        ),
                        "inline": True
                    }
                ]
            }
        ]
    }

    response = requests.post(
        DISCORD_WEBHOOK,
        json=message,
        timeout=30
    )

    response.raise_for_status()


# =========================================================
# PROGRAM UTAMA
# =========================================================

def main():

    comics = load_comics()

    state = load_state()

    state_changed = False

    for comic in comics:

        comic_name = comic["name"]
        comic_url = comic["url"]

        print(
            f"\nMengecek: {comic_name}"
        )

        try:

            # Mengambil chapter terbaru
            latest = get_latest_chapter(
                comic_url
            )

            latest_number = latest[
                "number"
            ]

            print(
                f"Chapter terbaru di Baozi: "
                f"{latest_number}"
            )

            # Chapter terakhir yang tersimpan
            last_number = state.get(
                comic_name
            )

            # Jika belum pernah disimpan
            if last_number is None:

                print(
                    "Belum ada data chapter sebelumnya."
                )

                # Simpan chapter terbaru
                state[comic_name] = (
                    latest_number
                )

                state_changed = True

                print(
                    f"State awal disimpan: "
                    f"{latest_number}"
                )

                # Tidak mengirim notif saat pertama kali
                continue

            last_number = int(
                last_number
            )

            print(
                f"Chapter terakhir tersimpan: "
                f"{last_number}"
            )

            # =================================================
            # JIKA ADA CHAPTER BARU
            # =================================================

            if latest_number > last_number:

                print(
                    f"UPDATE DITEMUKAN! "
                    f"{last_number} → "
                    f"{latest_number}"
                )

                # Kirim notifikasi Discord
                send_discord(
                    comic_name,
                    latest,
                    comic_url
                )

                # Update state
                state[comic_name] = (
                    latest_number
                )

                state_changed = True

                print(
                    "Notifikasi berhasil dikirim."
                )

            # =================================================
            # JIKA TIDAK ADA UPDATE
            # =================================================

            elif latest_number == last_number:

                print(
                    "Tidak ada chapter baru."
                )

            # =================================================
            # JIKA CHAPTER TURUN
            # =================================================

            else:

                print(
                    "PERINGATAN: Nomor chapter "
                    "di Baozi lebih kecil dari "
                    "state.json."
                )

                print(
                    "State tidak diubah."
                )

        except Exception as error:

            print(
                f"Gagal mengecek "
                f"{comic_name}: {error}"
            )

    # =========================================================
    # SIMPAN STATE JIKA ADA PERUBAHAN
    # =========================================================

    if state_changed:

        save_state(state)

        print(
            "\nstate.json berhasil diperbarui."
        )

    else:

        print(
            "\nTidak ada perubahan pada state.json."
        )


# =========================================================
# JALANKAN PROGRAM
# =========================================================

if __name__ == "__main__":
    main()
