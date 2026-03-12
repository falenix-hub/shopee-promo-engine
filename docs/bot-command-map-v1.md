# Bot Command Map V1

## Manual mode
- `/start`
- `/help`
- `/preview <short_link> | <nama produk> | <category> | <reason> | <harga_lama> | <harga_sekarang> | <rating> | <sold_count> | <hemat_nominal/hemat_percent>`
- `/post <short_link> | <nama produk> | <category> | <reason> | <harga_lama> | <harga_sekarang> | <rating> | <sold_count> | <hemat_nominal/hemat_percent>`
- `/add_watch <short_link> | <label> | <category> | <reason> | <harga_lama> | <harga_sekarang>`
- `/list_watch`

## Auto mode
- `/auto_on`
- `/auto_off`
- `/auto_status`
- `/run_once`

## Batasan V1
- manual mode hanya menerima short affiliate link `https://s.shopee.co.id/...`
- manual mode sekarang menuntut metadata produk lengkap agar caption rapi dan tidak generik
- auto mode masih berbasis watchlist/manual seeded items
- full scraping harga live dan custom-link resolver otomatis belum diaktifkan penuh
