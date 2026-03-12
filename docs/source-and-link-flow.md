# Source Product + Affiliate Link Flow

## Flow V1 yang dipilih

### Step 1 — kandidat produk
Kandidat produk masuk dari:
- Penawaran Produk Shopee Affiliate
- watchlist manual kategori prioritas
- halaman toko/kategori/promo Shopee tertentu

### Step 2 — pengambilan data
Data minimal yang perlu diambil:
- nama produk
- harga sekarang
- URL produk
- kategori
- nama toko
- rating
- sold count

### Step 3 — tracking harga
Simpan histori harga per produk untuk mendeteksi:
- penurunan harga
- harga terendah yang pernah terlihat
- perubahan signifikan

### Step 4 — scoring deal
Hitung skor berdasarkan:
- discount score
- trust score
- conversion score
- freshness score
- anti-spam / anti-duplicate rule

### Step 5 — affiliate link generation
Gunakan `Custom Link` Shopee Affiliate:
- masukkan URL produk/toko/promo
- tambahkan tag tracking
- hasilkan affiliate link final

### Step 6 — Telegram publishing
Format post:
- headline promo
- nama produk
- harga lama -> harga sekarang
- hemat berapa
- alasan singkat
- link affiliate

## Jalur implementasi teknis
### Mode awal
- semi-browser automation / browser relay
- SQLite lokal
- publisher bot Telegram

### Jalur yang belum dipakai
- Open API resmi Shopee Affiliate (belum tersedia pada akun ini)

## Tagging recommendation
Contoh tag untuk custom link:
- category_beauty
- channel_telegram
- promo_drop
- source_offer
- dailybatch_01
