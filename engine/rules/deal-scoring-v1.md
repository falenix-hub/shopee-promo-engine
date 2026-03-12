# Deal Scoring V1

## Objective
Memilih deal yang layak **auto-post** ke channel `Pemburu Promo Shopee` tanpa membuat channel berubah jadi spam dump.

## Struktur skor
Total skor akhir: **0 - 100**

Komponen:
- Discount Score: 0 - 30
- Trust Score: 0 - 20
- Conversion Score: 0 - 20
- Freshness Score: 0 - 10
- Commission Score: 0 - 10
- Spam Penalty: 0 sampai -20

---

## 1. Discount Score (0 - 30)
Menilai seberapa menarik perubahan harga.

### Rule dasar
- drop >= 10% → +10
- drop >= 15% → +15
- drop >= 20% → +20
- drop >= 30% → +25
- harga terendah sejak tracking dimulai → +5 bonus

### Rule nominal
- drop nominal >= Rp20.000 → +5
- drop nominal >= Rp50.000 → +10

Maksimum komponen ini: 30

---

## 2. Trust Score (0 - 20)
Menilai apakah produk/toko cukup aman dipromosikan.

### Rating produk
- rating >= 4.7 → +8
- rating >= 4.8 → +10
- rating < 4.5 → 0

### Sold count
- sold >= 50 → +4
- sold >= 200 → +6
- sold >= 1000 → +8

### Bonus toko/produk stabil
- toko dikenal / sering lolos shortlist → +2

Maksimum komponen ini: 20

---

## 3. Conversion Score (0 - 20)
Menilai potensi produk untuk menarik klik dan pembelian.

### Kategori prioritas
- beauty & skincare → +8
- home living → +8
- gadget accessories → +8
- fashion → +6
- health → +5

### Harga psikologis
- harga <= Rp50.000 → +6
- harga <= Rp100.000 → +4
- harga > Rp300.000 → +1

### Kejelasan use-case
- problem/benefit mudah dipahami → +4 sampai +6

Maksimum komponen ini: 20

---

## 4. Freshness Score (0 - 10)
Menilai apakah deal masih baru dan layak dipost cepat.

- terdeteksi turun hari ini → +5
- pertama kali lolos threshold → +3
- sedang ada momentum campaign/promo besar → +2

Maksimum komponen ini: 10

---

## 5. Commission Score (0 - 10)
Karena ini affiliate, komisi tetap penting tapi tidak boleh mengalahkan kualitas deal.

- affiliate aktif → +4
- komisi kategori/produk cukup baik → +3 sampai +6

Maksimum komponen ini: 10

---

## 6. Spam Penalty (0 sampai -20)
Mencegah channel jadi robotik.

- produk sama dipost < 72 jam lalu → -10
- toko sama terlalu sering muncul hari ini → -4
- kategori sama mendominasi feed → -3
- deal tidak cukup beda dari post sebelumnya → -5

---

## Threshold V1
### Auto-post jika:
- final_score >= 70
- rating >= 4.7
- sold_count >= 50
- drop_percent >= 10 ATAU drop_amount >= 20000
- belum dipost dalam 72 jam terakhir

### Simpan ke shortlist jika:
- final_score 55 - 69

### Skip jika:
- final_score < 55
- produk meragukan / noise / misleading

---

## Catatan penting
V1 harus **selective**. Lebih baik sedikit deal tapi tajam, daripada banyak post yang merusak trust channel.
