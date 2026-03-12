# Shopee Affiliate Audit

## Account context
- akun affiliate aktif dan login di browser relay
- username terlihat sebagai `Adelleva_`

## Temuan utama
### 1. Open API
Status: **tidak tersedia untuk akun ini**

Indikasi di halaman Open API:
- `AppID: --`
- `Rahasia: --`
- tombol `Terapkan` nonaktif
- pesan bahwa akun tidak memiliki akses ke Platform Open API Shopee Affiliate

**Implikasi:**
V1 tidak bisa mengandalkan API resmi. Jalur utama harus browser/UI flow.

### 2. Link Khusus (Custom Link)
Status: **tersedia dan usable**

Kemampuan yang terlihat:
- dapat mengubah hingga 5 link sekaligus
- mendukung halaman utama Shopee, halaman produk, halaman promo, halaman toko, dan halaman kategori
- mendukung hingga 5 tag tracking

**Implikasi:**
Ini menjadi jalur inti untuk menghasilkan affiliate link final yang siap dipost ke Telegram.

### 3. Tampilan Produk / Product Feed
Status: **kosong / tidak ada data**

**Implikasi:**
Product Feed bawaan belum bisa dijadikan source kandidat awal.

### 4. Product Offer
Secara struktur menu, modul `Penawaran Produk` tersedia.

**Implikasi:**
Product Offer berpotensi menjadi source kandidat awal bersama watchlist manual, meski perlu automation/browser extraction untuk implementasi V1.

## Kesimpulan arsitektur
Karena kondisi akun saat ini:
- no Open API
- Custom Link available
- Product Feed kosong

Maka flow V1 paling realistis:
1. ambil kandidat produk dari Product Offer + watchlist/manual source
2. cek harga dan histori harga
3. hitung deal score
4. ubah URL ke affiliate custom link bertag
5. auto-post ke Telegram channel
