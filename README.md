# GlassPin

Website inspirasi bergaya **glassmorphism elegan** (charcoal & champagne — tanpa neon),
dengan ikon **SVG resmi Lucide** (lisensi ISC) dan tanpa emoji. Semua fitur **tanpa login**.

## Cara menjalankan

```bash
python3 server.py
```

Buka `http://localhost:8000` (port bisa diubah lewat env `PORT`).

## Fitur

| Fitur | Keterangan |
|---|---|
| Beranda (feed) | Kurasi otomatis topik populer, tampilan masonry |
| Pencarian | Cari gambar/video — kueri Indonesia otomatis diekspansi ke Inggris |
| Filter | Semua / Foto / Video |
| Detail pin | Gambar/video besar, judul, deskripsi, kreator, lisensi, sumber, tag |
| Unduh | Tombol unduh media (proxy server, bebas CORS) |
| Komentar | Tanpa login — tersimpan di `data/comments.json` |
| Simpan & Suka | Koleksi tersimpan (localStorage) |
| Navigasi keyboard | Esc tutup, panah kiri/kanan berpindah pin |
| Pencarian saran | Riwayat + tren, tombol chip tren |
| Infinite scroll | Muat lebih banyak otomatis + tombol manual |

## Sumber data

- **Openverse** — gratis, tanpa API key
- **Wikimedia Commons** — gratis, tanpa API key
- **Pexels / Pixabay** — opsional (key gratis, isi di menu Pengaturan) untuk hasil lebih kaya & video

## Struktur

```
glasspin/
├── server.py            # backend Python stdlib (API + proxy unduh + komentar)
├── data/comments.json   # penyimpanan komentar
└── public/
    ├── index.html       # antarmuka + sprite ikon Lucide
    ├── css/style.css    # desain glassmorphism elegan
    └── js/app.js        # logika aplikasi
```

## Catatan

- Konten berasal dari sumber terbuka; hak cipta milik pencipta masing-masing.
- Ikon oleh **Lucide** (https://lucide.dev) — ISC License.
