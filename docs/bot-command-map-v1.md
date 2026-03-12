# Bot Command Map V1

## Manual mode
- `/start`
- `/help`
- `/preview <short_affiliate_link>`
- `/post <short_affiliate_link>`
- `/add_watch <short_link> | <label> | <category> | <reason> | <harga_lama> | <harga_sekarang>`
- `/list_watch`

## Auto mode
- `/auto_on`
- `/auto_off`
- `/auto_status`
- `/run_once`

## Batasan V1
- manual mode hanya menerima short affiliate link `https://s.shopee.co.id/...`
- metadata produk dicoba di-generate otomatis dari short link dan halaman produk Shopee
- jika metadata tertentu tidak tersedia, bot akan fallback ke caption yang tetap rapi tapi lebih generik
- auto mode masih berbasis watchlist/manual seeded items
- full scraping harga live dan custom-link resolver otomatis belum diaktifkan penuh
