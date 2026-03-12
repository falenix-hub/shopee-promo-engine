# Bot Command Map V1 (Simple)

## Tujuan
Bot fokus hanya untuk posting cepat ke channel `Pemburu Promo Shopee` tanpa banyak mode yang bikin rawan error.

## Commands
- `/start`
- `/help`
- `/preview <short_affiliate_link>`
- `/post <short_affiliate_link>`

## Input valid
Hanya menerima short affiliate link Shopee seperti:
- `https://s.shopee.co.id/...`

## Perilaku bot
### /preview
- ambil metadata semampunya dari short link
- generate caption rapi
- tampilkan ke user tanpa post ke channel

### /post
- ambil metadata semampunya dari short link
- generate caption rapi
- kirim ke channel Telegram
- balas message_id hasil post

## Batasan V1
- tidak ada auto mode dulu
- tidak ada watchlist dulu
- tidak ada queue dulu
- fokus ke kestabilan manual post
