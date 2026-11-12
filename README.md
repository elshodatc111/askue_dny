# Hodimlar nazorati - Qashqadaryo HETK

CAS dasturidan olingan Excel fayllar asosida tuman/shahar va brigadalar kesimida aloqa holatini
kuzatish, kunlarni solishtirish (dinamika) va nomma-nom ro'yxatlarni ko'rish uchun veb-dastur.

**Texnologiyalar:** Python (Django), MySQL, ECharts (diagrammalar), Leaflet (xarita). Interfeys faqat o'zbek tilida.

## 1. Birinchi o'rnatish (Windows)

Talab: Python va MySQL o'rnatilgan, MySQL xizmati ishlab turgan bo'lishi kerak.

1. `setup.bat` ni ikki marta bosing. U avtomatik ravishda:
   - virtual muhit yaratadi va kutubxonalarni o'rnatadi,
   - `.env` faylini yaratadi (MySQL: `root`, parolsiz, baza nomi `hodimlar`),
   - MySQL da `hodimlar` bazasini va jadvallarni yaratadi,
   - administrator yaratadi: **login `admin`, parol `Admin@12345`** (kirgach darhol almashtiring).
2. `run.bat` ni bosing. Dastur `http://localhost:8000` da ishga tushadi (waitress serveri).

MySQL paroli yoki manzili boshqacha bo'lsa, `.env` faylini tahrirlang.

## 2. Cloudflare orqali internetga chiqarish

1. `.env` da `CSRF_TRUSTED_ORIGINS=https://sizning-domen.uz` va `HTTPS=1` ni belgilang.
2. Cloudflare Tunnel (cloudflared) ni `http://localhost:8000` ga yo'naltiring.
3. `run.bat` ni Windows Task Scheduler orqali kompyuter yoqilganda avtomatik ishga tushiring.

## 3. Kundalik ish tartibi

1. CAS dan 4 ta faylni yuklab oling: konsentratorlar, GPRS hisoblagichlar, aloqadan chiqib ketgan hisoblagichlar, to'g'ridan-to'g'ri ulanishlar.
2. Administrator sifatida **Fayl yuklash** sahifasiga kiring, fayllarni tashlang va sanani belgilang.
3. Fayl turi ustun nomlariga qaramasdan mazmunidan aniqlanadi (CAS qaysi tilda yuklashidan qat'i nazar).
4. Qayta ishlash orqa fonda bajariladi (1-2 daqiqa). Tayyor bo'lgach ma'lumotlar paydo bo'ladi.

**Hududiy tuzilma** (Area Information Report) birinchi marta yuklanadi: TP lar va brigadalar shundan yaratiladi.
Keyinchalik yangi TP paydo bo'lsa, uni qayta yuklash mumkin (mavjud brigadalar va qo'lda qilingan o'zgarishlarga tegmaydi).

## 4. Sahifalar

| Sahifa | Vazifasi |
|---|---|
| Bosh panel | Asosiy ko'rsatkichlar, animatsion diagrammalar, kunlik dinamika. Tuman tanlansa, brigadalar kesimi |
| Dinamika jadvallari | Ikki sanani tanlab solishtirish: tuman, tanlangach brigadalar va ularga biriktirilgan hodimlar |
| Nomma-nom ro'yxat | Har bir raqam ortidagi qurilmalar. Qidirish, filtr, Excelga yuklash, "yangi paydo bo'lgan / tuzalgan" |
| Xarita | GPS koordinatasi bor qurilmalar, muddat bo'yicha ranglangan |
| Fayl yuklash, Brigadalar, TP ko'chirish, Foydalanuvchilar | Administrator uchun boshqaruv |

Muddat oraliqlari: 1 kungacha, 2-7, 7-30 (8-30), 30-90 (31-90), 90 kundan ortiq. Offline muddati
"oxirgi aloqa vaqti" dan ma'lumot sanasigacha hisoblanadi; aloqadan chiqib ketgan hisoblagichlar uchun CAS dagi "necha kun" ustuni ishlatiladi.

## 5. Rollar

| Rol | Ruxsat |
|---|---|
| Administrator | Hamma narsa, yuklash, brigada va foydalanuvchilarni tahrirlash |
| Viloyat hodimi | Butun viloyatni ko'radi |
| Tuman rahbari | Butun viloyatni ko'radi |
| Tuman hodimi | Faqat o'z tumani |

## 6. Ma'lumotlar saqlanishi

- Jamlama statistika (har kun, har TP bo'yicha) doim saqlanadi.
- Nomma-nom qatorlar `DETAIL_RETENTION_DAYS` (standart 180) kun saqlanadi. Eskilarini tozalash: `tozalash.bat`.
- Brigada o'zgarishlari (TP ko'chirish) statistikaga darhol, barcha kunlar uchun qo'llanadi (joriy biriktirish bo'yicha).

## 7. Keyinga qoldirilganlar

Hodimning dala yozuvlari (foto, izoh, GPS) va mobil (Flutter) ilova. Ma'lumotlar bazasi va API ularga tayyor tuzilgan.

## 8. Loyiha tuzilmasi

```
config/            Django sozlamalari
core/models.py     Tuman, Brigada, Hodim, TP, Yuklama, Kuzatuv, TPSana, Profil
core/services/     importer.py (Excel o'qish), stats.py (statistika), names.py (matn/hodimlar)
core/views.py      sahifalar
core/templates/    HTML shablonlar
core/static/       CSS, JS, ECharts, Leaflet
core/tests.py      avtomatik testlar  (python manage.py test core)
```

Testlar: `venv\Scripts\activate` keyin `python manage.py test core`.


## Ruxsatlar (bo'lim va amaliyotlar)

Har bir foydalanuvchi uchun "Foydalanuvchilar" sahifasida bo'limlar va ularning amaliyotlari (ko'rish, Excel/PDF yuklab olish,
fayl yuklash, brigada tahrirlash va h.k.) alohida belgilanadi. Rol standart ruxsatlarni beradi, administrator esa har bir
hodim uchun ularni qo'shishi yoki olib qo'yishi mumkin. "Foydalanuvchilar" bo'limi faqat administratorda qoladi.
Ko'rish doirasi (qaysi tumanlar) rolga bog'liq: tuman hodimi faqat o'z tumanini ko'radi.

## Yangi ko'rsatkichlar

- **3 kundan ortiq** - oxirgi aloqa ma'lumot sanasidan 2 kun va undan oldin bo'lganlar (12.11 da: 10.11 va undan oldin).
- **30 kundan ortiq** - oxirgi aloqa 31 kun va undan oldin bo'lganlar.
- Dinamika jadvalini Excel va PDF ga yuklab olish mumkin (tugmalar sahifaning yuqori o'ng burchagida).

Yangilashdan keyin `setup.bat` (yoki `python manage.py migrate`) ni qayta ishga tushiring: yangi migratsiya qo'llanadi.
