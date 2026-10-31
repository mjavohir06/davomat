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

## Ishlatish

- Ishga kelganda **✅ Keldim**, ketayotganda **🏁 Ketdim** ni bosing.
- «Ketdim» dan keyin hisobot oynasi ochiladi: ishlarni tanlang yoki yozing → **Yuborish ➤**.
  Ilova Telegram'da guruhni o'zi ochadi va hisobotni rasm + izoh bilan yuboradi.
- «Keldim» bosilgan kuni eslatma vaqtidan boshlab hisobot yuborilmaguncha eslatib turadi.
  «Keldim» bosilmagan kun dam olish kuni hisoblanadi.
- **Oylik hisobot** — oy bo'yicha Excel jadval: kelish/ketish, ishlagan soat, kechikishlar.
- Yangi versiya chiqsa, ilova o'zi taklif qiladi va bir bosishda yangilanadi.
- O'chirish: Sozlamalar → «Ilovani o'chirish» yoki Windows «Ilovalar» ro'yxatidan.

Ma'lumotlar `%APPDATA%\Davomat` da saqlanadi.

## Ishlab chiquvchi uchun

- `davomat.pyw` — butun ilova (Python 3.14, `.venv`: telethon, pystray, pillow, openpyxl, comtypes, pyinstaller).
- `yigish.ps1` — `dist\Davomat.exe` ni yig'adi va ichidagi qismlarni sinaydi.
- `chiqarish.ps1 "izoh"` — `VERSIYA` bo'yicha GitHub reliz yaratadi; o'rnatilgan ilovalar shundan yangilanadi.
- Telegram Desktop orqali yuborish UI Automation bilan ishlaydi va har qadamni tekshiradi
  (chat yopiladi → guruh havola orqali ochiladi → rasm joylanadi → izoh tekshiriladi → Send).
  Biror qadam o'xshamasa, hech narsa yubormaydi.
