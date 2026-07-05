# Spesifikasi Teknis (Spektek)
## Defensive Cyber Simulator — Cyber Range Pelatihan Tim Biru

| | |
|---|---|
| **Nama Paket** | Pengadaan Platform Defensive Cyber Simulator (Cyber Range) |
| **Sifat** | Self-hosted · Air-Gapped · On-Premise di fasilitas instansi |
| **Pengguna** | Tim pertahanan siber (Blue Team) instansi/pangkalan |
| **Versi Dokumen** | 1.0 |

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

---

## 3. Bagian 1 — Infrastruktur Hardware & Jaringan

| ID | Requirement | Spesifikasi minimum |
|---|---|---|
| INF-01 | Compute | ≥ 4 node server enterprise, 2 × 32-core CPU, 1 TB RAM per node |
| INF-02 | Kapasitas VM | Mampu menjalankan ratusan VM/container target skenario |
| INF-03 | Storage | SAN all-flash, ≥ 50 TB usable, high IOPS |
| INF-04 | Switching | 2 × ToR switch 10/25 GbE, redundan (MLAG) |
| INF-05 | Firewall | 1 × NGFW untuk kontrol egress |
| INF-06 | Isolasi | Air-gap + segmentasi VLAN ketat dari jaringan produksi |

---

## 4. Bagian 2 — Perangkat Lunak Platform Inti

| ID | Requirement | Deskripsi |
|---|---|---|
| PLT-01 | Exercise Director Dashboard | Multi-tenant / multi-skenario, tampilan terpusat |
| PLT-02 | Injeksi event | Manual maupun terjadwal (scheduled) |
| PLT-03 | Visualisasi topologi | Real-time, status node (sehat/compromised/quarantined) |
| PLT-04 | Scenario Engine & Workflow Runner | Deploy/destroy lab gaya Infrastructure-as-Code, < 15 menit |
| PLT-05 | Dummy traffic | Traffic pengguna palsu agar lab tampak "hidup" |
| PLT-06 | Scoring Engine | Menangkap metrik insiden TTD/TTT/TTC/TTR secara otomatis |
| PLT-07 | AAR (After-Action Review) | Laporan akhir PDF/Word + timeline + analisis gap SOP |

**Definisi metrik:**

| Metrik | Arti | Target default |
|---|---|---|
| TTD | Time to Detect | 5 menit |
| TTT | Time to Triage | 10 menit |
| TTC | Time to Contain | 30 menit |
| TTR | Time to Recover | 60 menit |

---

## 5. Bagian 3 — Modul Pelatihan & Skenario

| ID | Modul | Deskripsi |
|---|---|---|
| MOD-01 | SOC Simulator | Emulator SIEM: log palsu Firewall/EDR/DNS/Proxy |
| MOD-02 | Web Security Lab | Container aplikasi web rentan (OWASP Top 10) |
| MOD-03 | OT/ICS Digital Twin | SCADA/HMI dummy (power/HVAC), simulasi kegagalan operasional akibat serangan |
| MOD-04 | C2 Resilience & Supply Chain | Dashboard pimpinan: data delay/konflik saat jamming; anomali vendor pihak ketiga (sertifikat kedaluwarsa, hash mismatch) |
| MOD-05 | Ransomware Response | VM disuntik skrip self-encrypt **dummy** (bukan malware nyata) untuk melatih quarantine, isolasi, dan restore backup |

---

## 6. Bagian 4 — Guardrail Keamanan Wajib (Kritikal)

| ID | Requirement | Deskripsi |
|---|---|---|
| KMN-01 | Isolasi ketat | Tolak semua ruting internet |
| KMN-02 | Kill switch | Satu sakelar darurat (fisik/logis) mematikan seluruh VM latihan seketika |
| KMN-03 | Dummy data enforcement | Larang malware nyata, identitas personel nyata, kredensial nyata, dan peta jaringan militer nyata; hanya parameter berbasis allowlist |
| KMN-04 | RBAC | Pemisahan peran ketat: Admin, Exercise Director, Commander, SOC Analyst, Observer |
| KMN-05 | Audit immutable | Log audit tamper-proof (tamper-evident) atas setiap aksi |

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
4. Kill switch menghentikan seluruh node; isolasi menolak ruting internet / IP publik.
5. RBAC menegakkan pemisahan peran; log audit lolos verifikasi integritas.
6. Tidak ada malware/identitas/kredensial nyata yang dapat dimasukkan (ditolak guardrail).
