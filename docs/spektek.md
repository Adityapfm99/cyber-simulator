# Spesifikasi Teknis (Spektek)
## Defensive Cyber Simulator — Cyber Range Pelatihan Tim Biru

| | |
|---|---|
| **Nama Paket** | Pengadaan Platform Defensive Cyber Simulator (Cyber Range) |
| **Sifat** | Self-hosted · Air-Gapped · On-Premise di fasilitas instansi |
| **Pengguna** | Tim pertahanan siber (Blue Team) instansi/pangkalan |
| **Versi Dokumen** | 1.0 |
| **Status** | Acuan requirement (MVP perangkat lunak: lihat kolom Kesesuaian) |

---

## 1. Latar Belakang & Tujuan

Instansi memerlukan sarana pelatihan pertahanan siber yang **realistis namun aman**,
terletak di fasilitas sendiri dan **terisolasi penuh** dari jaringan produksi maupun
internet. Platform ini menyediakan lingkungan "cyber range" untuk melatih deteksi,
triase, penanggulangan, dan pemulihan insiden — dengan penekanan utama pada
**kedaulatan data (data sovereignty)** dan **pengaman keselamatan (safety guardrails)**.

**Tujuan:**
1. Menyelenggarakan latihan (exercise) multi-skenario yang terukur.
2. Mengukur kinerja tim melalui metrik waktu respons insiden.
3. Menjamin tidak ada risiko kebocoran data / malware nyata keluar dari lab.

---

## 2. Ruang Lingkup

Spektek terdiri dari empat bagian:

1. **Infrastruktur Hardware & Jaringan** (perangkat keras cyber range).
2. **Perangkat Lunak Platform Inti** (Exercise Director, Scenario Engine, Scoring/AAR).
3. **Modul Pelatihan & Skenario**.
4. **Guardrail Keamanan Wajib** (kritikal).

Kolom **Kesesuaian** menandai status prototipe perangkat lunak (MVP) yang menyertai
dokumen ini: ✅ terpenuhi · 🟡 sebagian · 📄 dokumentasi/desain · ⛔ belum.

---

## 3. Bagian 1 — Infrastruktur Hardware & Jaringan

> Detail desain & diagram: [`infrastructure.md`](infrastructure.md).

| ID | Requirement | Spesifikasi minimum | Kesesuaian |
|---|---|---|---|
| INF-01 | Compute | ≥ 4 node server enterprise, 2 × 32-core CPU, 1 TB RAM per node | 📄 |
| INF-02 | Kapasitas VM | Mampu menjalankan ratusan VM/container target skenario | 📄 |
| INF-03 | Storage | SAN all-flash, ≥ 50 TB usable, high IOPS | 📄 |
| INF-04 | Switching | 2 × ToR switch 10/25 GbE, redundan (MLAG) | 📄 |
| INF-05 | Firewall | 1 × NGFW untuk kontrol egress | 📄 |
| INF-06 | Isolasi | Air-gap + segmentasi VLAN ketat dari jaringan produksi | 📄 / ✅* |

\* Isolasi dimodelkan di perangkat lunak (guardrail menolak IP publik). Perangkat
keras itu sendiri di luar lingkup kode.

---

## 4. Bagian 2 — Perangkat Lunak Platform Inti

| ID | Requirement | Deskripsi | Kesesuaian |
|---|---|---|---|
| PLT-01 | Exercise Director Dashboard | Multi-skenario, tampilan terpusat | ✅ |
| PLT-02 | Injeksi event | Manual maupun terjadwal (scheduled) | ✅ |
| PLT-03 | Visualisasi topologi | Real-time, status node (sehat/compromised/quarantined) | ✅ |
| PLT-04 | Scenario Engine | Deploy/destroy lab gaya Infrastructure-as-Code, < 15 menit | ✅* |
| PLT-05 | Dummy traffic | Traffic pengguna palsu agar lab tampak "hidup" | ✅ |
| PLT-06 | Scoring Engine | Menangkap TTD/TTT/TTC/TTR otomatis | ✅ |
| PLT-07 | AAR (After-Action Review) | Laporan akhir + timeline + analisis gap SOP | ✅** |

\* Deploy/destroy bersifat **simulasi** (state di basis data), bukan provisioning
hypervisor nyata. \** Ekspor **PDF** tersedia; ekspor **Word** belum.

**Definisi metrik:**

| Metrik | Arti | Target default |
|---|---|---|
| TTD | Time to Detect | 5 menit |
| TTT | Time to Triage | 10 menit |
| TTC | Time to Contain | 30 menit |
| TTR | Time to Recover | 60 menit |

---

## 5. Bagian 3 — Modul Pelatihan & Skenario

| ID | Modul | Deskripsi | Kesesuaian |
|---|---|---|---|
| MOD-01 | SOC Simulator | Emulator SIEM: log palsu Firewall/EDR/DNS/Proxy | ✅ |
| MOD-02 | Web Security Lab | Container aplikasi web rentan (OWASP Top 10) | ⛔ |
| MOD-03 | OT/ICS Digital Twin | SCADA/HMI dummy (power/HVAC), simulasi kegagalan operasional | 🟡 |
| MOD-04 | C2 Resilience & Supply Chain | Dashboard pimpinan: data delay/konflik saat jamming; anomali vendor (cert kedaluwarsa, hash mismatch) | ✅ |
| MOD-05 | Ransomware Response | VM disuntik skrip self-encrypt **dummy** (bukan malware nyata); latih quarantine, isolasi, restore backup | ✅* |

\* MOD-03 direpresentasikan pada level data/status (belum ada animasi gauge HMI).
MOD-05 "restore backup" diwakili aksi Restore node.

---

## 6. Bagian 4 — Guardrail Keamanan Wajib (Kritikal)

| ID | Requirement | Deskripsi | Kesesuaian |
|---|---|---|---|
| KMN-01 | Isolasi ketat | Tolak semua ruting internet | ✅ |
| KMN-02 | Kill switch | Sakelar darurat mematikan seluruh VM latihan seketika | ✅ |
| KMN-03 | Dummy data enforcement | Larang malware nyata, identitas personel nyata, kredensial nyata, peta jaringan militer nyata; hanya parameter berbasis allowlist | ✅ |
| KMN-04 | RBAC | Pemisahan peran ketat: Admin, Exercise Director, Commander, SOC Analyst, Observer | ✅ |
| KMN-05 | Audit immutable | Log audit tamper-proof atas setiap aksi | ✅ |

**Mekanisme (implementasi MVP):**
- KMN-01: hanya rentang privat RFC1918 yang diizinkan di topologi; IP publik ditolak (HTTP 422).
- KMN-03: allowlist tipe serangan dummy, allowlist identitas, pemindaian pola kredensial.
- KMN-05: log audit ber-*hash chain* (`hash = sha256(prev_hash + baris)`); endpoint verifikasi mendeteksi perusakan.

---

## 7. Persyaratan Non-Fungsional

| ID | Kategori | Requirement |
|---|---|---|
| NFR-01 | Keamanan deploy | On-premise, air-gapped; tanpa dependensi layanan eksternal untuk autentikasi |
| NFR-02 | Ketersediaan | Redundansi switch & dual-homing compute/storage |
| NFR-03 | Kinerja | Deploy skenario < 15 menit |
| NFR-04 | Auditabilitas | Seluruh aksi tercatat & dapat diverifikasi |
| NFR-05 | Kedaulatan data | Seluruh data tetap di fasilitas instansi |

---

## 8. Kriteria Penerimaan (Acceptance)

1. Exercise Director dapat membuat, men-deploy, dan menghancurkan minimal 2 template skenario.
2. Injeksi serangan dummy memunculkan log SIEM & membuka insiden yang ter-skor.
3. Metrik TTD/TTT/TTC/TTR tercatat dan laporan AAR dapat diunduh.
4. Kill switch menghentikan seluruh node; isolasi menolak IP publik.
5. RBAC menegakkan pemisahan peran; log audit lolos verifikasi integritas.
6. Tidak ada malware/identitas/kredensial nyata yang dapat dimasukkan (ditolak guardrail).

---

## 9. Catatan Kesesuaian & Batasan Prototipe

- Prototipe menyertai dokumen ini sebagai **simulasi perangkat lunak** (Bagian 2–4),
  bukan cyber range operasional. Deploy/serangan/VM dimodelkan di basis data.
- **Bagian 1** murni desain/pengadaan hardware (di luar kode).
- Gap yang tersisa: MOD-02 (Web Security Lab / container OWASP), pendalaman MOD-03
  (animasi kegagalan OT/ICS), ekspor Word untuk AAR.
- Deployment "sesuai spek" **wajib on-premise & air-gapped**. Hosting cloud publik
  (mis. Vercel) hanya untuk demo, bertentangan dengan NFR-01/NFR-05.

---

*Dokumen ini memformalkan requirement yang menjadi dasar implementasi. Lihat
[`../README.md`](../README.md) untuk platform, [`infrastructure.md`](infrastructure.md)
untuk desain hardware, dan [`dashboard-mockup.md`](dashboard-mockup.md) untuk tampilan.*
