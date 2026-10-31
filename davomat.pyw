"""Davomat — kunlik ish hisobotini rasm (jadval) ko'rinishida Telegram guruhga yuboruvchi Windows ilova.

- "Keldim" / "Ketdim" tugmalari — kelgan/ketgan vaqt; "Ketdim" dan keyin hisobot oynasi.
- Yuborish: Telegram Desktop orqali (kodsiz, o'z akkauntidan; guruh havolasi bo'lsa guruh o'zi ochiladi)
  yoki Telegram API (Telethon) orqali — kengaytirilgan sozlamalarda.
- Dam olish chegarasigacha "Keldim" bosilmasa — dam olish kuni: eslatma ham, xabar ham yo'q.
- "Keldim" bosilgan kuni eslatma vaqtidan boshlab hisobot yuborilmaguncha takror eslatadi.
- Oylik hisobot (Excel), uch til (o'zbek, rus, ingliz), GitHub orqali avtomatik yangilanish.

Ishga tushirish (ishlab chiqish):  .venv\\Scripts\\pythonw.exe davomat.pyw
Tarqatish:  yigish.ps1 -> dist\\Davomat.exe (birinchi ishga tushganda o'zini o'rnatadi), chiqarish.ps1 -> GitHub release.
"""
import asyncio
import ctypes
import datetime as dt
import io
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import winreg
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import pystray
from PIL import Image, ImageDraw, ImageFont
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

VERSIYA = "2.0.0"
REPO = "mjavohir06/davomat"
FROZEN = getattr(sys, "frozen", False)  # PyInstaller exe
HERE = os.path.dirname(sys.executable if FROZEN else os.path.abspath(__file__))
# exe: dastur %LOCALAPPDATA%\Programs\Davomat da, ma'lumot %APPDATA%\Davomat da (yangilanishda tegilmaydi);
# ishlab chiqish nusxasi: hammasi skript yonida
BASE = os.path.join(os.environ.get("APPDATA", HERE), "Davomat") if FROZEN else HERE
DATA = os.path.join(BASE, "malumot")
OUT = os.path.join(BASE, "hisobotlar")
SOZ_FAYL = os.path.join(DATA, "sozlamalar.json")
HOLAT_FAYL = os.path.join(DATA, "holat.json")
SESSION = os.path.join(DATA, "telegram")
INSTALL_DIR = os.path.join(os.environ.get("LOCALAPPDATA", HERE), "Programs", "Davomat")
INSTALL_EXE = os.path.join(INSTALL_DIR, "Davomat.exe")
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Davomat"
PORT = 47631  # bitta nusxa: ikkinchi nusxa birinchisiga "ochil" (yoki "chiqish") deydi
ISH_SONI = 10  # jadvalda 10 ta ish qatori
YASHIL = "#107c41"
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW

STANDART = {
    "til": "uz", "ism": "", "guruh_havola": "",
    "api_id": "", "api_hash": "", "telefon": "", "chat_id": None, "chat_nomi": "",
    "ish_boshi": "09:00", "eslatma": "17:45", "takror_daq": 15, "dam_chegara": "18:00",
    "fayl_nomi": "Xisobot kunlik {sana}.xlsx", "izoh": "",  # izoh bo'sh — tanlangan tildagi standart matn
}

# ------------------------------------------------------------------ tillar
TIL = "uz"
TILLAR = {"uz": "O'zbekcha", "ru": "Русский", "en": "English"}
TR = {}  # o'zbekcha matn -> (ruscha, inglizcha); fayl oxirida to'ldiriladi


def T(s, **kw):
    """Tarjima: kalit — o'zbekcha matn. kw berilsa .format(**kw)."""
    if TIL != "uz" and s in TR:
        s = TR[s][0 if TIL == "ru" else 1]
    return s.format(**kw) if kw else s


HAFTA = {
    "uz": ["dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba"],
    "ru": ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}
HAFTA_QISQA = {
    "uz": ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"],
    "ru": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}
OYLAR = {
    "uz": ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr",
           "dekabr"],
    "ru": ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь",
           "декабрь"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"],
}


def oy_nomi(oy):
    """'2026-10' -> 'oktabr 2026'."""
    y, m = oy.split("-")
    return f"{OYLAR[TIL][int(m) - 1]} {y}"


# ------------------------------------------------------------------ yordamchilar
def oqi(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def yoz(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(path + ".tmp", path)


def bugun():
    return dt.date.today().isoformat()


def hm(t):
    return t.strftime("%H:%M")


def vaqt_ol(s):
    """'9:05' / '09.05' / '0905' -> datetime.time yoki None."""
    s = str(s).strip().replace(".", ":").replace(" ", "")
    if s.isdigit() and len(s) in (3, 4):
        s = s[:-2] + ":" + s[-2:]
    try:
        h, m = s.split(":")
        return dt.time(int(h), int(m))
    except ValueError:
        return None


def daqiqa(s):
    t = vaqt_ol(s)
    return t.hour * 60 + t.minute if t else None


def soat_daq(m):
    """Daqiqa -> 'S:DD'."""
    return "—" if m is None else f"{m // 60}:{m % 60:02d}"


def telefon_ol(s):
    """'90 123-45-67' / '998901234567' / '+998 (90) 123 45 67' -> '+998901234567'."""
    raqam = "".join(ch for ch in s if ch.isdigit())
    if len(raqam) == 9:  # operator kodi bilan, 998 siz
        raqam = "998" + raqam
    return "+" + raqam if raqam else ""


def tg_havola(s):
    """Foydalanuvchi kiritgan guruh havolasi -> Telegram Desktop ochadigan tg:// havola yoki None.
    t.me/+XXXX, t.me/joinchat/XXXX (taklif), t.me/c/123/45 (xabar havolasi), t.me/username, tg://..."""
    s = (s or "").strip()
    if s.startswith("tg://"):
        return s
    m = re.match(r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(.+)", s)
    if not m:
        return None
    q = [x for x in m.group(1).split("?")[0].split("/") if x]
    if not q:
        return None
    if q[0].startswith("+") and len(q[0]) > 1:
        return "tg://join?invite=" + q[0][1:]
    if q[0] == "joinchat" and len(q) > 1:
        return "tg://join?invite=" + q[1]
    if q[0] == "c" and len(q) > 1 and q[1].isdigit():
        post = q[-1] if len(q) > 2 and q[-1].isdigit() else "1"
        return f"tg://privatepost?channel={q[1]}&post={post}"
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,}", q[0]):
        return f"tg://resolve?domain={q[0]}" + (f"&post={q[1]}" if len(q) > 1 and q[1].isdigit() else "")
    return None


FONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


def rasm_yasa(sana, kelgan, ketgan, ishlar, path, ism=""):
    """Hisobot jadvalini PNG rasmga chizish. sana: datetime.date."""
    k = 2  # tiniq bo'lishi uchun ikki barobar o'lchamda chiziladi
    f = lambda nom, o: ImageFont.truetype(os.path.join(FONTS, nom), o * k)  # noqa: E731
    oddiy, qalin, sarlavha = f("calibri.ttf", 20), f("calibrib.ttf", 20), f("calibrib.ttf", 26)
    W1, W2, W3 = 56 * k, 520 * k, 150 * k  # raqam | ish / yozuv | vaqt
    PAD, QATOR = 24 * k, 40 * k
    eni = PAD * 2 + W1 + W2 + W3
    olcham = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    def bolib(matn, en):  # uzun ishni bir necha qatorga bo'lish
        qatorlar, joriy = [], ""
        for soz in matn.split():
            sinov = f"{joriy} {soz}".strip()
            if olcham.textlength(sinov, font=oddiy) <= en or not joriy:
                joriy = sinov
            else:
                qatorlar.append(joriy)
                joriy = soz
        return qatorlar + [joriy] if joriy else [""]

    ishlar = list(ishlar)[:ISH_SONI] + [""] * (ISH_SONI - len(ishlar))
    ish_qatorlari = [bolib(x, W2 + W3 - 24 * k) for x in ishlar]
    balandliklar = [QATOR] + [max(QATOR, len(q) * 26 * k + 14 * k) for q in ish_qatorlari] + [QATOR]
    tepa = PAD + 50 * k + (32 * k if ism else 0)
    boyi = tepa + sum(balandliklar) + PAD
    im = Image.new("RGB", (eni, boyi), "white")
    d = ImageDraw.Draw(im)
    d.text((PAD, PAD), T("Kunlik hisobot — {sana} ({kun})", sana=f"{sana:%d.%m.%Y}", kun=HAFTA[TIL][sana.weekday()]),
           font=sarlavha, fill=(16, 124, 65))
    if ism:
        d.text((PAD, PAD + 38 * k), T("Xodim: {ism}", ism=ism), font=qalin, fill=(40, 40, 40))

    x0, x1, x2, x3 = PAD, PAD + W1, PAD + W1 + W2, PAD + W1 + W2 + W3
    CHIZIQ, BOSH = (90, 90, 90), (226, 239, 218)
    y = tepa

    def vaqt_qatori(y, h, nom, vaqt):
        d.rectangle((x0, y, x3, y + h), fill=BOSH)
        d.text(((x1 + x2) / 2, y + h / 2), nom, font=qalin, fill="black", anchor="mm")
        d.text(((x2 + x3) / 2, y + h / 2), hm(vaqt) if vaqt else "", font=qalin, fill="black", anchor="mm")
        for x in (x0, x1, x2, x3):
            d.line((x, y, x, y + h), fill=CHIZIQ, width=k)

    vaqt_qatori(y, balandliklar[0], T("Ishga kelgan vaqtim"), kelgan)
    y += balandliklar[0]
    for i, qatorlar in enumerate(ish_qatorlari):
        h = balandliklar[i + 1]
        d.line((x0, y, x3, y), fill=CHIZIQ, width=k)
        d.text(((x0 + x1) / 2, y + h / 2), str(i + 1), font=oddiy, fill="black", anchor="mm")
        ty = y + h / 2 - (len(qatorlar) - 1) * 13 * k  # qatorlar markazi
        for q in qatorlar:
            d.text((x1 + 12 * k, ty), q, font=oddiy, fill="black", anchor="lm")
            ty += 26 * k
        for x in (x0, x1, x3):
            d.line((x, y, x, y + h), fill=CHIZIQ, width=k)
        y += h
    d.line((x0, y, x3, y), fill=CHIZIQ, width=k)
    vaqt_qatori(y, balandliklar[-1], T("Ishdan ketgan vaqtim"), ketgan)
    d.rectangle((x0, tepa, x3, y + balandliklar[-1]), outline=(40, 40, 40), width=2 * k)
    d.line((x0, y, x3, y), fill=CHIZIQ, width=k)
    im = im.resize((eni // k, boyi // k), Image.LANCZOS)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path)
    return path


def _norm(s):
    return s.lower().replace("ʻ", "'").replace("‘", "'").replace("’", "'").replace("`", "'").replace("ʼ", "'")


def avto_toldir(entry, manba, soni=8):
    """Qidiruv kabi: yozilgan so'z bo'laklarining hammasi bor ishlar ostida chiqadi (tartibi muhim emas).
    ↑/↓ — tanlash, Enter/Tab yoki sichqoncha — qo'yish, Esc — yopish."""
    holat = {"oyna": None, "lb": None, "topilgan": []}

    def yop(_=None):
        if holat["oyna"]:
            holat["oyna"].destroy()
            holat["oyna"] = None

    def qoy(i):
        if 0 <= i < len(holat["topilgan"]):
            entry.delete(0, "end")
            entry.insert(0, holat["topilgan"][i])
            entry.icursor("end")
        yop()

    def yangila():
        matn = _norm(entry.get().strip())
        bolaklar = matn.split()
        if not bolaklar:
            return yop()
        topilgan = [x for x in manba() if all(b in _norm(x) for b in bolaklar) and _norm(x) != matn]
        topilgan.sort(key=lambda x: (not _norm(x).startswith(bolaklar[0]), len(x)))
        holat["topilgan"] = topilgan = topilgan[:soni]
        if not topilgan:
            return yop()
        if not holat["oyna"]:
            o = holat["oyna"] = tk.Toplevel(entry)
            o.overrideredirect(True)
            o.attributes("-topmost", True)
            lb = holat["lb"] = tk.Listbox(o, font=("Segoe UI", 10), activestyle="none", relief="solid", bd=1,
                                          selectbackground="#107c41", exportselection=False)
            lb.pack(fill="both", expand=True)
            lb.bind("<ButtonRelease-1>", lambda e: qoy(lb.nearest(e.y)))
        lb = holat["lb"]
        lb.delete(0, "end")
        for x in topilgan:
            lb.insert("end", x)
        lb.config(height=len(topilgan))
        lb.selection_set(0)
        holat["oyna"].geometry(f"{entry.winfo_width()}x{len(topilgan) * 22 + 4}"
                               f"+{entry.winfo_rootx()}+{entry.winfo_rooty() + entry.winfo_height()}")

    def tugma(e):
        if e.keysym in ("Down", "Up"):
            if not holat["oyna"]:
                return None  # qidiruv ro'yxati yo'q — combobox o'z ochiluvchi ro'yxatini ochsin
            lb = holat["lb"]
            sel = lb.curselection()
            i = (sel[0] if sel else -1) + (1 if e.keysym == "Down" else -1)
            i = max(0, min(i, lb.size() - 1))
            lb.selection_clear(0, "end")
            lb.selection_set(i)
            lb.see(i)
            return "break"
        if e.keysym in ("Return", "Tab") and holat["oyna"]:
            sel = holat["lb"].curselection()
            qoy(sel[0] if sel else 0)
            return "break" if e.keysym == "Return" else None
        if e.keysym == "Escape":
            yop()
            return "break"
        return None

    def yozildi(e):
        if e.keysym not in ("Down", "Up", "Return", "Tab", "Escape", "Shift_L", "Shift_R", "Control_L", "Control_R"):
            yangila()

    entry.bind("<KeyPress>", tugma)
    entry.bind("<KeyRelease>", yozildi)
    entry.bind("<FocusOut>", lambda e: entry.after(200, yop))  # sichqoncha bilan bosishga ulgursin
    entry.winfo_toplevel().bind("<Configure>", lambda e: yop() if e.widget is entry.winfo_toplevel() else None,
                                add="+")  # oyna surilsa yopiladi


def _clipboard(formatlar):
    """Windows clipboardga [(format, bytes), ...] yozadi (oldingisi o'chadi)."""
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    k32.GlobalAlloc.restype = ctypes.c_void_p
    k32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u32.SetClipboardData.restype = ctypes.c_void_p
    u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    u32.OpenClipboard.argtypes = [ctypes.c_void_p]
    for _ in range(20):
        if u32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        raise OSError("boshqa dastur clipboardni ushlab turibdi")
    try:
        u32.EmptyClipboard()
        for fmt, data in formatlar:
            h = k32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
            ctypes.memmove(k32.GlobalLock(h), data, len(data))
            k32.GlobalUnlock(h)
            if not u32.SetClipboardData(fmt, h):
                raise OSError("SetClipboardData bajarilmadi")
    finally:
        u32.CloseClipboard()


def clipboard_matn(s):
    _clipboard([(13, (s + "\0").encode("utf-16-le"))])  # CF_UNICODETEXT


def clipboard_rasm(path):
    b = io.BytesIO()
    Image.open(path).convert("RGB").save(b, "BMP")
    with open(path, "rb") as f:
        png = f.read()
    _clipboard([(8, b.getvalue()[14:]),  # CF_DIB (BMP fayl sarlavhasisiz)
                (ctypes.windll.user32.RegisterClipboardFormatW("PNG"), png)])


def telegram_exe():
    """Telegram Desktop yo'li: odatiy joy, bo'lmasa tg:// havolasi ro'yxatdagi dastur."""
    p = os.path.expandvars(r"%APPDATA%\Telegram Desktop\Telegram.exe")
    if os.path.exists(p):
        return p
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"tg\shell\open\command") as kl:
            cmd = winreg.QueryValue(kl, None)
        p = cmd.split('"')[1] if cmd.startswith('"') else cmd.split()[0]
        if os.path.exists(p):
            return p
    except (OSError, IndexError):
        pass
    return None


def _telegram_oynasi():
    """Telegram.exe ning ko'rinadigan asosiy oynasi (hwnd) yoki None."""
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_wchar_p,
                                               ctypes.POINTER(ctypes.c_uint)]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    topildi = []

    def tgmi(hwnd):
        pid = ctypes.c_uint()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = k32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            buf, n = ctypes.create_unicode_buffer(520), ctypes.c_uint(520)
            k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
            return buf.value.lower().endswith("\\telegram.exe")
        finally:
            k32.CloseHandle(h)

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def har_biri(hwnd, _):
        if u32.IsWindowVisible(hwnd) and u32.GetWindowTextLengthW(hwnd) and not u32.GetWindow(hwnd, 4) \
                and tgmi(hwnd):  # GW_OWNER yo'q — asosiy oyna
            topildi.append(hwnd)
            return False
        return True
    u32.EnumWindows(har_biri, None)
    return topildi[0] if topildi else None


def _uia():
    import comtypes.client
    try:
        from comtypes.gen import UIAutomationClient as U
    except ImportError:
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient as U
    return U, comtypes.client.CreateObject(U.CUIAutomation, interface=U.IUIAutomation)


# Telegram yuborish oynasidagi «hujjat sifatida» / «siqish» belgilari (til nomiga qarab)
_HUJJAT_SOZLARI = ("document", "file", "документ", "файл", "hujjat", "fayl")
_SIQISH_SOZLARI = ("compress", "сжат", "siq")


def telegramga_joyla(path, izoh, oyna, havola=None):
    """Telegram Desktop'ga rasmni izoh bilan yuboradi (UI Automation, har qadam tekshiriladi; Telegram tili muhim emas).
    havola berilsa: ochiq chat yopiladi, guruh havola orqali ochiladi — xabar maydoni faqat havola ishlasa paydo bo'ladi,
    shuning uchun noto'g'ri chatga ketmaydi. havola yo'q bo'lsa — foydalanuvchi ochib qo'ygan chatga.
    Keyin: xabar maydoniga fokus -> rasm Ctrl+V -> «rasm yuborish» oynasi -> izoh -> «hujjat» belgisi o'chiq -> Send."""
    import comtypes
    U, uia = _uia()
    u32 = ctypes.windll.user32
    u32.GetForegroundWindow.restype = ctypes.c_void_p
    u32.GetAncestor.restype = ctypes.c_void_p
    u32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    u32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
    u32.IsIconic.argtypes = [ctypes.c_void_p]
    u32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    CTRL, A, V, ESC = 0x11, 0x41, 0x56, 0x1B

    def kut(s):
        oxiri = time.time() + s
        while time.time() < oxiri:
            oyna.update()
            time.sleep(0.03)

    hwnd = _telegram_oynasi()
    if not hwnd and havola:
        os.startfile(havola)  # Telegram yopiq bo'lsa ham ochadi
        for _i in range(50):
            kut(0.2)
            hwnd = _telegram_oynasi()
            if hwnd:
                break
        kut(2)
    if not hwnd:
        raise RuntimeError(T("Telegram oynasi topilmadi — Telegram Desktop'ni oching."))
    root = uia.ElementFromHandle(ctypes.c_void_p(hwnd))

    def top(cls, ota=None, nom=None):
        c = uia.CreatePropertyCondition(U.UIA_ClassNamePropertyId, "class " + cls)
        if nom:
            c = uia.CreateAndCondition(c, uia.CreatePropertyCondition(U.UIA_NamePropertyId, nom))
        try:
            e = (ota or root).FindFirst(U.TreeScope_Descendants, c)
            e.CurrentName  # NULL bo'lsa xato beradi
            return e
        except (ValueError, comtypes.COMError):
            return None

    def hammasi(cls, ota):
        c = uia.CreatePropertyCondition(U.UIA_ClassNamePropertyId, "class " + cls)
        els = ota.FindAll(U.TreeScope_Descendants, c)
        return [els.GetElement(i) for i in range(els.Length)]

    def maydon_ol():
        """Ochiq chatning xabar maydoni (ko'rinib turgan bo'lsa)."""
        tarix = top("HistoryWidget")
        m = tarix and top("Ui::InputField::Inner", tarix)
        if not m or m.CurrentIsOffscreen:
            return None
        r = m.CurrentBoundingRectangle
        return m if r.right > r.left else None

    def faolmi():
        return u32.GetAncestor(u32.GetForegroundWindow(), 3) == hwnd  # GA_ROOTOWNER

    def faol():
        if not faolmi():
            raise RuntimeError(T("Telegram oynasi faol emas — hech narsa yuborilmadi."))

    def oldinga():
        if u32.IsIconic(hwnd):
            u32.ShowWindow(hwnd, 9)  # SW_RESTORE
        u32.SetForegroundWindow(hwnd)
        kut(0.3)
        if not faolmi():  # Windows fokus o'g'irlashni cheklaydi — Alt bosib turilganda ruxsat beradi
            u32.keybd_event(0x12, 0, 0, 0)
            u32.SetForegroundWindow(hwnd)
            u32.keybd_event(0x12, 0, 2, 0)
            kut(0.4)
        faol()

    def bos(*vk):
        faol()
        for k in vk:
            u32.keybd_event(k, 0, 0, 0)
        for k in reversed(vk):
            u32.keybd_event(k, 0, 2, 0)  # KEYEVENTF_KEYUP

    def bosish(e):
        e.GetCurrentPattern(U.UIA_InvokePatternId).QueryInterface(U.IUIAutomationInvokePattern).Invoke()

    def qiymat(e):
        return e.GetCurrentPattern(U.UIA_ValuePatternId).QueryInterface(U.IUIAutomationValuePattern).CurrentValue

    oldinga()
    if top("Ui::BoxLayerWidget"):
        raise RuntimeError(T("Telegram'da boshqa oyna ochiq turibdi — avval uni yoping."))

    if havola:
        # 1) ochiq chatni yopamiz: keyin paydo bo'lgan xabar maydoni aniq havoladagi guruhniki bo'ladi
        for _i in range(3):
            m = maydon_ol()
            if not m:
                break
            m.SetFocus()
            kut(0.15)
            bos(ESC)
            kut(0.5)
        if maydon_ol():  # tor oynada — «orqaga» tugmasi (yuqori panelning eng chap tugmasi)
            tb = top("HistoryView::TopBarWidget")
            if tb:
                chap = tb.CurrentBoundingRectangle.left
                for b in hammasi("Ui::IconButton", tb):
                    if abs(b.CurrentBoundingRectangle.left - chap) < 6:
                        bosish(b)
                        kut(0.5)
                        break
        if maydon_ol():
            raise RuntimeError(T("Ochiq chatni yopib bo'lmadi — hech narsa yuborilmadi."))
        # 2) guruhni havola orqali ochamiz
        os.startfile(havola)
        for _i in range(40):
            kut(0.2)
            if maydon_ol() or top("Ui::BoxLayerWidget"):
                break
        if top("Ui::BoxLayerWidget") or not maydon_ol():
            if top("Ui::BoxLayerWidget") and faolmi():
                bos(ESC)
            raise RuntimeError(T("Guruh havola orqali ochilmadi (havola eskirgan yoki guruhga a'zo emassiz). "
                                 "Hech narsa yuborilmadi — Sozlamalardagi guruh havolasini tekshiring."))
        kut(0.5)
        oldinga()

    maydon = maydon_ol()
    if not maydon:
        raise RuntimeError(T("Telegram'da chat ochilmagan — hisobot guruhini ochib, qayta bosing."))
    maydon.SetFocus()
    kut(0.2)
    if not maydon.CurrentHasKeyboardFocus:
        raise RuntimeError(T("Xabar maydoniga fokus o'tmadi — hech narsa yuborilmadi."))

    clipboard_rasm(path)
    bos(CTRL, V)
    box = None
    for _i in range(40):  # 4 s gacha
        kut(0.1)
        box = top("SendFilesBox")
        if box:
            break
    if not box:
        raise RuntimeError(T("Rasm yuborish oynasi chiqmadi — hech narsa yuborilmadi."))
    kut(0.3)
    try:
        izoh_m = top("Ui::InputField::Inner", box)
        if not izoh_m:
            raise RuntimeError(T("Izoh maydoni topilmadi."))
        izoh_m.SetFocus()
        kut(0.15)
        clipboard_matn(izoh)
        bos(CTRL, A)  # chatdagi qoralama izohga o'tgan bo'lsa — almashtiriladi
        bos(CTRL, V)
        kut(0.3)
        yozilgan = qiymat(izoh_m)
        if yozilgan.strip() != izoh.strip():
            raise RuntimeError(T("Izoh to'g'ri yozilmadi: «{q}».", q=yozilgan))
        qatlam = top("Ui::BoxLayerWidget") or root  # tugmalar SendFilesBox emas, qatlam ichida
        for cb in hammasi("Ui::Checkbox", qatlam):  # rasm siqilgan holda (oddiy rasm) ketsin
            nom = cb.CurrentName.lower()
            kerak = 0 if any(s in nom for s in _HUJJAT_SOZLARI) else 1 if any(s in nom for s in _SIQISH_SOZLARI) else None
            if kerak is None:
                continue
            tg = cb.GetCurrentPattern(U.UIA_TogglePatternId).QueryInterface(U.IUIAutomationTogglePattern)
            if tg.CurrentToggleState != kerak:
                tg.Toggle()
                kut(0.2)
        tugmalar = hammasi("Ui::RoundButton", qatlam)  # Add | Cancel | Send — Send eng o'ngda
        if not tugmalar:
            raise RuntimeError(T("«Yuborish» tugmasi topilmadi."))
        send = max(tugmalar, key=lambda b: (b.CurrentBoundingRectangle.right, b.CurrentBoundingRectangle.bottom))
        faol()
        bosish(send)
    except Exception:
        if top("SendFilesBox") and faolmi():
            bos(ESC)  # bekor
        raise
    for _i in range(30):
        kut(0.1)
        if not top("SendFilesBox"):
            return
    raise RuntimeError(T("Yuborish oynasi yopilmadi — Telegram'ni tekshiring."))


# ------------------------------------------------------------------ oylik hisobot
def oy_hisobi(kunlar, oy, ish_boshi):
    """oy: '2026-10'. -> (qatorlar, jami) — faqat «Keldim» bosilgan kunlar."""
    boshi = daqiqa(ish_boshi) or 9 * 60
    qatorlar = []
    for sana in sorted(x for x in kunlar if x.startswith(oy)):
        k = kunlar[sana]
        kel, ket = daqiqa(k.get("keldi", "")), daqiqa(k.get("ketdi", ""))
        if kel is None:
            continue
        qatorlar.append({
            "sana": dt.date.fromisoformat(sana), "keldi": k["keldi"], "ketdi": k.get("ketdi", ""),
            "ishladi": ket - kel if ket is not None and ket > kel else None,
            "kech": max(0, kel - boshi), "yuborildi": k.get("yuborildi", ""), "ishlar": k.get("ishlar", []),
        })
    ishlagan = [q["ishladi"] for q in qatorlar if q["ishladi"] is not None]
    jami = {
        "kunlar": len(qatorlar), "jami": sum(ishlagan),
        "ortacha": sum(ishlagan) // len(ishlagan) if ishlagan else None,
        "kech_kun": sum(1 for q in qatorlar if q["kech"]), "kech_jami": sum(q["kech"] for q in qatorlar),
        "yuborilmagan": sum(1 for q in qatorlar if not q["yuborildi"]),
    }
    return qatorlar, jami


def oylik_xlsx(kunlar, oy, ism, ish_boshi, path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    qatorlar, jami = oy_hisobi(kunlar, oy, ish_boshi)
    wb = Workbook()
    ws = wb.active
    ws.title = oy
    ws["A1"] = T("Oylik davomat — {oy}", oy=oy_nomi(oy))
    ws["A1"].font = Font(bold=True, size=14, color="107C41")
    ws["A2"] = T("Xodim: {ism}", ism=ism or "—")
    ws["A3"] = T("Ish boshlanishi: {v}", v=ish_boshi)
    sarlavha = [T("Sana"), T("Kun"), T("Keldi"), T("Ketdi"), T("Ishlagan vaqt"), T("Kechikish (daq)"),
                T("Hisobot yuborildi"), T("Bajarilgan ishlar")]
    ws.append([])
    ws.append(sarlavha)
    bosh = ws.max_row
    ingichka = Side(style="thin", color="999999")
    chegara = Border(left=ingichka, right=ingichka, top=ingichka, bottom=ingichka)
    for c in ws[bosh]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="E2EFDA")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = chegara
    for q in qatorlar:
        ws.append([q["sana"], HAFTA_QISQA[TIL][q["sana"].weekday()], q["keldi"], q["ketdi"] or "—",
                   soat_daq(q["ishladi"]), q["kech"] or "", q["yuborildi"] or "—", "; ".join(q["ishlar"])])
        r = ws.max_row
        ws.cell(r, 1).number_format = "DD.MM.YYYY"
        for c in ws[r]:
            c.border = chegara
            c.alignment = Alignment(vertical="top", wrap_text=c.column == 8,
                                    horizontal="left" if c.column == 8 else "center")
        if q["kech"]:
            ws.cell(r, 6).font = Font(color="C42B1C")
    ws.append([])
    for nom, qiymat in ((T("Ish kunlari"), jami["kunlar"]), (T("Jami ishlagan vaqt"), soat_daq(jami["jami"])),
                        (T("O'rtacha kunlik"), soat_daq(jami["ortacha"])), (T("Kech qolgan kunlar"), jami["kech_kun"]),
                        (T("Jami kechikish (daq)"), jami["kech_jami"]),
                        (T("Hisobot yuborilmagan kunlar"), jami["yuborilmagan"])):
        ws.append([nom, None, None, None, qiymat])
        ws.cell(ws.max_row, 1).font = Font(bold=True)
        ws.cell(ws.max_row, 5).alignment = Alignment(horizontal="center")
    for col, en in zip("ABCDEFGH", (12, 6, 8, 8, 13, 13, 15, 70)):
        ws.column_dimensions[col].width = en
    ws.freeze_panes = ws.cell(bosh + 1, 1)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb.save(path)
    return path


# ------------------------------------------------------------------ bitta nusxa, o'rnatish, yangilanish
def boshqasiga(xabar=b"panel"):
    """Ishlab turgan nusxaga xabar yuborish. Nusxa yo'q bo'lsa False."""
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=1) as s:
            s.sendall(xabar)
        return True
    except OSError:
        return False


def port_bandmi():
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", PORT))
        return False
    except OSError:
        return True
    finally:
        s.close()


def boshqasi_yopilsin(soniya=15):
    """Ishlab turgan nusxani yopib, port bo'shashini kutadi."""
    if port_bandmi():
        boshqasiga(b"chiqish")
        oxiri = time.time() + soniya
        while port_bandmi() and time.time() < oxiri:
            time.sleep(0.3)
        time.sleep(1.5)  # jarayon to'liq chiqib, exe fayli bo'shasin


def _papka(csidl):
    buf = ctypes.create_unicode_buffer(520)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
    return buf.value


YORLIQLAR = (0x10, 0x07, 0x02)  # ish stoli, Startup (avtoyuklash), Start menyu


def yorliqlar_yarat(exe):
    lnklar = "|".join(os.path.join(_papka(c), "Davomat.lnk") for c in YORLIQLAR)
    ps = ("$sh=New-Object -ComObject WScript.Shell; foreach($l in $env:DAV_LNK.Split('|')){"
          "$s=$sh.CreateShortcut($l); $s.TargetPath=$env:DAV_EXE; $s.WorkingDirectory=(Split-Path $env:DAV_EXE);"
          "$s.Description='Davomat'; $s.Save()}")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], timeout=60,
                   env={**os.environ, "DAV_LNK": lnklar, "DAV_EXE": exe}, creationflags=NO_WINDOW, check=True)


def royxatga_yoz(exe):
    """«Ilovalar va xususiyatlar» ro'yxatida ko'rinsin (o'chirish shu yerdan ham bo'ladi)."""
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
        for nom, q in (("DisplayName", "Davomat"), ("DisplayVersion", VERSIYA), ("Publisher", "mjavohir06"),
                       ("DisplayIcon", exe), ("InstallLocation", os.path.dirname(exe)),
                       ("UninstallString", f'"{exe}" --ochirish')):
            winreg.SetValueEx(k, nom, 0, winreg.REG_SZ, q)
        for nom in ("NoModify", "NoRepair"):
            winreg.SetValueEx(k, nom, 0, winreg.REG_DWORD, 1)


def _til_yukla():
    global TIL
    TIL = oqi(SOZ_FAYL, {}).get("til", "uz")
    if TIL not in TILLAR:
        TIL = "uz"


def ornatish():
    """Yuklab olingan Davomat.exe birinchi marta ochilganda: %LOCALAPPDATA%\\Programs\\Davomat ga ko'chiradi,
    yorliqlar (ish stoli, avtoyuklash, Start) va «Ilovalar» ro'yxatiga yozadi, o'rnatilganini ishga tushiradi."""
    _til_yukla()
    r = tk.Tk()
    r.withdraw()
    try:
        boshqasi_yopilsin()
        os.makedirs(INSTALL_DIR, exist_ok=True)
        if os.path.exists(INSTALL_EXE):
            eski = INSTALL_EXE[:-4] + ".old.exe"
            try:
                os.remove(eski)
            except OSError:
                pass
            try:
                os.remove(INSTALL_EXE)
            except PermissionError:
                os.replace(INSTALL_EXE, eski)  # band bo'lsa — nomini o'zgartirib bo'ladi
        shutil.copy2(sys.executable, INSTALL_EXE)
        royxatga_yoz(INSTALL_EXE)
        yorliqlar_yarat(INSTALL_EXE)
    except Exception as e:  # noqa: BLE001
        messagebox.showerror("Davomat", T("O'rnatib bo'lmadi:\n{e}", e=e))
        return
    messagebox.showinfo("Davomat", T("Davomat {v} o'rnatildi.\n\nIsh stolida «Davomat» yorlig'i paydo bo'ldi, "
                                     "kompyuter yonganda o'zi ishga tushadi.\nYuklab olingan faylni endi "
                                     "o'chirib tashlashingiz mumkin.", v=VERSIYA))
    subprocess.Popen([INSTALL_EXE, "--kut"], cwd=INSTALL_DIR)


def ochirish():
    """Davomat.exe --ochirish («Ilovalar» ro'yxatidan yoki Sozlamalardan)."""
    _til_yukla()
    r = tk.Tk()
    r.withdraw()
    if not messagebox.askyesno("Davomat", T("Davomat ilovasini kompyuterdan o'chiraymi?")):
        return
    boshqasi_yopilsin()
    for c in YORLIQLAR:
        try:
            os.remove(os.path.join(_papka(c), "Davomat.lnk"))
        except OSError:
            pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        pass
    if os.path.isdir(BASE) and messagebox.askyesno(
            "Davomat", T("Sozlamalar, davomat tarixi va hisobot rasmlari ham o'chirilsinmi?\n\n{p}", p=BASE)):
        shutil.rmtree(BASE, ignore_errors=True)
    messagebox.showinfo("Davomat", T("Davomat o'chirildi."))
    # dastur papkasini o'zimiz yopilgandan keyin o'chiradi
    subprocess.Popen(f'cmd /c ping 127.0.0.1 -n 4 >nul & rmdir /s /q "{INSTALL_DIR}"', cwd=os.environ.get("TEMP", "C:\\"),
                     creationflags=NO_WINDOW | 0x00000008)  # DETACHED_PROCESS


def _versiya(t):
    return tuple(int(x) for x in re.findall(r"\d+", t)[:3])


def yangilanish_ol():
    """GitHub'dagi oxirgi reliz -> (teg, exe_url, izoh)."""
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/latest",
                                 headers={"User-Agent": "Davomat", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.load(r)
    url = next((a["browser_download_url"] for a in d.get("assets", []) if a["name"].lower().endswith(".exe")), None)
    return d["tag_name"], url, d.get("body") or ""


def tray_korinsin():
    """Soat yonidagi belgi «^» ichiga yashirinmasin (Windows 11: belgi kamida bir marta chiqqan bo'lishi kerak)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\NotifyIconSettings") as k:
            i = 0
            while True:
                try:
                    nom = winreg.EnumKey(k, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(k, nom, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as s:
                        p = winreg.QueryValueEx(s, "ExecutablePath")[0].lower()
                        if p == sys.executable.lower() or (FROZEN and p.endswith("\\davomat\\davomat.exe")):
                            try:
                                if winreg.QueryValueEx(s, "IsPromoted")[0] == 1:
                                    continue
                            except OSError:
                                pass
                            winreg.SetValueEx(s, "IsPromoted", 0, winreg.REG_DWORD, 1)
                except OSError:
                    continue
    except OSError:
        pass


class Telegram:
    """Telethon alohida ipda (asyncio); tk ipidan `run()` bilan chaqiriladi."""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        self.client = None
        self.key = None

    def run(self, coro, timeout=120):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    def mijoz(self, soz):
        key = (str(soz["api_id"]), soz["api_hash"])
        if self.client is None or self.key != key:
            async def yarat():
                if self.client:
                    await self.client.disconnect()
                c = TelegramClient(SESSION, int(soz["api_id"]), soz["api_hash"],
                                   device_model="Davomat (Windows)", app_version=VERSIYA)
                await c.connect()
                return c
            self.client = self.run(yarat())
            self.key = key
        elif not self.client.is_connected():
            # kompyuter uxlagan / internet uzilgan — Telethon taslim bo'lgan, qayta ulanamiz
            self.run(self.client.connect())
        return self.client

    def ishla(self, soz, fabrika, timeout=120):
        """`fabrika(c)` korutinasini bajaradi; ulanish uzilgan bo'lsa qayta ulanib yana bir marta urinadi."""
        c = self.mijoz(soz)
        try:
            return self.run(fabrika(c), timeout)
        except ConnectionError:
            async def qayta():
                try:
                    await c.disconnect()
                except Exception:
                    pass
                await c.connect()
            self.run(qayta())
            return self.run(fabrika(c), timeout)

    def kirganmi(self, soz):
        return self.ishla(soz, lambda c: c.is_user_authorized())

    def guruhlar(self, soz):
        async def ol(c):
            return [(d.id, d.name) for d in await c.get_dialogs(limit=300) if d.is_group or d.is_channel]
        return self.ishla(soz, ol)

    def yubor(self, soz, path, izoh):
        async def yub(c):
            try:
                chat = await c.get_input_entity(soz["chat_id"])
            except ValueError:  # sessiyada yo'q — suhbatlar ro'yxatini yangilab qayta
                await c.get_dialogs(limit=300)
                chat = await c.get_input_entity(soz["chat_id"])
            await c.send_file(chat, path, caption=izoh)  # rasm sifatida
        self.ishla(soz, yub, timeout=300)


class Ilova:
    def __init__(self):
        global TIL
        os.makedirs(DATA, exist_ok=True)
        self.soz = {**STANDART, **oqi(SOZ_FAYL, {})}
        TIL = self.soz["til"] if self.soz["til"] in TILLAR else "uz"
        self.holat = oqi(HOLAT_FAYL, {"kunlar": {}, "ishlar_tarixi": []})
        self.holat.setdefault("kunlar", {})
        self.holat.setdefault("ishlar_tarixi", [])
        self._kochir()
        self.tg = Telegram()
        self.q = queue.Queue()
        self.keyingi_eslatma = None
        self.keyingi_yangilanish = dt.datetime.now() + dt.timedelta(seconds=20)
        self.yangilanish_soralgan = None  # shu sessiyada rad etilgan versiya qayta so'ralmaydi
        self.hisobot_oyna = self.soz_oyna = self.panel_oyna = self.royxat_oyna = None
        self.oylik_oyna = self.tanishuv_oyna = None

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("Davomat")
        self.ikonka_rasm = self._ikonka()
        self.root.iconphoto(True, tk.PhotoImage(data=self._png(self.ikonka_rasm.resize((32, 32)))))
        st = ttk.Style()
        st.configure("Katta.TButton", padding=(12, 8))
        st.configure("Asosiy.TButton", padding=(18, 14), font=("Segoe UI", 13, "bold"))

        threading.Thread(target=self._tinglovchi, daemon=True).start()

        def band(matn, cmd, **kw):  # matn funksiya — til almashsa menyu ham o'zgaradi
            return pystray.MenuItem(lambda _i: T(matn), lambda: self.q.put(cmd), **kw)
        self.tray = pystray.Icon("davomat", self.ikonka_rasm, "Davomat", pystray.Menu(
            band("Ochish", "panel", default=True),
            band("✅ Keldim", "keldim"),
            band("🏁 Ketdim", "ketdim"),
            band("Hisobot", "hisobot"),
            band("Ishlar ro'yxati", "ishlar"),
            band("Oylik hisobot", "oylik"),
            band("Sozlamalar", "sozlamalar"),
            band("Hisobotlar papkasi", "papka"),
            band("Chiqish", "chiqish"),
        ))
        self.tray.run_detached()

        self.root.after(300, self._navbat)
        self.root.after(1000, self._tekshir)
        self.root.after(15_000, tray_korinsin)
        # asosiy oyna doim pastki panelda turadi; bugun "Keldim" bosilgan yoki dam olish kuni bo'lsa — kichraytirilgan
        self.panel()
        if self.kun().get("keldi") or self.dam_kunimi():
            self.panel_oyna.iconify()
        if not self.soz["ism"]:
            self.root.after(400, self.tanishuv)

    def _kochir(self):
        """Eski (1.x) sozlamalarni yangisiga moslash."""
        s = self.soz
        if s.get("izoh") == "{sana} kunlik hisobot":  # eski standart — endi tilga qarab standart
            s["izoh"] = ""
        if not s.get("guruh_havola") and str(s.get("chat_id") or "").startswith("-100"):
            s["guruh_havola"] = f"https://t.me/c/{str(s['chat_id'])[4:]}/1"  # API da tanlangan guruh
        yoz(SOZ_FAYL, s)

    # ------------------------------------------------------------ yordamchilar
    @staticmethod
    def _ikonka():
        im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((2, 2, 62, 62), 14, fill=(16, 124, 65))
        d.rectangle((16, 14, 48, 50), fill="white")
        for y in (22, 30, 38):
            d.line((21, y, 43, y), fill=(16, 124, 65), width=3)
        return im

    @staticmethod
    def _png(im):
        import base64
        b = io.BytesIO()
        im.save(b, "PNG")
        return base64.b64encode(b.getvalue())

    def _tinglovchi(self):
        s = socket.socket()
        s.bind(("127.0.0.1", PORT))
        s.listen()
        while True:
            conn, _a = s.accept()
            try:
                conn.settimeout(1)
                xabar = conn.recv(32)
            except OSError:
                xabar = b""
            conn.close()
            self.q.put("chiqish" if xabar.startswith(b"chiqish") else "panel")

    def _navbat(self):
        while not self.q.empty():
            cmd = self.q.get()
            nom, arg = (cmd[0], cmd[1:]) if isinstance(cmd, tuple) else (cmd, ())
            if nom == "panel":
                self.panel()
            elif nom == "keldim":
                self.keldim()
            elif nom == "ketdim":
                self.ketdim()
            elif nom == "ishlar":
                self.ishlar_royxati()
            elif nom == "hisobot":
                self.hisobot()
            elif nom == "oylik":
                self.oylik()
            elif nom == "sozlamalar":
                self.sozlamalar()
            elif nom == "papka":
                os.makedirs(OUT, exist_ok=True)
                os.startfile(OUT)
            elif nom == "yangi":
                self._yangilanish_taklif(*arg)
            elif nom == "yangi_yoq":
                messagebox.showinfo("Davomat", T("Sizda eng yangi versiya ({v}).", v=VERSIYA), parent=self._ota())
            elif nom == "yangi_xato":
                messagebox.showwarning("Davomat", T("Yangilanishni tekshirib bo'lmadi:\n{e}", e=arg[0]),
                                       parent=self._ota())
            elif nom == "yuklandi":
                self._almashtir(arg[0])
            elif nom == "chiqish":
                self.tray.stop()
                self.root.destroy()
                return
        self.root.after(300, self._navbat)

    def kun(self, sana=None):
        return self.holat["kunlar"].setdefault(sana or bugun(), {})

    def saqla_holat(self):
        yoz(HOLAT_FAYL, self.holat)

    def saqla_soz(self):
        yoz(SOZ_FAYL, self.soz)

    def api_tayyor(self):
        s = self.soz
        return bool(str(s["api_id"]).isdigit() and s["api_hash"] and s["chat_id"]
                    and os.path.exists(SESSION + ".session"))

    def izoh_matn(self, sana):
        ism = self.soz["ism"].strip()
        andoza = self.soz["izoh"].strip() or (T("{sana} kunlik hisobot") + (" — {ism}" if ism else ""))
        try:
            return andoza.format(sana=sana, ism=ism)
        except (KeyError, IndexError, ValueError):
            return andoza

    def _ota(self):
        return self.panel_oyna if self.panel_oyna and self.panel_oyna.winfo_exists() else self.root

    @staticmethod
    def _oldinga(w):
        w.deiconify()
        w.lift()
        w.attributes("-topmost", True)
        w.after(500, lambda: w.attributes("-topmost", False))

    def _ochiqmi(self, w):
        if w and w.winfo_exists():
            self._oldinga(w)
            return True
        return False

    # ------------------------------------------------------------ keldim / ketdim va eslatma
    def dam_kunimi(self):
        """Dam olish chegarasigacha "Keldim" bosilmagan bo'lsa — bugun dam olish kuni."""
        chegara = vaqt_ol(self.soz["dam_chegara"]) or dt.time(18, 0)
        return not self.kun().get("keldi") and dt.datetime.now().time() >= chegara

    def keldim(self):
        k = self.kun()
        if k.get("keldi"):
            if not messagebox.askyesno("Davomat", T("Bugun {v} da «Keldim» bosilgan.\nKelgan vaqtni hozirgi vaqtga "
                                                    "o'zgartiraymi?", v=k["keldi"]), parent=self._ota()):
                return
        elif self.dam_kunimi():
            if not messagebox.askyesno("Davomat", T("Soat {v} dan o'tdi — bugun dam olish kuni deb hisoblangan.\n"
                                                    "Baribir «Keldim» deb belgilaymi?", v=self.soz["dam_chegara"]),
                                       parent=self._ota()):
                return
        k["keldi"] = hm(dt.datetime.now())
        self.saqla_holat()
        self.tray.notify(T("Kelgan vaqt: {v}", v=k["keldi"]), "Davomat")
        self._panel_yangila()

    def ketdim(self):
        k = self.kun()
        if not k.get("keldi"):
            messagebox.showwarning("Davomat", T("Bugun «Keldim» bosilmagan. Avval «Keldim» ni bosing (yoki hisobot "
                                                "oynasida kelgan vaqtni qo'lda yozing)."), parent=self._ota())
            return
        k["ketdi"] = hm(dt.datetime.now())
        self.saqla_holat()
        self._panel_yangila()
        if self.hisobot_oyna and self.hisobot_oyna.winfo_exists():  # ochiq oynada ham yangi vaqt
            self._h_ketgan.delete(0, "end")
            self._h_ketgan.insert(0, k["ketdi"])
        self.hisobot()

    def _tekshir(self):
        now = dt.datetime.now()
        k = self.kun()
        esl = vaqt_ol(self.soz["eslatma"]) or dt.time(17, 45)
        if (k.get("keldi") and not k.get("yuborildi") and now.time() >= esl
                and (self.keyingi_eslatma is None or now >= self.keyingi_eslatma)):
            self.keyingi_eslatma = now + dt.timedelta(minutes=max(1, int(self.soz["takror_daq"] or 15)))
            self.hisobot(eslatma=True)
        if FROZEN and now >= self.keyingi_yangilanish:
            self.keyingi_yangilanish = now + dt.timedelta(hours=12)
            self.yangilanish_tekshir()
        if self.panel_oyna and self.panel_oyna.winfo_exists():
            self._panel_yangila()  # kun almashsa ham to'g'ri ko'rsatsin
        self.root.after(30_000, self._tekshir)

    # ------------------------------------------------------------ yangilanish
    def yangilanish_tekshir(self, qolda=False):
        def ish():
            try:
                teg, url, izoh = yangilanish_ol()
            except Exception as e:  # noqa: BLE001 — internet yo'q va h.k.
                if qolda:
                    self.q.put(("yangi_xato", str(e)))
                return
            if _versiya(teg) > _versiya(VERSIYA) and url:
                if qolda or teg != self.yangilanish_soralgan:
                    self.q.put(("yangi", teg, url, izoh, qolda))
            elif qolda:
                self.q.put(("yangi_yoq",))
        threading.Thread(target=ish, daemon=True).start()

    def _yangilanish_taklif(self, teg, url, izoh, qolda):
        self.yangilanish_soralgan = teg
        if not FROZEN:
            messagebox.showinfo("Davomat", T("GitHub'da yangi versiya bor: {t}.\n(Ishlab chiqish nusxasi — "
                                             "o'zi yangilanmaydi.)", t=teg), parent=self._ota())
            return
        matn = T("Davomat'ning yangi versiyasi chiqdi: {t} (sizda {v}).", t=teg, v=VERSIYA)
        if izoh.strip():
            matn += "\n\n" + izoh.strip()[:600]
        if not messagebox.askyesno("Davomat", matn + "\n\n" + T("Hozir yangilaymi? (bir necha soniya)"),
                                   parent=self._ota()):
            return

        def yukla():
            yangi = os.path.join(os.path.dirname(sys.executable), "Davomat.new.exe")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Davomat"})
                with urllib.request.urlopen(req, timeout=120) as r, open(yangi, "wb") as f:
                    shutil.copyfileobj(r, f)
                if os.path.getsize(yangi) < 1_000_000:
                    raise OSError("yuklangan fayl juda kichik")
            except Exception as e:  # noqa: BLE001
                self.q.put(("yangi_xato", str(e)))
                return
            self.q.put(("yuklandi", yangi))
        self.tray.notify(T("Yangilanish yuklanmoqda..."), "Davomat")
        threading.Thread(target=yukla, daemon=True).start()

    def _almashtir(self, yangi):
        """Ishlab turgan exe nomini o'zgartirib (Windows ruxsat beradi), o'rniga yangisini qo'yib, qayta ishga tushirish."""
        exe = sys.executable
        eski = exe[:-4] + ".old.exe"
        try:
            if os.path.exists(eski):
                os.remove(eski)
            os.replace(exe, eski)
            os.replace(yangi, exe)
        except OSError as e:
            messagebox.showerror("Davomat", T("Yangilab bo'lmadi:\n{e}", e=e), parent=self._ota())
            return
        subprocess.Popen([exe, "--kut"], cwd=os.path.dirname(exe))
        self.q.put("chiqish")

    # ------------------------------------------------------------ birinchi ishga tushirish
    def tanishuv(self, qiymatlar=None):
        """Ism, til, guruh havolasi va ish vaqtini so'raydi (ism kiritilmaguncha har safar chiqadi)."""
        if self.tanishuv_oyna and self.tanishuv_oyna.winfo_exists():
            if qiymatlar is None:
                self._oldinga(self.tanishuv_oyna)
                return
            self.tanishuv_oyna.destroy()
        s = self.soz
        v = qiymatlar or {"til": TIL, "ism": s["ism"], "havola": s["guruh_havola"], "boshi": s["ish_boshi"]}
        w = self.tanishuv_oyna = tk.Toplevel(self.root)
        w.title(T("Davomat — xush kelibsiz"))
        w.resizable(False, False)
        f = ttk.Frame(w, padding=18)
        f.pack()
        ttk.Label(f, text=T("Xush kelibsiz! Bir marta sozlab olamiz."), font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        ttk.Label(f, text="Til / Язык / Language:").grid(row=1, column=0, sticky="w")
        til = ttk.Combobox(f, values=list(TILLAR.values()), state="readonly", width=14)
        til.set(TILLAR[v["til"]])
        til.grid(row=1, column=1, sticky="w", pady=3)

        ttk.Label(f, text=T("Ism-familiyangiz:")).grid(row=2, column=0, sticky="w")
        ism = ttk.Entry(f, width=40, font=("Segoe UI", 10))
        ism.insert(0, v["ism"])
        ism.grid(row=2, column=1, sticky="w", pady=3)
        ttk.Label(f, text=T("(hisobot rasmida va izohda chiqadi)"), foreground="gray").grid(
            row=3, column=1, sticky="w")

        ttk.Label(f, text=T("Guruh havolasi:")).grid(row=4, column=0, sticky="w", pady=(8, 0))
        havola = ttk.Entry(f, width=40, font=("Segoe UI", 10))
        havola.insert(0, v["havola"])
        havola.grid(row=4, column=1, sticky="w", pady=(8, 3))
        ttk.Label(f, text=T("Guruhdagi istalgan xabar ustida o'ng tugma → «Copy Message Link»\n"
                            "(yoki taklif havolasi t.me/+...). Ixtiyoriy — bo'lsa guruh o'zi ochiladi."),
                  foreground="gray", justify="left").grid(row=5, column=1, sticky="w")

        ttk.Label(f, text=T("Ish boshlanish vaqti:")).grid(row=6, column=0, sticky="w", pady=(8, 0))
        boshi = ttk.Entry(f, width=8, font=("Segoe UI", 10))
        boshi.insert(0, v["boshi"])
        boshi.grid(row=6, column=1, sticky="w", pady=(8, 3))

        def joriy():
            kod = next(k for k, n in TILLAR.items() if n == til.get())
            return {"til": kod, "ism": ism.get(), "havola": havola.get(), "boshi": boshi.get()}

        def til_ozgardi(_e=None):
            global TIL
            TIL = joriy()["til"]
            self.tanishuv(joriy())  # oyna yangi tilda qayta chiziladi
        til.bind("<<ComboboxSelected>>", til_ozgardi)

        def boshlash():
            global TIL
            j = joriy()
            if not j["ism"].strip():
                messagebox.showwarning("Davomat", T("Ism-familiyangizni yozing."), parent=w)
                return
            if j["havola"].strip() and not tg_havola(j["havola"]):
                messagebox.showwarning("Davomat", T("Guruh havolasi noto'g'ri. Masalan: https://t.me/c/1234567890/15 "
                                                    "yoki https://t.me/+AbCdEf..."), parent=w)
                return
            if not vaqt_ol(j["boshi"]):
                messagebox.showwarning("Davomat", T("Vaqtni SS:DD ko'rinishida yozing (masalan 09:00)."), parent=w)
                return
            TIL = j["til"]
            s.update(til=j["til"], ism=j["ism"].strip(), guruh_havola=j["havola"].strip(),
                     ish_boshi=hm(vaqt_ol(j["boshi"])))
            self.saqla_soz()
            w.destroy()
            self.qayta_chiz()

        ttk.Button(f, text=T("Boshlash"), style="Katta.TButton", command=boshlash).grid(
            row=7, column=1, sticky="e", pady=(14, 0))
        w.protocol("WM_DELETE_WINDOW", w.destroy)
        self._oldinga(w)
        ism.focus_set()

    def qayta_chiz(self):
        """Til almashganda asosiy oynani yangi tilda qayta chizish."""
        if self.panel_oyna and self.panel_oyna.winfo_exists():
            kichik = self.panel_oyna.state() == "iconic"
            self.panel_oyna.destroy()
            self.panel_oyna = None
            self.panel()
            if kichik:
                self.panel_oyna.iconify()

    # ------------------------------------------------------------ asosiy oyna (Keldim / Ketdim)
    def panel(self):
        if self.panel_oyna and self.panel_oyna.winfo_exists():
            w = self.panel_oyna
            w.deiconify()
        else:
            w = self.panel_oyna = tk.Toplevel(self.root)
            w.title("Davomat")
            w.resizable(False, False)
            w.protocol("WM_DELETE_WINDOW", w.iconify)  # yopilmaydi — pastki panelda qoladi
            f = ttk.Frame(w, padding=18)
            f.pack()
            self._p_sana = ttk.Label(f, font=("Segoe UI", 12, "bold"))
            self._p_sana.grid(row=0, column=0, columnspan=2, sticky="w")
            self._p_holat = ttk.Label(f, font=("Segoe UI", 10), justify="left")
            self._p_holat.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))
            ttk.Button(f, text="✅  " + T("Keldim"), style="Asosiy.TButton", command=self.keldim).grid(
                row=2, column=0, sticky="we", padx=(0, 6))
            ttk.Button(f, text="🏁  " + T("Ketdim"), style="Asosiy.TButton", command=self.ketdim).grid(
                row=2, column=1, sticky="we", padx=(6, 0))
            b = ttk.Frame(f)
            b.grid(row=3, column=0, columnspan=2, sticky="we", pady=(12, 0))
            for i, (matn, cmd) in enumerate(((T("Hisobot"), self.hisobot), (T("Ishlar ro'yxati"), self.ishlar_royxati),
                                             (T("Oylik hisobot"), self.oylik), (T("Sozlamalar"), self.sozlamalar))):
                ttk.Button(b, text=matn, command=cmd).grid(row=0, column=i, sticky="we", padx=(0 if i == 0 else 6, 0))
                b.columnconfigure(i, weight=1)
            ttk.Label(f, text=T("(yopsangiz pastki panelda qoladi)"), foreground="gray").grid(
                row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._panel_yangila()
        self._oldinga(w)

    def _panel_yangila(self):
        if not (self.panel_oyna and self.panel_oyna.winfo_exists()):
            return
        k = self.kun()
        bugun_ = dt.date.today()
        sarlavha = f"{bugun_:%d.%m.%Y}, {HAFTA[TIL][bugun_.weekday()]}"
        if self.soz["ism"]:
            sarlavha += f" — {self.soz['ism']}"
        self._p_sana.config(text=sarlavha)
        if self.dam_kunimi():
            matn, rang = T("Bugun dam olish kuni («Keldim» bosilmagan) — hisobot yuborilmaydi."), "gray"
        else:
            yub = T("yuborilgan ({v})", v=k["yuborildi"]) if k.get("yuborildi") else T("yuborilmagan")
            matn = (T("Keldim:") + f"  {k.get('keldi') or '—'}\n" + T("Ketdim:") + f"  {k.get('ketdi') or '—'}\n"
                    + T("Hisobot:") + f" {yub}")
            rang = YASHIL if k.get("yuborildi") else ""
        self._p_holat.config(text=matn, foreground=rang)

    # ------------------------------------------------------------ hisobot oynasi
    def hisobot(self, eslatma=False):
        if self._ochiqmi(self.hisobot_oyna):
            if eslatma:
                self.hisobot_oyna.bell()
            return
        k = self.kun()
        w = self.hisobot_oyna = tk.Toplevel(self.root)
        w.title(T("Kunlik hisobot — {sana}", sana=f"{dt.date.today():%d.%m.%Y}"))
        w.resizable(False, False)
        f = ttk.Frame(w, padding=16)
        f.pack(side="left", fill="both")

        if k.get("yuborildi"):
            ttk.Label(f, text=T("✔ Bugungi hisobot {v} da yuborilgan. Qayta yuborish mumkin.", v=k["yuborildi"]),
                      foreground=YASHIL).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        elif eslatma:
            ttk.Label(f, text=T("⏰ Kunlik hisobotni yuborish vaqti bo'ldi!"), foreground="#c42b1c",
                      font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        ttk.Label(f, text=T("Ishga kelgan vaqtim:")).grid(row=1, column=0, sticky="w")
        kelgan = ttk.Entry(f, width=8, font=("Segoe UI", 11))
        kelgan.insert(0, k.get("keldi", ""))
        kelgan.grid(row=1, column=1, sticky="w", pady=2)
        ttk.Label(f, text=T("(«Keldim» bosilgan vaqt)"), foreground="gray").grid(row=1, column=2, sticky="w")

        tarix = self.holat["ishlar_tarixi"]
        tayyor = self.holat.setdefault("tayyor_ishlar", [])
        ttk.Label(f, text=T("Bajarilgan ishlar (o'ngdagi ro'yxatdan tanlang yoki o'zingiz yozing):")).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(10, 4))
        qatorlar = []
        saqlangan = k.get("ishlar", [])
        for i in range(ISH_SONI):
            ttk.Label(f, text=f"{i + 1}.").grid(row=3 + i, column=0, sticky="e", padx=(0, 6))
            cb = ttk.Combobox(f, values=list(dict.fromkeys(tayyor + tarix)), width=60, font=("Segoe UI", 10))
            if i < len(saqlangan):
                cb.insert(0, saqlangan[i])
            avto_toldir(cb, lambda: list(dict.fromkeys(tayyor + tarix)))
            cb.grid(row=3 + i, column=1, columnspan=2, sticky="we", pady=1)
            qatorlar.append(cb)

        # o'ng tomonda: oldindan yozib qo'yilgan ishlar — ikki marta bosilsa keyingi bo'sh qatorga tushadi
        o = ttk.Frame(w, padding=(0, 16, 16, 16))
        o.pack(side="left", fill="both")
        ttk.Label(o, text=T("Tayyor ishlar"), font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(o, text=T("(ikki marta bosing — qo'shiladi)"), foreground="gray").pack(anchor="w")
        lb = tk.Listbox(o, width=38, height=16, font=("Segoe UI", 10), activestyle="none")
        lb.pack(fill="both", expand=True, pady=4)

        def royxat_yangila():
            lb.delete(0, "end")
            for x in tayyor:
                lb.insert("end", x)
            for q in qatorlar:
                q.config(values=list(dict.fromkeys(tayyor + tarix)))
        royxat_yangila()

        def qosh(_e=None):
            for sel in lb.curselection():
                ish = tayyor[sel]
                if any(q.get().strip() == ish for q in qatorlar):
                    continue  # allaqachon bor
                bosh = next((q for q in qatorlar if not q.get().strip()), None)
                if bosh is None:
                    messagebox.showinfo("Davomat", T("{n} ta qatorning hammasi to'lgan.", n=ISH_SONI), parent=w)
                    return
                bosh.insert(0, ish)
        lb.bind("<Double-Button-1>", qosh)
        ttk.Button(o, text=T("← Qo'shish"), command=qosh).pack(fill="x")
        ttk.Button(o, text=T("Ro'yxatni tahrirlash"), command=lambda: self.ishlar_royxati(royxat_yangila)).pack(
            fill="x", pady=(4, 0))

        r = 3 + ISH_SONI
        ttk.Label(f, text=T("Ishdan ketgan vaqtim:")).grid(row=r, column=0, sticky="w", pady=(10, 0))
        ketgan = ttk.Entry(f, width=8, font=("Segoe UI", 11))
        ketgan.insert(0, k.get("ketdi") or hm(dt.datetime.now()))
        ketgan.grid(row=r, column=1, sticky="w", pady=(10, 0))
        self._h_ketgan = ketgan
        if self.soz["guruh_havola"]:
            guruh = T("Guruh: {g} — Telegram'da o'zi ochiladi.", g=self.soz["chat_nomi"] or self.soz["guruh_havola"])
        else:
            guruh = T("Guruh havolasi kiritilmagan — yuborishdan oldin guruhni Telegram'da o'zingiz oching "
                      "(yoki Sozlamalarga havolani kiriting).")
        ttk.Label(f, text=guruh, foreground="gray", wraplength=560, justify="left").grid(
            row=r + 1, column=0, columnspan=3, sticky="w", pady=(8, 0))

        def malumot():
            return ([q.get().strip() for q in qatorlar if q.get().strip()], kelgan.get(), ketgan.get())

        def qoralama():
            ishlar, kel, ket = malumot()
            k["ishlar"] = ishlar
            for key, val in (("keldi", kel), ("ketdi", ket)):
                if vaqt_ol(val):
                    k[key] = hm(vaqt_ol(val))
            self.saqla_holat()
            self._panel_yangila()

        def keyinroq():
            qoralama()
            w.destroy()

        def rasm_tayyorla():
            """Tekshiradi, qoralamani saqlaydi va hisobot rasmini yasaydi -> (path, izoh) yoki None."""
            ishlar, kel, ket = malumot()
            t1, t2 = vaqt_ol(kel), vaqt_ol(ket)
            if not t1 or not t2:
                messagebox.showwarning("Davomat", T("Kelgan va ketgan vaqtni SS:DD ko'rinishida yozing "
                                                    "(masalan 09:00)."), parent=w)
                return None
            if not ishlar:
                messagebox.showwarning("Davomat", T("Kamida bitta bajarilgan ishni yozing."), parent=w)
                return None
            qoralama()
            sana = dt.date.today().strftime("%d.%m.%Y")
            try:
                nom = self.soz["fayl_nomi"].format(sana=sana, ism=self.soz["ism"])
            except (KeyError, IndexError, ValueError):
                nom = STANDART["fayl_nomi"].format(sana=sana)
            nom = re.sub(r'[\\/:*?"<>|]', "_", os.path.splitext(nom)[0]) + ".png"
            path = rasm_yasa(dt.date.today(), t1, t2, ishlar, os.path.join(OUT, nom), self.soz["ism"])
            return path, self.izoh_matn(sana)

        def yubor():
            """Asosiy tugma: API sozlangan bo'lsa — API orqali, aks holda Telegram Desktop orqali."""
            if not self.api_tayyor():
                return ulash()
            t = rasm_tayyorla()
            if not t:
                return
            path, izoh = t
            w.config(cursor="watch")
            w.update()
            try:
                self.tg.yubor(self.soz, path, izoh)
            except Exception as e:  # noqa: BLE001 — foydalanuvchiga ko'rsatiladi
                w.config(cursor="")
                if messagebox.askyesno("Davomat", T("API orqali yuborib bo'lmadi:\n{e}\n\nTelegram Desktop orqali "
                                                    "yuboraymi?", e=e), parent=w):
                    ulash()
                return
            yuborildi(T("Hisobot «{g}» guruhiga yuborildi.", g=self.soz["chat_nomi"]))

        def ulash():
            """Telegram Desktop orqali, o'z akkauntidan, kodsiz."""
            t = rasm_tayyorla()
            if not t:
                return
            path, izoh = t
            havola = tg_havola(self.soz["guruh_havola"])
            if havola:  # bir tugma: guruh o'zi ochiladi
                w.config(cursor="watch")
                try:
                    telegramga_joyla(path, izoh, w, havola)
                except Exception as e:  # noqa: BLE001
                    w.config(cursor="")
                    messagebox.showerror("Davomat", T("Yuborib bo'lmadi:\n{e}\n\nRasm saqlandi: {p}", e=e, p=path),
                                         parent=w)
                    return
                yuborildi(T("Hisobot Telegram orqali yuborildi."))
                return

            exe = telegram_exe()
            if exe:
                subprocess.Popen([exe])  # yopiq bo'lsa ochadi, ochiq bo'lsa oldinga chiqaradi
            u = tk.Toplevel(w)
            u.title(T("Telegram orqali yuborish"))
            u.resizable(False, False)
            u.attributes("-topmost", True)
            u.transient(w)
            g = ttk.Frame(u, padding=14)
            g.pack()
            ttk.Label(g, text=T("Telegram'da hisobot guruhini oching,\nkeyin «Yuborish ➤» ni bosing."),
                      font=("Segoe UI", 10, "bold")).pack(anchor="w")
            ttk.Label(g, text=T("Izoh: «{i}»", i=izoh), foreground="gray").pack(anchor="w", pady=(6, 0))
            ttk.Label(g, text=T("Maslahat: Sozlamalarga guruh havolasini kiritsangiz, guruh o'zi ochiladi."),
                      foreground="gray").pack(anchor="w", pady=(4, 0))

            def jonat():
                try:
                    telegramga_joyla(path, izoh, u)
                except Exception as e:  # noqa: BLE001
                    messagebox.showerror("Davomat", T("Yuborib bo'lmadi:\n{e}", e=e), parent=u)
                    return
                u.destroy()
                yuborildi(T("Hisobot Telegram orqali yuborildi."))

            p = ttk.Frame(g)
            p.pack(fill="x", pady=(12, 0))
            ttk.Button(p, text=T("Yuborish ➤"), style="Katta.TButton", command=jonat).pack(side="right")
            ttk.Button(p, text=T("Bekor"), command=u.destroy).pack(side="right", padx=6)

        def yuborildi(xabar):
            ishlar = malumot()[0]
            k["yuborildi"] = hm(dt.datetime.now())
            for x in ishlar:  # yangi ishlar ro'yxat boshiga
                if x in tarix:
                    tarix.remove(x)
                tarix.insert(0, x)
            del tarix[60:]
            self.saqla_holat()
            self._panel_yangila()
            w.destroy()
            self.tray.notify(xabar, "Davomat")

        b = ttk.Frame(f)
        b.grid(row=r + 2, column=0, columnspan=3, sticky="e", pady=(14, 0))
        ttk.Button(b, text=T("Keyinroq"), command=keyinroq).pack(side="left", padx=4)
        ttk.Button(b, text=T("Saqlash"), command=qoralama).pack(side="left", padx=4)
        if self.api_tayyor():  # ikkala usul: asosiy — API, qo'shimcha — Telegram Desktop
            ttk.Button(b, text=T("Telegram Desktop orqali"), command=ulash).pack(side="left", padx=4)
        ttk.Button(b, text=T("Yuborish ➤"), style="Katta.TButton", command=yubor).pack(side="left", padx=4)
        w.protocol("WM_DELETE_WINDOW", keyinroq)
        self._oldinga(w)
        (qatorlar[len(saqlangan)] if len(saqlangan) < ISH_SONI else qatorlar[0]).focus_set()

    # ------------------------------------------------------------ tayyor ishlar ro'yxati
    def ishlar_royxati(self, keyin=None):
        """Hisobotga yozilishi mumkin bo'lgan ishlarni oldindan yozib qo'yish (qo'shish, o'zgartirish, o'chirish, tartib)."""
        if self._ochiqmi(self.royxat_oyna):
            return
        tayyor = self.holat.setdefault("tayyor_ishlar", [])
        w = self.royxat_oyna = tk.Toplevel(self.root)
        w.title(T("Davomat — tayyor ishlar ro'yxati"))
        w.resizable(False, False)
        f = ttk.Frame(w, padding=16)
        f.pack()
        ttk.Label(f, text=T("Hisobotga yozilishi mumkin bo'lgan ishlar. Hisobot oynasida shu ro'yxatdan tanlaysiz."),
                  foreground="gray").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        lb = tk.Listbox(f, width=60, height=14, font=("Segoe UI", 10), activestyle="none")
        lb.grid(row=1, column=0, sticky="nsew")
        tug = ttk.Frame(f)
        tug.grid(row=1, column=1, sticky="n", padx=(8, 0))
        matn = ttk.Entry(f, width=60, font=("Segoe UI", 10))
        matn.grid(row=2, column=0, sticky="we", pady=(8, 0))

        def saqla(tanla=None):
            self.saqla_holat()
            lb.delete(0, "end")
            for x in tayyor:
                lb.insert("end", x)
            if tanla is not None and 0 <= tanla < len(tayyor):
                lb.selection_set(tanla)
                lb.see(tanla)
            if keyin:
                keyin()

        def tanlangan():
            sel = lb.curselection()
            return sel[0] if sel else None

        def qosh(_e=None):
            x = matn.get().strip()
            if x and x not in tayyor:
                tayyor.append(x)
                matn.delete(0, "end")
                saqla(len(tayyor) - 1)
            matn.focus_set()

        def ozgartir():
            i, x = tanlangan(), matn.get().strip()
            if i is None or not x:
                messagebox.showinfo("Davomat", T("Ro'yxatdan ishni tanlang va pastda yangi matnni yozing."), parent=w)
                return
            tayyor[i] = x
            saqla(i)

        def ochir():
            i = tanlangan()
            if i is not None:
                del tayyor[i]
                saqla(min(i, len(tayyor) - 1))

        def sur(qadam):
            i = tanlangan()
            if i is not None and 0 <= i + qadam < len(tayyor):
                tayyor[i], tayyor[i + qadam] = tayyor[i + qadam], tayyor[i]
                saqla(i + qadam)

        def tanlanganda(_e=None):
            i = tanlangan()
            if i is not None:
                matn.delete(0, "end")
                matn.insert(0, tayyor[i])

        lb.bind("<<ListboxSelect>>", tanlanganda)
        matn.bind("<Return>", qosh)
        ttk.Button(f, text=T("➕ Qo'shish"), command=qosh).grid(row=2, column=1, sticky="we", padx=(8, 0), pady=(8, 0))
        for nom, cmd in ((T("✏ O'zgartirish"), ozgartir), (T("🗑 O'chirish"), ochir),
                         (T("▲ Yuqoriga"), lambda: sur(-1)), (T("▼ Pastga"), lambda: sur(1))):
            ttk.Button(tug, text=nom, command=cmd).pack(fill="x", pady=2)
        ttk.Label(f, text=T("Yangi ishni pastga yozib Enter yoki «Qo'shish» ni bosing."), foreground="gray").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        saqla()
        self._oldinga(w)
        matn.focus_set()

    # ------------------------------------------------------------ oylik hisobot
    def oylik(self):
        if self._ochiqmi(self.oylik_oyna):
            return
        kunlar = self.holat["kunlar"]
        oylar = sorted({x[:7] for x, k in kunlar.items() if k.get("keldi")} | {bugun()[:7]}, reverse=True)
        w = self.oylik_oyna = tk.Toplevel(self.root)
        w.title(T("Davomat — oylik hisobot"))
        w.resizable(False, False)
        f = ttk.Frame(w, padding=16)
        f.pack()
        ttk.Label(f, text=T("Oy:")).grid(row=0, column=0, sticky="w")
        tanlov = ttk.Combobox(f, values=[oy_nomi(o) for o in oylar], state="readonly", width=18)
        tanlov.current(0)
        tanlov.grid(row=0, column=1, sticky="w", padx=6)
        natija = ttk.Label(f, font=("Segoe UI", 10), justify="left")
        natija.grid(row=1, column=0, columnspan=3, sticky="w", pady=(12, 0))

        def oy():
            return oylar[tanlov.current()]

        def korsat(_e=None):
            _q, j = oy_hisobi(kunlar, oy(), self.soz["ish_boshi"])
            natija.config(text="\n".join((
                T("Ish kunlari: {n}", n=j["kunlar"]),
                T("Jami ishlagan vaqt: {v}", v=soat_daq(j["jami"])),
                T("O'rtacha kunlik: {v}", v=soat_daq(j["ortacha"])),
                T("Kech qolgan kunlar: {n} (jami {d} daq, ish boshlanishi {b})", n=j["kech_kun"], d=j["kech_jami"],
                  b=self.soz["ish_boshi"]),
                T("Hisobot yuborilmagan kunlar: {n}", n=j["yuborilmagan"]))))
        tanlov.bind("<<ComboboxSelected>>", korsat)
        korsat()

        def excel():
            ism = re.sub(r'[\\/:*?"<>|]', "_", self.soz["ism"] or "")
            path = os.path.join(OUT, f"Davomat {oy()} {ism}".strip() + ".xlsx")
            try:
                oylik_xlsx(kunlar, oy(), self.soz["ism"], self.soz["ish_boshi"], path)
            except PermissionError:
                messagebox.showerror("Davomat", T("Fayl boshqa dasturda ochiq turibdi — Excel'ni yopib, qayta "
                                                  "urinib ko'ring:\n{p}", p=path), parent=w)
                return
            os.startfile(path)

        ttk.Button(f, text=T("Excel'ga saqlash va ochish"), style="Katta.TButton", command=excel).grid(
            row=2, column=0, columnspan=3, sticky="e", pady=(14, 0))
        self._oldinga(w)

    # ------------------------------------------------------------ sozlamalar
    def sozlamalar(self):
        if self._ochiqmi(self.soz_oyna):
            return
        s = self.soz
        w = self.soz_oyna = tk.Toplevel(self.root)
        w.title(T("Davomat — sozlamalar"))
        w.resizable(False, False)
        f = ttk.Frame(w, padding=16)
        f.pack()
        qator = [0]

        def bolim(matn):
            ttk.Label(f, text=matn, font=("Segoe UI", 10, "bold")).grid(
                row=qator[0], column=0, columnspan=3, sticky="w", pady=(12 if qator[0] else 0, 2))
            qator[0] += 1

        def maydon(nom, qiymat, en=40, izoh=None):
            ttk.Label(f, text=nom).grid(row=qator[0], column=0, sticky="w")
            e = ttk.Entry(f, width=en)
            e.insert(0, str(qiymat))
            e.grid(row=qator[0], column=1, sticky="w", pady=2, columnspan=1 if izoh else 2)
            if izoh:
                ttk.Label(f, text=izoh, foreground="gray").grid(row=qator[0], column=2, sticky="w", padx=(6, 0))
            qator[0] += 1
            return e

        bolim(T("Asosiy"))
        ttk.Label(f, text="Til / Язык / Language:").grid(row=qator[0], column=0, sticky="w")
        til = ttk.Combobox(f, values=list(TILLAR.values()), state="readonly", width=14)
        til.set(TILLAR[TIL])
        til.grid(row=qator[0], column=1, sticky="w", pady=2)
        qator[0] += 1
        ism = maydon(T("Ism-familiya:"), s["ism"])

        bolim(T("Guruh"))
        havola = maydon(T("Guruh havolasi:"), s["guruh_havola"], 46)
        ttk.Label(f, text=T("Guruhdagi istalgan xabar ustida o'ng tugma → «Copy Message Link»\n"
                            "(yoki taklif havolasi t.me/+...). Ixtiyoriy — bo'lsa guruh o'zi ochiladi."),
                  foreground="gray", justify="left").grid(row=qator[0], column=1, columnspan=2, sticky="w")
        qator[0] += 1

        def sina():
            h = tg_havola(havola.get())
            if not h:
                messagebox.showwarning("Davomat", T("Guruh havolasi noto'g'ri. Masalan: https://t.me/c/1234567890/15 "
                                                    "yoki https://t.me/+AbCdEf..."), parent=w)
                return
            os.startfile(h)
        ttk.Button(f, text=T("Havolani sinash"), command=sina).grid(row=qator[0], column=1, sticky="w", pady=2)
        qator[0] += 1

        bolim(T("Ish vaqti va eslatma"))
        boshi = maydon(T("Ish boshlanishi:"), s["ish_boshi"], 8, T("(oylik hisobotda kechikish shundan hisoblanadi)"))
        esl = maydon(T("Eslatma vaqti:"), s["eslatma"], 8, T("(«Keldim» bosilgan kuni, hisobot yuborilmagan bo'lsa)"))
        takror = maydon(T("Takrorlash (daq):"), s["takror_daq"], 8, T("(yuborilmaguncha har necha daqiqada)"))
        dam = maydon(T("Dam olish chegarasi:"), s["dam_chegara"], 8,
                     T("(shu vaqtgacha «Keldim» bosilmasa — dam olish kuni)"))

        bolim(T("Hisobot"))
        fayl = maydon(T("Rasm fayli nomi:"), s["fayl_nomi"])
        izoh = maydon(T("Xabar matni:"), s["izoh"])
        ttk.Label(f, text=T("Bo'sh qoldirilsa: «{n}». {{sana}}, {{ism}} ishlatish mumkin.",
                            n=self.izoh_matn(dt.date.today().strftime("%d.%m.%Y"))),
                  foreground="gray").grid(row=qator[0], column=1, columnspan=2, sticky="w")
        qator[0] += 1

        # ---- kengaytirilgan: Telegram API (Telethon) — ochiladigan bo'lim
        kengayt = ttk.Frame(f)
        ochiq = [bool(s["api_id"])]
        tugma = ttk.Button(f)
        tugma.grid(row=qator[0], column=0, columnspan=3, sticky="w", pady=(14, 0))
        qator[0] += 1
        kengayt.grid(row=qator[0], column=0, columnspan=3, sticky="w")
        qator[0] += 1

        def almash():
            ochiq[0] = not ochiq[0]
            chiz()

        def chiz():
            tugma.config(text=("▾ " if ochiq[0] else "▸ ") + T("Kengaytirilgan: Telegram API orqali yuborish"),
                         command=almash)
            if ochiq[0]:
                kengayt.grid()
            else:
                kengayt.grid_remove()

        ttk.Label(kengayt, text=T("Xabar sizning akkauntingizdan to'g'ridan-to'g'ri ketadi (Telegram Desktop shart "
                                  "emas).\nmy.telegram.org → API development tools dan api_id va api_hash oling."),
                  foreground="gray", justify="left").grid(row=0, column=0, columnspan=3, sticky="w", pady=(4, 4))
        api = {}
        for i, (k, nom) in enumerate((("api_id", "api_id:"), ("api_hash", "api_hash:"),
                                      ("telefon", T("Telefon (+998...):")))):
            ttk.Label(kengayt, text=nom).grid(row=1 + i, column=0, sticky="w")
            e = ttk.Entry(kengayt, width=40)
            e.insert(0, str(s[k]))
            e.grid(row=1 + i, column=1, columnspan=2, sticky="w", pady=2)
            api[k] = e
        holat = ttk.Label(kengayt, foreground="gray")
        holat.grid(row=4, column=1, columnspan=2, sticky="w")
        guruh = ttk.Label(kengayt, text=s["chat_nomi"] or T("— tanlanmagan"))
        guruh.grid(row=5, column=1, columnspan=2, sticky="w")

        def olish():
            for k in ("api_id", "api_hash", "telefon"):
                s[k] = api[k].get().strip()
            s["telefon"] = telefon_ol(s["telefon"])
            api["telefon"].delete(0, "end")
            api["telefon"].insert(0, s["telefon"])

        def kirish():
            olish()
            if not 12 <= len(s["telefon"]) <= 16:
                messagebox.showwarning("Davomat", T("Telefon raqami noto'g'ri: {t}\nMasalan: +998901234567",
                                                    t=s["telefon"] or "—"), parent=w)
                return
            if not str(s["api_id"]).isdigit() or not s["api_hash"]:
                messagebox.showwarning("Davomat", T("api_id (raqam), api_hash va telefonni yozing."), parent=w)
                return
            try:
                if self.tg.kirganmi(s):
                    holat.config(text=T("✔ Kirilgan"), foreground=YASHIL)
                    return
                c = self.tg.client
                self.tg.run(c.send_code_request(s["telefon"]))
                kod = simpledialog.askstring("Telegram", T("Telegram ilovasiga kelgan kodni yozing:"), parent=w)
                if not kod:
                    return
                try:
                    self.tg.run(c.sign_in(s["telefon"], kod.strip()))
                except SessionPasswordNeededError:
                    pw = simpledialog.askstring("Telegram", T("Ikki bosqichli tekshiruv paroli:"), parent=w, show="•")
                    if not pw:
                        return
                    self.tg.run(c.sign_in(password=pw))
                holat.config(text=T("✔ Kirildi"), foreground=YASHIL)
                self.saqla_soz()
            except Exception as e:  # noqa: BLE001
                messagebox.showerror("Davomat", T("Kirib bo'lmadi:\n{e}", e=e), parent=w)

        def guruh_tanla():
            olish()
            try:
                if not self.tg.kirganmi(s):
                    messagebox.showwarning("Davomat", T("Avval Telegramga kiring."), parent=w)
                    return
                royxat = self.tg.guruhlar(s)
            except Exception as e:  # noqa: BLE001
                messagebox.showerror("Davomat", T("Guruhlarni olib bo'lmadi:\n{e}", e=e), parent=w)
                return
            t = tk.Toplevel(w)
            t.title(T("Guruhni tanlang"))
            lb = tk.Listbox(t, width=50, height=18, font=("Segoe UI", 10))
            for _id, nom in royxat:
                lb.insert("end", nom)
            lb.pack(padx=10, pady=10)

            def ok(_e=None):
                sel = lb.curselection()
                if sel:
                    s["chat_id"], s["chat_nomi"] = royxat[sel[0]]
                    guruh.config(text=s["chat_nomi"])
                    if str(s["chat_id"]).startswith("-100") and not havola.get().strip():
                        havola.insert(0, f"https://t.me/c/{str(s['chat_id'])[4:]}/1")
                    self.saqla_soz()
                t.destroy()
            lb.bind("<Double-Button-1>", ok)
            ttk.Button(t, text=T("Tanlash"), command=ok).pack(pady=(0, 10))

        ttk.Button(kengayt, text=T("Telegramga kirish"), command=kirish).grid(row=4, column=0, sticky="w", pady=4)
        ttk.Button(kengayt, text=T("Guruhni tanlash"), command=guruh_tanla).grid(row=5, column=0, sticky="w", pady=4)
        chiz()

        # ---- pastki qator: versiya, yangilanish, o'chirish, saqlash
        p = ttk.Frame(f)
        p.grid(row=qator[0], column=0, columnspan=3, sticky="we", pady=(16, 0))
        ttk.Label(p, text=T("Versiya {v}", v=VERSIYA), foreground="gray").pack(side="left")
        ttk.Button(p, text=T("Yangilanishni tekshirish"), command=lambda: self.yangilanish_tekshir(qolda=True)).pack(
            side="left", padx=6)
        if FROZEN:
            def ochir():
                subprocess.Popen([sys.executable, "--ochirish"])
            ttk.Button(p, text=T("Ilovani o'chirish"), command=ochir).pack(side="left")

        def saqla():
            global TIL
            olish()
            vaqtlar = [vaqt_ol(x.get()) for x in (boshi, esl, dam)]
            if not all(vaqtlar):
                messagebox.showwarning("Davomat", T("Vaqtlarni SS:DD ko'rinishida yozing (masalan 17:45)."), parent=w)
                return
            if not takror.get().strip().isdigit() or not 1 <= int(takror.get()) <= 240:
                messagebox.showwarning("Davomat", T("Takrorlash — 1 dan 240 gacha daqiqa."), parent=w)
                return
            if havola.get().strip() and not tg_havola(havola.get()):
                messagebox.showwarning("Davomat", T("Guruh havolasi noto'g'ri. Masalan: https://t.me/c/1234567890/15 "
                                                    "yoki https://t.me/+AbCdEf..."), parent=w)
                return
            if not ism.get().strip():
                messagebox.showwarning("Davomat", T("Ism-familiyangizni yozing."), parent=w)
                return
            yangi_til = next(k for k, n in TILLAR.items() if n == til.get())
            s.update(ism=ism.get().strip(), guruh_havola=havola.get().strip(), ish_boshi=hm(vaqtlar[0]),
                     eslatma=hm(vaqtlar[1]), dam_chegara=hm(vaqtlar[2]), takror_daq=int(takror.get()),
                     fayl_nomi=fayl.get().strip() or STANDART["fayl_nomi"], izoh=izoh.get().strip(), til=yangi_til)
            self.saqla_soz()
            self.keyingi_eslatma = None
            w.destroy()
            if yangi_til != TIL:
                TIL = yangi_til
            self.qayta_chiz()

        ttk.Button(p, text=T("Saqlash"), style="Katta.TButton", command=saqla).pack(side="right")
        self._oldinga(w)

        def kirish_holati():
            if not (str(s["api_id"]).isdigit() and s["api_hash"] and os.path.exists(SESSION + ".session")):
                return
            try:
                if self.tg.kirganmi(s):
                    holat.config(text=T("✔ Kirilgan"), foreground=YASHIL)
            except Exception:  # noqa: BLE001 — internet yo'q va h.k.; kirish tugmasi xatoni ko'rsatadi
                pass
        if ochiq[0]:
            w.after(300, kirish_holati)


def sinov(fayl):
    """Davomat.exe --sinov <fayl>: yig'ilgan exe ichidagi qismlar ishlashini tekshirish (o'rnatmaydi)."""
    natija = {"versiya": VERSIYA, "frozen": FROZEN}
    for nom, fn in (
            ("uia", lambda: _uia()[1] is not None),
            ("telegram_exe", telegram_exe),
            ("telegram_oyna", lambda: bool(_telegram_oynasi())),
            ("rasm", lambda: rasm_yasa(dt.date.today(), dt.time(9), dt.time(18), ["sinov"],
                                       os.path.join(os.environ["TEMP"], "davomat_sinov.png"), "Sinov")),
            ("xlsx", lambda: oylik_xlsx({bugun(): {"keldi": "09:10", "ketdi": "18:00", "ishlar": ["a"]}}, bugun()[:7],
                                        "Sinov", "09:00", os.path.join(os.environ["TEMP"], "davomat_sinov.xlsx"))),
            ("telethon", lambda: TelegramClient is not None),
            ("tarjima", lambda: (len(TR), T("Keldim"))),
    ):
        try:
            natija[nom] = repr(fn())
        except Exception as e:  # noqa: BLE001
            natija[nom] = "XATO: " + repr(e)
    with open(fayl, "w", encoding="utf-8") as f:
        json.dump(natija, f, ensure_ascii=False, indent=1)


def main():
    a = sys.argv[1:]
    if "--sinov" in a:
        sinov(a[a.index("--sinov") + 1])
        return
    if "--ochirish" in a:
        ochirish()
        return
    if FROZEN:
        if os.path.normcase(os.path.abspath(sys.executable)) != os.path.normcase(INSTALL_EXE):
            ornatish()  # yuklab olingan fayl ochildi — o'rnatamiz
            return
        try:
            os.remove(INSTALL_EXE[:-4] + ".old.exe")  # yangilanishdan qolgan eski versiya
        except OSError:
            pass
    if "--kut" in a:  # yangilanish/o'rnatishdan keyin: eski nusxa yopilishini kutish
        oxiri = time.time() + 20
        while port_bandmi() and time.time() < oxiri:
            time.sleep(0.3)
    # bitta nusxa: ilova allaqachon ishlayotgan bo'lsa — uning oynasini ochadi
    if boshqasiga(b"panel"):
        return
    if FROZEN:
        try:
            royxatga_yoz(sys.executable)  # versiya raqami «Ilovalar» ro'yxatida yangilansin
        except OSError:
            pass
    # pastki panelda python emas, o'z belgisi va nomi bilan alohida ko'rinsin
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("mjavohir.davomat")
    Ilova().root.mainloop()


# ------------------------------------------------------------------ tarjimalar (o'zbekcha -> rus, ingliz)
TR.update({
    'Oylik davomat — {oy}': ('Месячная посещаемость — {oy}', 'Monthly attendance — {oy}'),
    'Xodim: {ism}': ('Сотрудник: {ism}', 'Employee: {ism}'),
    'Ish boshlanishi: {v}': ('Начало работы: {v}', 'Work starts at: {v}'),
    'Kunlik hisobot — {sana} ({kun})': ('Ежедневный отчёт — {sana} ({kun})', 'Daily report — {sana} ({kun})'),
    'Ishga kelgan vaqtim': ('Время прихода', 'Arrival time'),
    'Ishdan ketgan vaqtim': ('Время ухода', 'Departure time'),
    "Yuborish oynasi yopilmadi — Telegram'ni tekshiring.": ('Окно отправки не закрылось — проверьте Telegram.', 'The send window did not close — check Telegram.'),
    'Sana': ('Дата', 'Date'),
    'Kun': ('День', 'Day'),
    'Keldi': ('Пришёл', 'Arrived'),
    'Ketdi': ('Ушёл', 'Left'),
    'Ishlagan vaqt': ('Отработано', 'Worked'),
    'Kechikish (daq)': ('Опоздание (мин)', 'Late (min)'),
    'Hisobot yuborildi': ('Отчёт отправлен', 'Report sent'),
    'Bajarilgan ishlar': ('Выполненные работы', 'Completed tasks'),
    "Davomat {v} o'rnatildi.\n\nIsh stolida «Davomat» yorlig'i paydo bo'ldi, kompyuter yonganda o'zi ishga tushadi.\nYuklab olingan faylni endi o'chirib tashlashingiz mumkin.": ('Davomat {v} установлен.\n\nНа рабочем столе появился ярлык «Davomat», программа запускается вместе с компьютером.\nСкачанный файл теперь можно удалить.', 'Davomat {v} has been installed.\n\nA «Davomat» shortcut is on your desktop, and the app starts with Windows.\nYou can now delete the downloaded file.'),
    "Davomat o'chirildi.": ('Davomat удалён.', 'Davomat has been uninstalled.'),
    "Davomat'ning yangi versiyasi chiqdi: {t} (sizda {v}).": ('Вышла новая версия Davomat: {t} (у вас {v}).', 'A new version of Davomat is available: {t} (you have {v}).'),
    "Telegram oynasi topilmadi — Telegram Desktop'ni oching.": ('Окно Telegram не найдено — откройте Telegram Desktop.', 'Telegram window not found — open Telegram Desktop.'),
    "Telegram'da boshqa oyna ochiq turibdi — avval uni yoping.": ('В Telegram открыто другое окно — сначала закройте его.', 'Another window is open in Telegram — close it first.'),
    "Telegram'da chat ochilmagan — hisobot guruhini ochib, qayta bosing.": ('В Telegram не открыт чат — откройте группу для отчётов и нажмите ещё раз.', 'No chat is open in Telegram — open the report group and press again.'),
    "Xabar maydoniga fokus o'tmadi — hech narsa yuborilmadi.": ('Не удалось поставить курсор в поле сообщения — ничего не отправлено.', 'Could not focus the message field — nothing was sent.'),
    'Rasm yuborish oynasi chiqmadi — hech narsa yuborilmadi.': ('Окно отправки фото не появилось — ничего не отправлено.', 'The photo send window did not appear — nothing was sent.'),
    'Ish kunlari': ('Рабочих дней', 'Working days'),
    'Jami ishlagan vaqt': ('Всего отработано', 'Total worked'),
    "O'rtacha kunlik": ('В среднем за день', 'Daily average'),
    'Kech qolgan kunlar': ('Дней с опозданием', 'Days late'),
    'Jami kechikish (daq)': ('Всего опозданий (мин)', 'Total lateness (min)'),
    'Hisobot yuborilmagan kunlar': ('Дней без отчёта', 'Days without a report'),
    "Davomat ilovasini kompyuterdan o'chiraymi?": ('Удалить Davomat с компьютера?', 'Uninstall Davomat from this computer?'),
    "Sozlamalar, davomat tarixi va hisobot rasmlari ham o'chirilsinmi?\n\n{p}": ('Удалить также настройки, историю посещаемости и изображения отчётов?\n\n{p}', 'Also delete settings, attendance history and report images?\n\n{p}'),
    'Kelgan vaqt: {v}': ('Время прихода: {v}', 'Arrival time: {v}'),
    'Yangilanish yuklanmoqda...': ('Загружается обновление...', 'Downloading update...'),
    'Davomat — xush kelibsiz': ('Davomat — добро пожаловать', 'Davomat — welcome'),
    'Kunlik hisobot — {sana}': ('Ежедневный отчёт — {sana}', 'Daily report — {sana}'),
    "Guruh: {g} — Telegram'da o'zi ochiladi.": ('Группа: {g} — откроется в Telegram автоматически.', 'Group: {g} — opens in Telegram automatically.'),
    "Guruh havolasi kiritilmagan — yuborishdan oldin guruhni Telegram'da o'zingiz oching (yoki Sozlamalarga havolani kiriting).": ('Ссылка на группу не указана — перед отправкой откройте группу в Telegram сами (или укажите ссылку в Настройках).', 'No group link set — open the group in Telegram yourself before sending (or add the link in Settings).'),
    "Davomat — tayyor ishlar ro'yxati": ('Davomat — список готовых работ', 'Davomat — saved tasks list'),
    'Davomat — oylik hisobot': ('Davomat — месячный отчёт', 'Davomat — monthly report'),
    'Davomat — sozlamalar': ('Davomat — настройки', 'Davomat — settings'),
    'Asosiy': ('Основное', 'General'),
    'Ism-familiya:': ('Имя и фамилия:', 'Full name:'),
    'Guruh': ('Группа', 'Group'),
    'Guruh havolasi:': ('Ссылка на группу:', 'Group link:'),
    'Ish vaqti va eslatma': ('Рабочее время и напоминание', 'Working hours and reminder'),
    'Ish boshlanishi:': ('Начало работы:', 'Work starts at:'),
    '(oylik hisobotda kechikish shundan hisoblanadi)': ('(от него считается опоздание в месячном отчёте)', '(lateness in the monthly report is counted from this)'),
    'Eslatma vaqti:': ('Время напоминания:', 'Reminder time:'),
    "(«Keldim» bosilgan kuni, hisobot yuborilmagan bo'lsa)": ('(в день, когда нажато «Пришёл», если отчёт не отправлен)', '(on days you pressed «Arrived», if the report is not sent)'),
    'Takrorlash (daq):': ('Повтор (мин):', 'Repeat (min):'),
    '(yuborilmaguncha har necha daqiqada)': ('(каждые сколько минут, пока не отправлен)', '(every how many minutes until sent)'),
    'Dam olish chegarasi:': ('Граница выходного:', 'Day-off cutoff:'),
    '(shu vaqtgacha «Keldim» bosilmasa — dam olish kuni)': ('(если до этого времени не нажато «Пришёл» — выходной)', '(if «Arrived» is not pressed by then — day off)'),
    'Hisobot': ('Отчёт', 'Report'),
    'Rasm fayli nomi:': ('Имя файла изображения:', 'Image file name:'),
    'Xabar matni:': ('Текст сообщения:', 'Message text:'),
    'Telegram oynasi faol emas — hech narsa yuborilmadi.': ('Окно Telegram не активно — ничего не отправлено.', 'The Telegram window is not active — nothing was sent.'),
    "Ochiq chatni yopib bo'lmadi — hech narsa yuborilmadi.": ('Не удалось закрыть открытый чат — ничего не отправлено.', 'Could not close the open chat — nothing was sent.'),
    "Guruh havola orqali ochilmadi (havola eskirgan yoki guruhga a'zo emassiz). Hech narsa yuborilmadi — Sozlamalardagi guruh havolasini tekshiring.": ('Группа не открылась по ссылке (ссылка устарела или вы не участник). Ничего не отправлено — проверьте ссылку на группу в Настройках.', 'The group did not open from the link (the link expired or you are not a member). Nothing was sent — check the group link in Settings.'),
    'Izoh maydoni topilmadi.': ('Поле подписи не найдено.', 'Caption field not found.'),
    "Izoh to'g'ri yozilmadi: «{q}».": ('Подпись записалась неверно: «{q}».', 'The caption was not entered correctly: «{q}».'),
    '«Yuborish» tugmasi topilmadi.': ('Кнопка «Отправить» не найдена.', 'The «Send» button was not found.'),
    "O'rnatib bo'lmadi:\n{e}": ('Не удалось установить:\n{e}', 'Installation failed:\n{e}'),
    '{sana} kunlik hisobot': ('{sana} ежедневный отчёт', '{sana} daily report'),
    "Bugun «Keldim» bosilmagan. Avval «Keldim» ni bosing (yoki hisobot oynasida kelgan vaqtni qo'lda yozing).": ('Сегодня не нажато «Пришёл». Сначала нажмите «Пришёл» (или впишите время прихода вручную в окне отчёта).', '«Arrived» was not pressed today. Press «Arrived» first (or type the arrival time in the report window).'),
    "GitHub'da yangi versiya bor: {t}.\n(Ishlab chiqish nusxasi — o'zi yangilanmaydi.)": ('На GitHub есть новая версия: {t}.\n(Копия разработчика — не обновляется сама.)', 'A new version is on GitHub: {t}.\n(Developer copy — does not update itself.)'),
    'Bugun dam olish kuni («Keldim» bosilmagan) — hisobot yuborilmaydi.': ('Сегодня выходной («Пришёл» не нажато) — отчёт не отправляется.', 'Today is a day off («Arrived» not pressed) — no report is sent.'),
    'yuborilgan ({v})': ('отправлен ({v})', 'sent ({v})'),
    'yuborilmagan': ('не отправлен', 'not sent'),
    'Hisobot «{g}» guruhiga yuborildi.': ('Отчёт отправлен в группу «{g}».', 'The report was sent to «{g}».'),
    'Telegram orqali yuborish': ('Отправка через Telegram', 'Send via Telegram'),
    "✏ O'zgartirish": ('✏ Изменить', '✏ Edit'),
    "🗑 O'chirish": ('🗑 Удалить', '🗑 Delete'),
    '▲ Yuqoriga': ('▲ Вверх', '▲ Up'),
    '▼ Pastga': ('▼ Вниз', '▼ Down'),
    'Guruhni tanlang': ('Выберите группу', 'Choose a group'),
    "Bugun {v} da «Keldim» bosilgan.\nKelgan vaqtni hozirgi vaqtga o'zgartiraymi?": ('Сегодня «Пришёл» нажато в {v}.\nИзменить время прихода на текущее?', '«Arrived» was pressed today at {v}.\nChange the arrival time to now?'),
    'Hozir yangilaymi? (bir necha soniya)': ('Обновить сейчас? (несколько секунд)', 'Update now? (a few seconds)'),
    "Yangilab bo'lmadi:\n{e}": ('Не удалось обновить:\n{e}', 'Update failed:\n{e}'),
    'Ism-familiyangizni yozing.': ('Введите имя и фамилию.', 'Enter your full name.'),
    "Guruh havolasi noto'g'ri. Masalan: https://t.me/c/1234567890/15 yoki https://t.me/+AbCdEf...": ('Неверная ссылка на группу. Например: https://t.me/c/1234567890/15 или https://t.me/+AbCdEf...', 'Invalid group link. For example: https://t.me/c/1234567890/15 or https://t.me/+AbCdEf...'),
    "Vaqtni SS:DD ko'rinishida yozing (masalan 09:00).": ('Введите время в формате ЧЧ:ММ (например 09:00).', 'Enter the time as HH:MM (for example 09:00).'),
    'Hisobot:': ('Отчёт:', 'Report:'),
    "Kelgan va ketgan vaqtni SS:DD ko'rinishida yozing (masalan 09:00).": ('Введите время прихода и ухода в формате ЧЧ:ММ (например 09:00).', 'Enter arrival and departure times as HH:MM (for example 09:00).'),
    'Kamida bitta bajarilgan ishni yozing.': ('Впишите хотя бы одну выполненную работу.', 'Enter at least one completed task.'),
    'Hisobot Telegram orqali yuborildi.': ('Отчёт отправлен через Telegram.', 'The report was sent via Telegram.'),
    "Ro'yxatdan ishni tanlang va pastda yangi matnni yozing.": ('Выберите работу в списке и впишите новый текст внизу.', 'Select a task in the list and type the new text below.'),
    'Telefon (+998...):': ('Телефон (+998...):', 'Phone (+998...):'),
    '— tanlanmagan': ('— не выбрана', '— not selected'),
    "Telefon raqami noto'g'ri: {t}\nMasalan: +998901234567": ('Неверный номер телефона: {t}\nНапример: +998901234567', 'Invalid phone number: {t}\nFor example: +998901234567'),
    'api_id (raqam), api_hash va telefonni yozing.': ('Введите api_id (число), api_hash и телефон.', 'Enter api_id (a number), api_hash and phone.'),
    'Telegram ilovasiga kelgan kodni yozing:': ('Введите код, пришедший в Telegram:', 'Enter the code sent to your Telegram:'),
    "Vaqtlarni SS:DD ko'rinishida yozing (masalan 17:45).": ('Введите время в формате ЧЧ:ММ (например 17:45).', 'Enter times as HH:MM (for example 17:45).'),
    'Takrorlash — 1 dan 240 gacha daqiqa.': ('Повтор — от 1 до 240 минут.', 'Repeat — from 1 to 240 minutes.'),
    'Keldim': ('Пришёл', 'Arrived'),
    "Soat {v} dan o'tdi — bugun dam olish kuni deb hisoblangan.\nBaribir «Keldim» deb belgilaymi?": ('Уже {v} — сегодня считается выходным.\nВсё равно отметить «Пришёл»?', 'It is past {v} — today is counted as a day off.\nMark «Arrived» anyway?'),
    'Xush kelibsiz! Bir marta sozlab olamiz.': ('Добро пожаловать! Настроим один раз.', "Welcome! Let's set things up once."),
    'Ism-familiyangiz:': ('Ваши имя и фамилия:', 'Your full name:'),
    '(hisobot rasmida va izohda chiqadi)': ('(будет на изображении отчёта и в подписи)', '(shown on the report image and in the caption)'),
    "Guruhdagi istalgan xabar ustida o'ng tugma → «Copy Message Link»\n(yoki taklif havolasi t.me/+...). Ixtiyoriy — bo'lsa guruh o'zi ochiladi.": ('Правый клик по любому сообщению группы → «Копировать ссылку»\n(или пригласительная ссылка t.me/+...). Необязательно — если есть, группа откроется сама.', 'Right-click any message in the group → «Copy Message Link»\n(or an invite link t.me/+...). Optional — if set, the group opens automatically.'),
    'Ish boshlanish vaqti:': ('Начало рабочего дня:', 'Work start time:'),
    'Boshlash': ('Начать', 'Start'),
    "Ishlar ro'yxati": ('Список работ', 'Tasks list'),
    'Oylik hisobot': ('Месячный отчёт', 'Monthly report'),
    'Sozlamalar': ('Настройки', 'Settings'),
    'Ishga kelgan vaqtim:': ('Время прихода:', 'Arrival time:'),
    '(«Keldim» bosilgan vaqt)': ('(время нажатия «Пришёл»)', '(when «Arrived» was pressed)'),
    "Bajarilgan ishlar (o'ngdagi ro'yxatdan tanlang yoki o'zingiz yozing):": ('Выполненные работы (выберите из списка справа или впишите сами):', 'Completed tasks (pick from the list on the right or type your own):'),
    'Tayyor ishlar': ('Готовые работы', 'Saved tasks'),
    "(ikki marta bosing — qo'shiladi)": ('(двойной щелчок — добавить)', '(double-click to add)'),
    "{n} ta qatorning hammasi to'lgan.": ('Все {n} строк заполнены.', 'All {n} rows are filled.'),
    "← Qo'shish": ('← Добавить', '← Add'),
    "Ro'yxatni tahrirlash": ('Редактировать список', 'Edit list'),
    'Ishdan ketgan vaqtim:': ('Время ухода:', 'Departure time:'),
    "API orqali yuborib bo'lmadi:\n{e}\n\nTelegram Desktop orqali yuboraymi?": ('Не удалось отправить через API:\n{e}\n\nОтправить через Telegram Desktop?', 'Could not send via the API:\n{e}\n\nSend via Telegram Desktop instead?'),
    'Keyinroq': ('Позже', 'Later'),
    'Saqlash': ('Сохранить', 'Save'),
    'Yuborish ➤': ('Отправить ➤', 'Send ➤'),
    "Hisobotga yozilishi mumkin bo'lgan ishlar. Hisobot oynasida shu ro'yxatdan tanlaysiz.": ('Работы, которые можно вписать в отчёт. В окне отчёта вы выбираете из этого списка.', 'Tasks you can put in the report. In the report window you pick from this list.'),
    "➕ Qo'shish": ('➕ Добавить', '➕ Add'),
    "Yangi ishni pastga yozib Enter yoki «Qo'shish» ni bosing.": ('Впишите новую работу внизу и нажмите Enter или «Добавить».', 'Type a new task below and press Enter or «Add».'),
    'Oy:': ('Месяц:', 'Month:'),
    "Fayl boshqa dasturda ochiq turibdi — Excel'ni yopib, qayta urinib ko'ring:\n{p}": ('Файл открыт в другой программе — закройте Excel и попробуйте снова:\n{p}', 'The file is open in another program — close Excel and try again:\n{p}'),
    "Excel'ga saqlash va ochish": ('Сохранить в Excel и открыть', 'Save to Excel and open'),
    'Havolani sinash': ('Проверить ссылку', 'Test the link'),
    "Bo'sh qoldirilsa: «{n}». {{sana}}, {{ism}} ishlatish mumkin.": ('Если пусто: «{n}». Можно использовать {{sana}}, {{ism}}.', 'If empty: «{n}». You can use {{sana}}, {{ism}}.'),
    'Kengaytirilgan: Telegram API orqali yuborish': ('Дополнительно: отправка через Telegram API', 'Advanced: send via the Telegram API'),
    "Xabar sizning akkauntingizdan to'g'ridan-to'g'ri ketadi (Telegram Desktop shart emas).\nmy.telegram.org → API development tools dan api_id va api_hash oling.": ('Сообщение уходит напрямую с вашего аккаунта (Telegram Desktop не нужен).\nПолучите api_id и api_hash на my.telegram.org → API development tools.', 'The message goes straight from your account (Telegram Desktop not needed).\nGet api_id and api_hash at my.telegram.org → API development tools.'),
    '✔ Kirildi': ('✔ Вход выполнен', '✔ Signed in'),
    "Kirib bo'lmadi:\n{e}": ('Не удалось войти:\n{e}', 'Sign-in failed:\n{e}'),
    'Avval Telegramga kiring.': ('Сначала войдите в Telegram.', 'Sign in to Telegram first.'),
    "Guruhlarni olib bo'lmadi:\n{e}": ('Не удалось получить группы:\n{e}', 'Could not get groups:\n{e}'),
    'Telegramga kirish': ('Войти в Telegram', 'Sign in to Telegram'),
    'Guruhni tanlash': ('Выбрать группу', 'Choose group'),
    'Versiya {v}': ('Версия {v}', 'Version {v}'),
    'Yangilanishni tekshirish': ('Проверить обновления', 'Check for updates'),
    '(yopsangiz pastki panelda qoladi)': ('(если закрыть — останется на панели задач)', '(closing keeps it on the taskbar)'),
    'Ketdim:': ('Ушёл:', 'Left:'),
    '✔ Bugungi hisobot {v} da yuborilgan. Qayta yuborish mumkin.': ('✔ Сегодняшний отчёт отправлен в {v}. Можно отправить снова.', "✔ Today's report was sent at {v}. You can send it again."),
    "Yuborib bo'lmadi:\n{e}\n\nRasm saqlandi: {p}": ('Не удалось отправить:\n{e}\n\nИзображение сохранено: {p}', 'Could not send:\n{e}\n\nImage saved: {p}'),
    "Telegram'da hisobot guruhini oching,\nkeyin «Yuborish ➤» ni bosing.": ('Откройте в Telegram группу для отчётов,\nзатем нажмите «Отправить ➤».', 'Open the report group in Telegram,\nthen press «Send ➤».'),
    'Izoh: «{i}»': ('Подпись: «{i}»', 'Caption: «{i}»'),
    "Maslahat: Sozlamalarga guruh havolasini kiritsangiz, guruh o'zi ochiladi.": ('Совет: укажите ссылку на группу в Настройках — группа будет открываться сама.', 'Tip: add the group link in Settings and the group will open automatically.'),
    "Yuborib bo'lmadi:\n{e}": ('Не удалось отправить:\n{e}', 'Could not send:\n{e}'),
    'Bekor': ('Отмена', 'Cancel'),
    'Telegram Desktop orqali': ('Через Telegram Desktop', 'Via Telegram Desktop'),
    'Ish kunlari: {n}': ('Рабочих дней: {n}', 'Working days: {n}'),
    'Jami ishlagan vaqt: {v}': ('Всего отработано: {v}', 'Total worked: {v}'),
    "O'rtacha kunlik: {v}": ('В среднем за день: {v}', 'Daily average: {v}'),
    'Kech qolgan kunlar: {n} (jami {d} daq, ish boshlanishi {b})': ('Дней с опозданием: {n} (всего {d} мин, начало работы {b})', 'Days late: {n} (total {d} min, work starts {b})'),
    'Hisobot yuborilmagan kunlar: {n}': ('Дней без отчёта: {n}', 'Days without a report: {n}'),
    '✔ Kirilgan': ('✔ Вход выполнен', '✔ Signed in'),
    'Ikki bosqichli tekshiruv paroli:': ('Пароль двухэтапной проверки:', 'Two-step verification password:'),
    'Tanlash': ('Выбрать', 'Select'),
    "Ilovani o'chirish": ('Удалить программу', 'Uninstall the app'),
    'Ketdim': ('Ушёл', 'Left'),
    'Keldim:': ('Пришёл:', 'Arrived:'),
    "⏰ Kunlik hisobotni yuborish vaqti bo'ldi!": ('⏰ Пора отправить ежедневный отчёт!', '⏰ Time to send the daily report!'),
    'Sizda eng yangi versiya ({v}).': ('У вас последняя версия ({v}).', 'You have the latest version ({v}).'),
    "Yangilanishni tekshirib bo'lmadi:\n{e}": ('Не удалось проверить обновления:\n{e}', 'Could not check for updates:\n{e}'),
    'Ochish': ('Открыть', 'Open'),
    '✅ Keldim': ('✅ Пришёл', '✅ Arrived'),
    '🏁 Ketdim': ('🏁 Ушёл', '🏁 Left'),
    'Hisobotlar papkasi': ('Папка отчётов', 'Reports folder'),
    'Chiqish': ('Выход', 'Exit'),
})

if __name__ == "__main__":
    main()
