import asyncio
import json
import os
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


# =========================================================
# KONFIGURASI
# =========================================================

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")

COMICS_FILE = "comics.json"
STATE_FILE = "state.json"


# =========================================================
# KONFIGURASI INFINITE EVOLUTION
# =========================================================

INFINITE_EVOLUTION_NAME = (
    "Infinite Evolution Starting from Zero"
)

# PATOKAN CHAPTER
#
# Berdasarkan scans kamu:
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
# Digunakan untuk Urban Dragon Reveal.
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
# USER-AGENT BERSAMA
# =========================================================

USER_AGENT = (

    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"

)


# =========================================================
# MENGAMBIL HTML MENTAH (CARA CEPAT, TANPA JS)
#
# Cocok untuk situs yang chapter list-nya di-render
# server-side (mis. www.baozimh.com).
# =========================================================

def fetch_html_static(url):

    headers = {
        "User-Agent": USER_AGENT
    }

    response = requests.get(

        url,

        headers=headers,

        timeout=30

    )

    response.raise_for_status()

    return response.text


# =========================================================
# MENGAMBIL HTML SETELAH JAVASCRIPT DIJALANKAN
#
# Dipakai sebagai fallback ketika chapter list tidak
# ditemukan di HTML mentah -- biasanya karena situs
# (mis. baozimh.org) me-load daftar chapter lewat
# JavaScript/AJAX setelah halaman dibuka, bukan lewat
# server-side render.
# =========================================================

async def fetch_html_js_async(url, wait_ms=3000):

    async with async_playwright() as p:

        browser = await p.chromium.launch(

            headless=True,

            args=[

                # Banyak situs mengecek flag ini untuk
                # mendeteksi browser yang dikendalikan
                # otomatisasi (Playwright/Selenium/dll).
                "--disable-blink-features=AutomationControlled",

            ]

        )

        try:

            context = await browser.new_context(

                user_agent=USER_AGENT,

                viewport={

                    "width": 1366,

                    "height": 900

                },

                locale="zh-TW"

            )

            # Sembunyikan navigator.webdriver, penanda paling
            # umum dipakai situs untuk mendeteksi headless
            # browser otomatis.
            await context.add_init_script(

                "Object.defineProperty(navigator, "
                "'webdriver', {get: () => undefined});"

            )

            page = await context.new_page()

            await page.goto(

                url,

                timeout=30000,

                # domcontentloaded lebih aman daripada
                # networkidle -- beberapa situs punya koneksi
                # latar belakang (analytics/ads) yang membuat
                # networkidle tidak pernah tercapai.
                wait_until="domcontentloaded"

            )

            # Tunggu spesifik sampai chapter list muncul di DOM
            try:

                await page.wait_for_selector(

                    "a.comics-chapters__item",

                    timeout=15000

                )

            except Exception:

                # Selector tidak muncul dalam waktu tunggu --
                # lanjut saja, biar tetap diambil HTML apa
                # adanya untuk keperluan debug.
                pass

            # Beri waktu tambahan jaga-jaga untuk AJAX susulan.
            await page.wait_for_timeout(wait_ms)

            html = await page.content()

        finally:

            await browser.close()

    return html


def fetch_html_js(url, wait_ms=2000):

    return asyncio.run(

        fetch_html_js_async(
            url,
            wait_ms=wait_ms
        )

    )


# =========================================================
# PARSING HTML -> DAFTAR CHAPTER
#
# Situs "baozi" ternyata punya 2 platform/struktur HTML yang
# beda total tergantung domain:
#
# 1. www.baozimh.com (Vue) -> <a class="comics-chapters__item">
# 2. baozimh.org (Astro + Alpine.js) -> <div class="chapteritem">
#    dengan data-ct = judul chapter, atau fallback ke elemen
#    #lastchap (chapter terbaru saja, tersedia tanpa JS).
#
# Dicoba berurutan; yang pertama ketemu isinya dipakai.
# =========================================================

def parse_chapters(html, url):

    soup = BeautifulSoup(

        html,

        "html.parser"

    )

    chapters = parse_chapters_style_baozimh_com(soup, url)

    if chapters:

        return chapters

    chapters = parse_chapters_style_baozimh_org(soup, url)

    if chapters:

        return chapters

    return parse_latest_chapter_lastchap(soup, url)


# =========================================================
# STRUKTUR 1: www.baozimh.com (Vue)
#
# <a class="comics-chapters__item" data-index="..." href="...">
#   judul chapter
# </a>
# =========================================================

def parse_chapters_style_baozimh_com(soup, url):

    chapter_items = soup.select(

        "a.comics-chapters__item"

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
        # Urban Dragon:
        # nomor dibaca dari judul.
        #
        # Infinite Evolution:
        # nomor dihitung khusus nanti.
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
# STRUKTUR 2: baozimh.org (Astro + Alpine.js)
#
# <div class="chapteritem" data-index="...">
#   <a href="..." data-ct="judul chapter">...</a>
# </div>
#
# Judul chapter langsung tersedia di atribut data-ct, jadi
# tidak perlu ambil dari teks elemen.
#
# Catatan: bagian ini biasanya baru terisi setelah Alpine.js
# jalan (mode JavaScript/Playwright), karena di-render lewat
# x-html.
# =========================================================

def parse_chapters_style_baozimh_org(soup, url):

    items = soup.select(

        "div.chapteritem"

    )

    chapters = []

    seen_urls = set()

    for position, div in enumerate(
        items
    ):

        link = div.find("a")

        if link is None:

            continue

        href = link.get("href")

        if not href:

            continue

        chapter_url = urljoin(
            url,
            href
        )

        # Hindari duplikat -- situs ini menampilkan 2 daftar
        # terpisah (terbaru & terlama) yang bisa saja
        # tumpang tindih.
        if chapter_url in seen_urls:

            continue

        seen_urls.add(chapter_url)

        data_index = div.get("data-index")

        try:

            data_index = int(data_index)

        except (TypeError, ValueError):

            data_index = position

        title = (

            link.get("data-ct")
            or link.get_text(" ", strip=True)

        )

        chapter_number = extract_chapter_number(title)

        chapters.append({

            "data_index": data_index,

            "number": chapter_number,

            "title": title,

            "url": chapter_url

        })

    return chapters


# =========================================================
# STRUKTUR 3 (FALLBACK): elemen #lastchap
#
# <a id="lastchap" href="...">judul chapter terbaru</a>
#
# Cuma kasih 1 chapter (yang terbaru), tapi cukup untuk
# keperluan notifikasi update. Elemen ini biasanya tersedia
# di baozimh.org bahkan tanpa menjalankan JavaScript.
# =========================================================

def parse_latest_chapter_lastchap(soup, url):

    tag = soup.find(id="lastchap")

    if tag is None:

        return []

    href = tag.get("href")

    if not href:

        return []

    chapter_url = urljoin(url, href)

    title = tag.get_text(" ", strip=True)

    chapter_number = extract_chapter_number(title)

    return [{

        "data_index": 0,

        "number": chapter_number,

        "title": title,

        "url": chapter_url

    }]


# =========================================================
# DEBUG: TELUSURI PENYEBAB SELECTOR TIDAK KETEMU
#
# Dipanggil hanya saat mode statis maupun JavaScript
# sama-sama gagal menemukan chapter list. Tidak mengubah
# behavior, cuma mencetak info tambahan ke log Actions
# supaya penyebabnya bisa dipastikan (situs berubah struktur,
# atau situsnya sendiri gagal load data / diblokir anti-bot).
# =========================================================

def debug_html_snapshot(html):

    print("  --- DEBUG: info cuplikan HTML ---")

    print(f"  Panjang HTML: {len(html)} karakter")

    error_markers = [
        "获取数据失败",
        "获取数据失敗",
        "Just a moment",
        "Attention Required",
        "captcha",
    ]

    found_markers = [
        marker
        for marker in error_markers
        if marker.lower() in html.lower()
    ]

    if found_markers:

        print(

            "  Terdeteksi penanda gagal/anti-bot di HTML: "
            f"{found_markers}"

        )

    else:

        print(

            "  Tidak ada penanda error/anti-bot yang dikenal "
            "di HTML."

        )

    soup = BeautifulSoup(html, "html.parser")

    candidate_classes = set()

    for tag in soup.find_all("a", class_=True):

        for class_name in tag.get("class", []):

            if "chapter" in class_name.lower():

                candidate_classes.add(class_name)

    if candidate_classes:

        print(

            "  Class <a> yang mengandung kata 'chapter': "
            f"{sorted(candidate_classes)}"

        )

    else:

        print(

            "  Tidak ada elemen <a> dengan class yang "
            "mengandung kata 'chapter'."

        )

    print("  --- akhir info debug ---")


# =========================================================
# MENGAMBIL SEMUA CHAPTER DARI BAOZI
#
# Coba cara cepat (HTML statis) dulu. Kalau chapter list
# tidak ditemukan (situs JS-rendered seperti baozimh.org),
# otomatis fallback ke headless browser (Playwright).
# =========================================================

def get_chapters(url):

    html = fetch_html_static(url)

    chapters = parse_chapters(html, url)

    if chapters:

        return chapters


    print(

        "  Chapter list tidak ditemukan di HTML statis, "
        "mencoba mode JavaScript (Playwright)..."

    )

    html = fetch_html_js(url)

    chapters = parse_chapters(html, url)

    if not chapters:

        debug_html_snapshot(html)

        raise Exception(

            "Tidak menemukan chapter "
            "(sudah dicoba: selector baozimh.com, "
            "selector baozimh.org, dan elemen #lastchap; "
            "mode statis maupun JavaScript)"

        )

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
    # Nomor chapter dihitung berdasarkan patokan:
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
    # Urban Dragon menggunakan nomor
    # yang diambil dari judul.
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
    # Gunakan data-index.
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
    # Gunakan nomor chapter jika tersedia.
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
# MEMBUAT DATA STATE
# =========================================================

def create_state_data(
    chapter,
    chapter_id
):

    return {

        "data_index":

            chapter[
                "data_index"
            ],

        "number":

            chapter[
                "number"
            ],

        "title":

            chapter[
                "title"
            ],

        "url":

            chapter.get(
                "url"
            ),

        "chapter_id":

            chapter_id

    }


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
    # MENGAMBIL URL CHAPTER
    # =====================================================

    chapter_url = chapter.get(
        "url"
    )


    # =====================================================
    # MEMBUAT LINK BACA
    # =====================================================

    if chapter_url:

        read_link = (

            f"[🔗 Baca "
            f"{chapter_display}]"
            f"({chapter_url})"

        )

    else:

        read_link = (

            "🔗 URL chapter tidak ditemukan"

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
                    f"{chapter['title']}\n\n"

                    f"{read_link}"

                ),

                # Jika URL chapter tersedia,
                # klik judul embed akan membuka
                # chapter langsung.

                "url":

                    chapter_url
                    if chapter_url
                    else comic_url,

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


            print(

                f"  URL: "
                f"{latest['url']}"

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
                ] = create_state_data(

                    latest,

                    latest_id

                )


                state_changed = True


                print(

                    "State awal berhasil disimpan."

                )


                # Tidak mengirim notif
                # saat pertama kali dipantau.

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
            # TIDAK ADA CHAPTER BARU
            # =================================================

            if latest_id == last_id:

                print(

                    "Tidak ada chapter baru."

                )


                # =================================================
                # PERBAIKI / SINKRONKAN STATE
                #
                # Berguna untuk state lama seperti:
                #
                # "number": null
                #
                # dan belum memiliki URL.
                #
                # Tidak mengirim notif.
                # =================================================

                new_state_data = create_state_data(

                    latest,

                    latest_id

                )


                if comic_state != new_state_data:

                    state[
                        comic_name
                    ] = new_state_data


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
            ] = create_state_data(

                latest,

                latest_id

            )


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
