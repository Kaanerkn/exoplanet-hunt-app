# 🪐 Exoplanet Hunt – Otomasyon ile Ötegezegen Tespiti

Bu proje, **NASA’nın TESS ve Kepler açık verilerini** kullanarak **otomasyon tabanlı bir ötegezegen tespit sistemi** geliştirmeyi amaçlamaktadır. Sistem, transit yöntemine dayalı temel parametreleri analiz ederek potansiyel ötegezegen adaylarını belirler ve sonuçları otomatik olarak Excel dosyasına aktarır.

---

## 🚀 Proje Amacı

Bu çalışmanın temel amacı:

- NASA tarafından sağlanan **TESS ve Kepler verilerini** kullanmak  
- **Otomasyon sistemi** ile ötegezegen tespiti yapmak  
- Tespit edilen ötegezegenleri **Excel dosyası** formatında dışa aktarmak  
- Manuel işlemleri minimize ederek **tekrarlanabilir ve ölçeklenebilir** bir sistem oluşturmak  

---

## 🔬 Kullanılan Parametreler (TESS Verileri)

Ötegezegen adaylarının belirlenmesinde aşağıdaki **4 temel transit parametresi** kullanılmıştır:

- **Yörünge Periyodu (Orbital Period)**  
- **Transit Süresi (Transit Duration)**  
- **Transit Derinliği (Transit Depth)**  
- **TESS Büyüklüğü (TESS Magnitude)**  

Bu parametreler, bir gökcisminin yıldızının önünden geçiş yapıp yapmadığını ve gezegen olma ihtimalini değerlendirmek için kullanılmıştır.

---

## ⚙️ Metodoloji

1. **NASA Açık Veri Kaynağından Veri Çekme**  
   - TESS ve Kepler görevlerine ait veriler alınmıştır.

2. **Veri İşleme ve Filtreleme**  
   - Gerekli parametreler seçilmiş  
   - Uygun olmayan veya eksik veriler elenmiştir

3. **Otomatik Değerlendirme Sistemi**  
   - Transit parametrelerine dayalı karar mekanizması uygulanmıştır

4. **Sonuçların Excel’e Aktarılması**  
   - Tespit edilen ötegezegen adayları otomatik olarak `.xlsx` dosyasına yazdırılmıştır

---

## 🛠️ Kullanılan Teknolojiler

- **Python**
- **Jupyter Notebook**
- **Pandas**
- **NumPy**
- **Excel (.xlsx) çıktı**
- **Web tabanlı arayüz (otomasyon sistemi)**

---

## ▶️ Çalıştırma Adımları

```bash
pip install -r requirements.txt
streamlit run app.py

