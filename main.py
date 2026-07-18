import json
import os
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# =========================================================
# KONFIGURASI
# =========================================================

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")

COMICS_FILE = "comics.json"
STATE_FILE = "state.json"

# =========================================================
# KONFIGURASI KHUSUS INFINITE EVOLUTION
# =========================================================

INFINITE_EVOLUTION_NAME = "Infinite Evolution Starting From Zero"

INFINITE_EVOLUTION_REFERENCE_TITLE = "就好這口"

INFINITE_EVOLUTION_REFERENCE_CHAPTER = 107


# =========================================================
# MEMBACA DAFTAR KOMIK
# =========================================================

def load_comics():

    with open(
        COMICS_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# =========================================================
# MEMBACA STATE TERAKHIR
# =========================================================

def load_state():

    if not os.path.exists(STATE_FILE):

        return {}

    with open(
        STATE_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# =========================================================
# MENYIMPAN STATE
# =========================================================

def save_state(state):

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            state,
            file,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# MENGAMBIL NOMOR CHAPTER DARI JUDUL
# KHUSUS KOMIK YANG MENULIS NOMOR DI JUDUL
# =========================================================

def extract_chapter_number(title):

    patterns = [

        # Contoh:
        # 第74話 吳法現身？！
        r"第\s*(\d+)\s*[話话章]",

        # Contoh:
        # Chapter 74
        r"(?:Chapter|CHAPTER)\s*(\d+)",

        # Contoh:
        # Episode 74
        r"(?:Episode|EPISODE)\s*(\d+)",

        # Contoh:
        # Bab 74
        r"(?:Bab|BAB)\s*(\d+)",

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            title
        )

        if match:

            return int(
                match.group(1)
            )


    # Tidak ditemukan nomor
    return None


# =========================================================
# MENGHITUNG NOMOR CHAPTER INFINITE EVOLUTION
#
# 就好這口 = Chapter 107
#
# Chapter setelahnya:
# 就好這口        = 107
# Chapter berikut = 108
# Chapter berikut = 109
# =========================================================

def get_infinite_evolution_chapter_number(
    chapters,
    current_chapter
):

    reference_chapter = None


    # =====================================================
    # CARI CHAPTER PATOKAN
    # =====================================================

    for chapter in chapters:

        if (
            INFINITE_EVOLUTION_REFERENCE_TITLE
            in chapter["title"]
        ):

            reference_chapter = chapter

            break


    # =====================================================
    # PATOKAN TIDAK DITEMUKAN
    # =====================================================

    if reference_chapter is None:

        raise Exception(

            "Chapter patokan "
            f"'{INFINITE_EVOLUTION_REFERENCE_TITLE}' "
            "tidak ditemukan. "
            "Tidak dapat menentukan nomor chapter "
            "Infinite Evolution."

        )


    # =====================================================
    # HITUNG NOMOR CHAPTER
    # BERDASARKAN DATA-INDEX
    # =====================================================

    chapter_difference = (

        current_chapter[
            "data_index"
        ]

        -

        reference_chapter[
            "data_index"
        ]

    )


    chapter_number = (

        INFINITE_EVOLUTION_REFERENCE_CHAPTER

        +

        chapter_difference

    )


    return chapter_number


# =========================================================
# MENGAMBIL SEMUA CHAPTER DARI BAOZI
# =========================================================

def get_chapters(url):

    headers = {

        "User-Agent": (

            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
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


    # =====================================================
    # MENGAMBIL SEMUA CHAPTER
    # =====================================================

    chapter_items = soup.select(

        "a.comics-chapters__item"

    )


    if not chapter_items:

        raise Exception(

            "Tidak menemukan chapter "
            "dengan selector "
            ".comics-chapters__item"

        )


    chapters = []


    for position, item in enumerate(
        chapter_items
    ):


        # =================================================
        # MENGAMBIL DATA-INDEX
        # =================================================

        data_index = item.get(

            "data-index"

        )


        if data_index is not None:

            try:

                data_index = int(

                    data_index

                )

            except ValueError:

                data_index = position

        else:

            data_index = position


        # =================================================
        # MENGAMBIL JUDUL CHAPTER
        # =================================================

        title = item.get_text(

            " ",

            strip=True

        )


        # =================================================
        # MENGAMBIL NOMOR CHAPTER
        #
        # Untuk Urban Dragon:
        # ambil nomor dari judul
        #
        # Untuk Infinite Evolution:
        # dihitung nanti berdasarkan patokan
        # =================================================

        chapter_number = (

            extract_chapter_number(

                title

            )

        )


        # =================================================
        # MENGAMBIL URL CHAPTER
        # =================================================

        chapter_url = item.get(

            "href"

        )


        if chapter_url:

            chapter_url = urljoin(

                url,

                chapter_url

            )


        # =================================================
        # MENYIMPAN DATA CHAPTER
        # =================================================

        chapters.append({

            "data_index":
                data_index,

            "number":
                chapter_number,

            "title":
                title,

            "url":
                chapter_url

        })


    return chapters


# =========================================================
# MENENTUKAN CHAPTER TERBARU
# =========================================================

def get_latest_chapter(
    chapters,
    comic_name
):

    if not chapters:

        return None


    # =====================================================
    # KHUSUS INFINITE EVOLUTION
    #
    # Gunakan data-index terbesar.
    #
    # Nomor chapter akan dihitung berdasarkan
    # 就好這口 = Chapter 107
    # =====================================================

    if comic_name == INFINITE_EVOLUTION_NAME:

        latest = max(

            chapters,

            key=lambda chapter:

                chapter[
                    "data_index"
                ]

        )


        latest[
            "number"
        ] = get_infinite_evolution_chapter_number(

            chapters,

            latest

        )


        return latest


    # =====================================================
    # KOMIK LAIN / URBAN DRAGON
    #
    # Tetap menggunakan sistem sebelumnya
    # =====================================================

    numbered_chapters = [

        chapter

        for chapter in chapters

        if chapter[
            "number"
        ] is not None

    ]


    if numbered_chapters:

        return max(

            numbered_chapters,

            key=lambda chapter:

                chapter[
                    "number"
                ]

        )


    # Jika tidak ada nomor,
    # gunakan data-index terbesar

    return max(

        chapters,

        key=lambda chapter:

            chapter[
                "data_index"
            ]

    )


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


    # =====================================================
    # MENAMPILKAN NOMOR CHAPTER
    # =====================================================

    if chapter[
        "number"
    ] is not None:

        chapter_display = (

            f"Chapter "

            f"{chapter['number']}"

        )

    else:

        chapter_display = (

            f"Chapter baru "

            f"(Index "

            f"{chapter['data_index']})"

        )


    # =====================================================
    # PESAN DISCORD
    # =====================================================

    message = {

        "content":
            "<@892775710408732702>",

        "embeds": [

            {

                "title":
                    "🔔 Komik Update!",

                "description": (

                    f"📖 **{comic_name}**\n\n"

                    f"🆕 "
                    f"**{chapter_display}**\n\n"

                    f"📝 "
                    f"{chapter['title']}"

                ),

                "url":
                    comic_url,

                "color":
                    5814783

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
# MEMBUAT IDENTITAS CHAPTER
# =========================================================

def get_chapter_id(
    chapter,
    comic_name
):

    # =====================================================
    # KHUSUS INFINITE EVOLUTION
    #
    # Gunakan data-index sebagai ID.
    #
    # Karena nomor chapter dihitung dari patokan.
    # =====================================================

    if comic_name == INFINITE_EVOLUTION_NAME:

        return (

            f"index:"

            f"{chapter['data_index']}"

        )


    # =====================================================
    # URBAN DRAGON
    #
    # Tetap menggunakan nomor chapter
    # =====================================================

    if chapter[
        "number"
    ] is not None:

        return (

            f"number:"

            f"{chapter['number']}"

        )


    # =====================================================
    # FALLBACK
    # =====================================================

    return (

        f"index:"

        f"{chapter['data_index']}"

    )


# =========================================================
# PROGRAM UTAMA
# =========================================================

def main():

    comics = load_comics()

    state = load_state()

    state_changed = False


    # =====================================================
    # CEK SETIAP KOMIK
    # =====================================================

    for comic in comics:

        comic_name = comic[
            "name"
        ]

        comic_url = comic[
            "url"
        ]


        print(

            "\n=============================="

        )


        print(

            f"Mengecek: "

            f"{comic_name}"

        )


        try:

            # =================================================
            # AMBIL SEMUA CHAPTER
            # =================================================

            chapters = get_chapters(

                comic_url

            )


            print(

                f"Total chapter ditemukan: "

                f"{len(chapters)}"

            )


            # =================================================
            # CARI CHAPTER TERBARU
            # =================================================

            latest = get_latest_chapter(

                chapters,

                comic_name

            )


            if latest is None:

                print(

                    "Tidak menemukan "
                    "chapter terbaru."

                )

                continue


            # =================================================
            # TAMPILKAN INFO CHAPTER
            # =================================================

            print(

                "Chapter terbaru:"

            )


            print(

                f"  Index: "

                f"{latest['data_index']}"

            )


            print(

                f"  Nomor: "

                f"{latest['number']}"

            )


            print(

                f"  Judul: "

                f"{latest['title']}"

            )


            # =================================================
            # AMBIL STATE KOMIK
            # =================================================

            comic_state = state.get(

                comic_name

            )


            # =================================================
            # PERTAMA KALI DIPANTAU
            # =================================================

            if comic_state is None:

                print(

                    "Komik belum memiliki "
                    "state sebelumnya."

                )


                # =================================================
                # SIMPAN DATA CHAPTER TERBARU
                # =================================================

                state[
                    comic_name
                ] = {

                    "data_index":

                        latest[
                            "data_index"
                        ],

                    "number":

                        latest[
                            "number"
                        ],

                    "title":

                        latest[
                            "title"
                        ],

                    "chapter_id":

                        get_chapter_id(

                            latest,

                            comic_name

                        )

                }


                state_changed = True


                print(

                    "State awal berhasil disimpan."

                )


                # =================================================
                # TIDAK MENGIRIM NOTIF
                # SAAT PERTAMA KALI
                # =================================================

                continue


            # =================================================
            # CEK IDENTITAS CHAPTER
            # =================================================

            latest_id = get_chapter_id(

                latest,

                comic_name

            )


            last_id = comic_state.get(

                "chapter_id"

            )


            print(

                f"Chapter ID terakhir: "

                f"{last_id}"

            )


            print(

                f"Chapter ID terbaru: "

                f"{latest_id}"

            )


            # =================================================
            # TIDAK ADA UPDATE
            # =================================================

            if latest_id == last_id:

                print(

                    "Tidak ada chapter baru."

                )

                continue


            # =================================================
            # ADA CHAPTER BARU
            # =================================================

            print(

                "Chapter baru ditemukan!"

            )


            # =================================================
            # KIRIM NOTIFIKASI
            # =================================================

            send_discord(

                comic_name,

                latest,

                comic_url

            )


            print(

                "Notifikasi Discord berhasil dikirim."

            )


            # =================================================
            # UPDATE STATE
            # =================================================

            state[
                comic_name
            ] = {

                "data_index":

                    latest[
                        "data_index"
                    ],

                "number":

                    latest[
                        "number"
                    ],

                "title":

                    latest[
                        "title"
                    ],

                "chapter_id":

                    latest_id

            }


            state_changed = True


            print(

                "State berhasil diperbarui."

            )


        except Exception as error:

            print(

                f"❌ Gagal mengecek "

                f"{comic_name}: "

                f"{error}"

            )


    # =========================================================
    # SIMPAN STATE
    # =========================================================

    if state_changed:

        save_state(

            state

        )


        print(

            "\n✅ state.json berhasil disimpan."

        )

    else:

        print(

            "\nTidak ada perubahan state."

        )


# =========================================================
# JALANKAN PROGRAM
# =========================================================

if __name__ == "__main__":

    main()
