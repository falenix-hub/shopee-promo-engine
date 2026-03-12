# Pemburu Promo Shopee Engine — V1 Blueprint

## Objective
Membangun engine automation yang:
1. mengambil kandidat produk Shopee affiliate
2. mendeteksi penurunan harga / deal layak
3. menghasilkan affiliate link dengan tag tracking
4. memformat caption promo
5. auto-post ke channel Telegram `Pemburu Promo Shopee`

## Constraints nyata
- akun Shopee Affiliate saat ini **tidak punya akses Open API**
- Product Feed kreatif saat ini **kosong**
- jalur utama V1 harus memakai **browser/UI flow**
- Telegram publisher bot sudah tersedia: `@pemburu_promo_shopee_bot`

## Source of truth V1
### Product source
- halaman `Penawaran Produk`
- watchlist manual kategori prioritas
- halaman produk/toko/kategori Shopee yang diubah lewat `Custom Link`

### Affiliate link source
- halaman `Link Khusus (Custom Link)`
- tag tracking dipakai untuk kategori, channel, batch, atau eksperimen

## Kategori prioritas awal
1. Beauty & skincare
2. Home living
3. Gadget / aksesoris elektronik
4. Fashion wanita-pria
5. Health

## Arsitektur modul
1. `collector` — ambil kandidat produk
2. `tracker` — simpan harga & perubahan
3. `scorer` — hitung kelayakan deal
4. `linker` — generate affiliate custom link + tag
5. `publisher` — format & kirim ke Telegram
6. `history` — simpan riwayat post agar tidak spam/duplikat

## Deal qualification rules awal
- penurunan harga minimal 8-10%
- atau penurunan nominal minimal tertentu
- rating & sold count memadai
- bukan produk blacklist
- belum dipost dalam jangka waktu tertentu
- skor akhir di atas threshold

## Telegram post format awal
- headline promo
- nama produk
- harga lama -> harga baru
- persen / nominal hemat
- 1 kalimat alasan menarik
- CTA pendek
- affiliate link

## Database awal (SQLite)
### Table: products
- product_id
- name
- category
- shop_name
- rating
- sold_count
- last_seen_price
- lowest_seen_price
- affiliate_url
- source_url
- last_checked_at

### Table: price_history
- product_id
- checked_at
- price

### Table: posts
- product_id
- posted_at
- price_at_post
- drop_percent
- telegram_message_id
- tags_used

## Operasi harian V1
1. collector mengambil kandidat
2. tracker membandingkan harga sekarang vs history
3. scorer memberi skor deal
4. linker membuat affiliate link bertag
5. publisher auto-post ke channel
6. posts table mencatat riwayat

## Status saat ini
- channel sudah dibuat manual
- bot publisher sudah dijadikan admin channel
- repo baru sudah tersedia
- flow V1 siap masuk ke tahap implementasi teknis
