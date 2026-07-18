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

INFINITE_EVOLUTION_NAME = (
    "Infinite Evolution Starting from Zero"
)

# Berdasarkan data yang kamu berikan:
#
# data-index 133 = Chapter 109
#
# Maka:
#
# data-index 134 = Chapter 110
# data-index 135 = Chapter 111
# data-index 136 = Chapter 112
#
# dan seterusnya.

INFINITE_EVOLUTION_REFERENCE_INDEX = 133

INFINITE_EVOLUTION_REFERENCE_CHAPTER = 109


# =========================================================
# DISCORD USER ID
# =========================================================

DISCORD_USER_ID = "892775710408732702"


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
#
# Digunakan untuk Urban Dragon Reveal
#
# Contoh:
#
# 第74話 吳法現身？！  -> 74
# 第82話 彗星撞地球！  -> 82
#
# Chapter 74              -> 74
# Episode 74              -> 74
# Bab 74                  -> 74
# =========================================================

def extract_chapter_number(title):

    patterns = [

        # Contoh:
        # 第74話 吳法現身？！
        # 第82話 彗星撞地球！
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
# PATOKAN:
#
# data-index 133 = Chapter 109
#
# RUMUS:
#
# Nomor chapter =
# 109 + (data-index sekarang - 133)
#
# Contoh:
#
# Index 133 -> 109
# Index 134 -> 110
# Index 135 -> 111
# Index 136 -> 112
# =========================================================

def get_infinite_evolution_chapter_number(
    current_chapter
):

    chapter_difference = (

        current_chapter[
            "data_index"
        ]

        -

        INFINITE_EVOLUTION_REFERENCE_INDEX

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
        # nomor diambil dari judul.
        #
        # Untuk Infinite Evolution:
        # nomor akan dihitung khusus nanti.
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
    # Nomor chapter dihitung dari:
    #
    # Index 133 = Chapter 109
    # =====================================================

    if comic_name == INFINITE_EVOLUTION_NAME:

        latest = max(

            chapters,

            key=lambda chapter:
                chapter[
                    "data_index"
                ]

        )


        # Hitung nomor chapter
        latest[
            "number"
        ] = get_infinite_evolution_chapter_number(

            latest

        )


        return latest


    # =====================================================
    # KOMIK LAIN
    #
    # Urban Dragon tetap menggunakan
    # nomor chapter dari judul.
    # =====================================================

    numbered_chapters = [

        chapter

        for chapter in chapters

        if chapter[
            "number"
        ] is not None

    ]


    # =====================================================
    # JIKA ADA NOMOR CHAPTER
    # =====================================================

    if numbered_chapters:

        return max(

            numbered_chapters,

            key=lambda chapter:
                chapter[
                    "number"
                ]

        )


    # =====================================================
    # JIKA TIDAK ADA NOMOR
    #
    # Gunakan data-index terbesar.
    # =====================================================

    return max(

        chapters,

        key=lambda chapter:
            chapter[
                "data_index"
            ]

    )


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
    # Gunakan data-index sebagai identitas.
    #
    # Contoh:
    #
    # Index 133 -> index:133
    # Index 134 -> index:134
    # =====================================================

    if comic_name == INFINITE_EVOLUTION_NAME:

        return (

            f"index:"
            f"{chapter['data_index']}"

        )


    # =====================================================
    # KOMIK LAIN
    #
    # Gunakan nomor chapter.
    #
    # Contoh:
    #
    # Chapter 82 -> number:82
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

            f"{chapter['data_index']}"

            f")"

        )


    # =====================================================
    # MEMBUAT PESAN DISCORD
    # =====================================================

    message = {

        # Mention akun Discord
        "content":

            f"<@{DISCORD_USER_ID}>",

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


    # =====================================================
    # KIRIM REQUEST KE DISCORD
    # =====================================================

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
            # TAMPILKAN CHAPTER TERBARU
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
            # BUAT ID CHAPTER TERBARU
            # =================================================

            latest_id = get_chapter_id(

                latest,

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

                    "State awal berhasil disimpan."

                )


                # Tidak mengirim notif
                # saat pertama kali dipantau

                continue


            # =================================================
            # AMBIL ID CHAPTER TERAKHIR
            # =================================================

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
            # CEK APAKAH ADA UPDATE
            # =================================================

            if latest_id == last_id:

                print(

                    "Tidak ada chapter baru."

                )


                # =================================================
                # PERBAIKI DATA NOMOR CHAPTER
                #
                # Ini berguna untuk state lama
                # Infinite Evolution yang sebelumnya
                # memiliki:
                #
                # "number": null
                #
                # Sekarang akan diperbaiki menjadi:
                #
                # "number": 109
                #
                # tanpa mengirim notifikasi.
                # =================================================

                if (

                    comic_state.get(
                        "number"
                    )

                    !=

                    latest.get(
                        "number"
                    )

                    or

                    comic_state.get(
                        "title"
                    )

                    !=

                    latest.get(
                        "title"
                    )

                ):

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

                        "Data state berhasil "
                        "disinkronkan."

                    )


                continue


            # =================================================
            # ADA CHAPTER BARU
            # =================================================

            print(

                "Chapter baru ditemukan!"

            )


            # =================================================
            # KIRIM NOTIFIKASI DISCORD
            # =================================================

            send_discord(

                comic_name,

                latest,

                comic_url

            )


            print(

                "Notifikasi Discord "
                "berhasil dikirim."

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
