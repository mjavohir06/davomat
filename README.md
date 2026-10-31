# Davomat

Kunlik ish hisobotini (kelgan/ketgan vaqt va bajarilgan ishlar jadvali) rasm ko'rinishida Telegram guruhga
yuboruvchi Windows ilova. Til: o'zbek, rus, ingliz.

## O'rnatish (xodimlar uchun)

1. [Releases](https://github.com/mjavohir06/davomat/releases/latest) dan **Davomat.exe** ni yuklab oling.
2. Uni ochib yuboring. Windows «noma'lum dastur» desa: **Подробнее / More info → Выполнить в любом случае / Run anyway**.
3. Ilova o'zi o'rnatiladi: ish stolida «Davomat» yorlig'i paydo bo'ladi, kompyuter yonganda o'zi ishga tushadi.
   Admin huquqi kerak emas.
4. Birinchi oynada tilni, ism-familiyangizni va guruh havolasini kiriting.
   Guruh havolasi: Telegram'da guruhdagi istalgan xabar ustida o'ng tugma → **Copy Message Link**.

Kompyuterda **Telegram Desktop** o'rnatilgan va akkauntga kirilgan bo'lishi kerak.

## O'rnatish (MacBook)

1. [Releases](https://github.com/mjavohir06/davomat/releases/latest) dan yuklab oling:
    **Davomat-mac-arm64.zip** — M1/M2/M3/M4 (Apple Silicon), **Davomat-mac-intel.zip** — eski Intel MacBook'lar.
    Qaysi biri ekanini bilish: Apple menyusi → About This Mac → «Chip: Apple M…» bo'lsa arm64, «Processor: Intel» bo'lsa intel.
2. Zipni oching va **Davomat.app** ni **Applications** (Программы) papkasiga sudrab o'tkazing.
3. Birinchi marta ochganda macOS «Apple tekshira olmadi» deydi (ilova Apple'da imzolanmagan):
    **System Settings → Privacy & Security** → pastda «Davomat was blocked» yonidagi **Open Anyway** → parolni kiriting.
    (Yoki Terminal'da bir marta: `xattr -dr com.apple.quarantine /Applications/Davomat.app`)
4. Til, ism-familiya va guruh havolasini kiriting. Ilova Mac yonganda o'zi ishga tushadi va o'zi yangilanadi.

Mac'da yuborish:
- **To'liq avtomatik** — Sozlamalar → «Kengaytirilgan: Telegram API» (bir marta: my.telegram.org dan api_id/api_hash,
  telefon raqam va Telegram'ga kelgan kod). Shundan keyin «Yuborish ➤» hisobotni o'zi yuboradi.
- **Yarim qo'lda** (API'siz) — «Yuborish ➤» guruhni ochadi va rasmni nusxalaydi: ⌘V → «Izohni nusxalash» → ⌘V → Enter.

Mac'da soat yonidagi belgi o'rniga ekran tepasidagi **Davomat** menyusi va Dock belgisi ishlatiladi.

## Ishlatish

- Ishga kelganda **✅ Keldim**, ketayotganda **🏁 Ketdim** ni bosing.
- «Ketdim» dan keyin hisobot oynasi ochiladi: ishlarni tanlang yoki yozing → **Yuborish ➤**.
  Ilova Telegram'da guruhni o'zi ochadi va hisobotni rasm + izoh bilan yuboradi.
- «Keldim» bosilgan kuni eslatma vaqtidan boshlab hisobot yuborilmaguncha eslatib turadi.
  «Keldim» bosilmagan kun dam olish kuni hisoblanadi.
- **Oylik hisobot** — oy bo'yicha Excel jadval: kelish/ketish, ishlagan soat, kechikishlar.
- Yangi versiya chiqsa, ilova o'zi taklif qiladi va bir bosishda yangilanadi.
- O'chirish: Sozlamalar → «Ilovani o'chirish» yoki Windows «Ilovalar» ro'yxatidan.

Ma'lumotlar Windows'da `%APPDATA%\Davomat`, Mac'da `~/Library/Application Support/Davomat` da saqlanadi.

## Ishlab chiquvchi uchun

- `davomat.pyw` — butun ilova (Python 3.14, `.venv`: telethon, pystray, pillow, openpyxl, comtypes, pyinstaller).
- `yigish.ps1` — `dist\Davomat.exe` ni yig'adi va ichidagi qismlarni sinaydi.
- `chiqarish.ps1 "izoh"` — `VERSIYA` bo'yicha GitHub reliz yaratadi; o'rnatilgan ilovalar shundan yangilanadi.
- Telegram Desktop orqali yuborish UI Automation bilan ishlaydi va har qadamni tekshiradi
  (chat yopiladi → guruh havola orqali ochiladi → rasm joylanadi → izoh tekshiriladi → Send).
  Biror qadam o'xshamasa, hech narsa yubormaydi.
