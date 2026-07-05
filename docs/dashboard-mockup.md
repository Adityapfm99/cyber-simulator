# Mockup — Exercise Director Dashboard (Spektek §2)

Mockup tampilan **Exercise Director Dashboard** sebagai HTML statis dengan data
contoh. Ini menggambarkan susunan antarmuka platform (topologi + scoring + kill
switch). Tampilan aplikasi sebenarnya bersifat **real-time** (polling tiap ~2,5 dtk).

## Cara membuka

Buka file [`dashboard-mockup.html`](dashboard-mockup.html) langsung di browser
(dobel-klik). File sepenuhnya mandiri (CSS inline, tanpa dependensi eksternal).

> Untuk menjadikannya gambar: buka di browser lalu Save as / screenshot, atau
> print-to-PDF.

## Anatomi layar

```
┌──────────────────────────────────────────────────────────────────────┐
│ Top bar: status guardrail (ISOLATED, SYSTEMS NOMINAL) · peran · KILL   │
├───────────────┬──────────────────────────────────┬────────────────────┤
│ Scenarios     │ Header scenario + Deploy/Destroy  │ Inject Event       │
│ (pilih/buat)  │ Live Topology (SVG)               │ Containment        │
│               │ SOC / SIEM Live Feed              │ Incidents & Scoring│
└───────────────┴──────────────────────────────────┴────────────────────┘
```

| Wilayah | Fungsi | Spektek |
|---|---|---|
| **Top bar — pill guardrail** | Status isolasi & kill switch selalu terlihat | §4 |
| **Top bar — 🛑 KILL SWITCH** | Hentikan seluruh VM latihan seketika | §4 |
| **Scenarios (kiri)** | Multi-scenario: pilih, buat dari template, deploy/destroy | §2 |
| **Live Topology (tengah)** | Visualisasi topologi real-time; node `compromised` menyala merah | §2 |
| **SOC / SIEM Live Feed** | Log palsu Firewall/EDR/DNS/Proxy; baris serangan disorot | §3 |
| **Inject Event (kanan)** | Injeksi serangan dummy manual/terjadwal | §2/§3 |
| **Containment** | Analis SOC: quarantine/restore node terdampak | §3 |
| **Incidents & Scoring** | Metrik TTD/TTT/TTC/TTR + skor; unduh AAR | §2 |

## Detail pada mockup

- Scenario **"Enterprise SOC Defense — Demo"** dalam status `running`.
- Node **workstation-01** ditampilkan `compromised` (merah) akibat injeksi
  `ransomware`; feed SOC menampilkan baris `mass_file_rename … (DUMMY drill)`.
- Panel **Incidents** menunjukkan insiden dengan TTD/TTT tercapai (hijau) dan
  TTC/TTR belum (kuning), skor 75/100 — analis tinggal menekan **contain**.

## Warna status node

| Warna | Status |
|---|---|
| 🟢 Hijau | `up` (sehat) |
| 🔴 Merah | `compromised` |
| 🟠 Oranye | `quarantined` |
| ⚪ Abu | `halted` (kill switch) |

Lihat [`../README.md`](../README.md) untuk menjalankan aplikasi sebenarnya.
