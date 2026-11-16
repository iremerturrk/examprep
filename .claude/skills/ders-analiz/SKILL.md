---
name: ders-analiz
description: Bir dersin yüklenmiş PDF'lerini (slayt, sınav, ödev) analiz eder; konu ağacını, Bloom seviyeli kazanımları, çıkmış soruları, soru kalıplarını (archetype) ve zorluk profilini çıkarıp ExamPrep CLI ile toplu JSON olarak kaydeder. Kullanıcı bir dersi analiz etmek, kazanım haritası çıkarmak ya da yeni yüklenen belgelerle haritayı güncellemek istediğinde kullan.
argument-hint: <ders id veya adı>
---

# /ders-analiz

Bir dersin kazanım haritasını çıkarır ve kaydeder. Bütün okuma ve yazma işleri
`python -m examprep` CLI'si üzerinden yapılır. **Veritabanına doğrudan SQL yazma.**
Bu skill'de LLM'in işi anlamaktır: konuları, kazanımları ve soruları anlar,
soyutlar. Ağırlık, profil ve kapsam hesabını CLI yapar.

## Kurallar

- Komutları proje kökünden çalıştır: `.venv/bin/python -m examprep ...`
  (aşağıda kısaca `ep`). Tüm çıktılar JSON'dur. Hata olursa stderr'e
  `{"error", "details"}` yazılır ve komut 1 koduyla çıkar.
- **Toplu yaz, tek tek değil.** Her adımın sonucunu bir JSON dosyasına yaz
  ve tek bir import komutuyla gönder. Dosyalar şuraya yazılır:
  `data/analysis/<ders_id>/NN_<ad>.json`. Bu klasör git'e girmez.
- İlk kez yazarken önce `--dry-run` ile doğrula, sonra gerçek import'u yap.
- Import'lar tek işlemdir: bir satır bile hatalıysa hiçbir şey yazılmaz.
  `details` satır numarasını verir (`[3] key: ...`). Dosyayı düzelt ve
  aynı komutu tekrar çalıştır.
- Kullanıcının onayladığı kayıtlar güncellenmez, `skipped_approved` içinde
  döner. Bu normaldir, zorlamaya çalışma.
- **Kapsam kilidi:** yalnızca slaytlarda olan içerik kazanım olur. Kalıplar
  ve varyasyon değerleri slayt içeriğinin dışına çıkmaz. Slaytta karşılığı
  olmayan bir sınav sorusu kaydedilir ama kalıba bağlanmaz.
- Kaynak soruların metni yalnızca SourceQuestion'da saklanır. Kalıbın
  `skill` alanına soru metni, somut sayılar ya da diziler kopyalanmaz.

### Anahtarlar (`key`)
- Küçük harf, rakam, `.`, `-`, `_` kullanılır, ders içinde tekildir ve
  kalıcıdır. Tekrar analizde aynı şeye aynı anahtarı ver.
- Hiyerarşiyi noktayla göster:
  - konu: `siralama`
  - alt konu: `siralama.karsilastirma`
  - kazanım: `siralama.karsilastirma.merge-izle`
  - kalıp: `<kazanım_key>.<açı>[-n]`, örneğin `siralama.karsilastirma.merge-izle.trace`
- Türkçe karakterleri ASCII'ye çevir (ı→i, ş→s, ğ→g, ü→u, ö→o, ç→c).
- Kaynak sorular anahtarla değil, `document_id` + `label` ile tanınır
  (`label` belgedeki numaradır: `"3"`, `"2b"`).

## Akış

### 0. Hazırlık
1. Kullanıcı dersi adıyla verdiyse `ep course list` ile id'sini bul.
   Ders yoksa dur ve kullanıcıya söyle.
2. `ep doc list --course <id>` çalıştır. Belgeleri türüne göre ayır
   (slides / exam / homework). Hiç slayt yoksa dur: kazanımlar slayttan
   çıkar.
3. `ep course map --course <id> --no-text` çalıştır.
   - Harita boşsa **ilk analiz** yapılıyordur.
   - Doluysa **güncelleme** yapılıyordur. Mevcut anahtarları kullan,
     yalnızca yeni ya da değişen içeriği ekle. Hangi belgelerin daha önce
     işlendiğini kazanımların `source_document_id` alanından ve soruların
     `document_id` alanından anla.

### 1. Belgeleri oku
- `ep doc pages <belge_id> --start N --end M` ile 15-20 sayfalık parçalar
  halinde oku. Büyük belgeyi tek seferde okuma.
- `is_scanned: true` olan sayfanın `text` alanı boştur. O sayfanın
  `image_path` dosyasını Read aracıyla görüntü olarak oku.
  `ep doc pages <id> --scanned-only` hangi sayfaların taranmış olduğunu
  listeler.
- Metin çıkarımı bozuksa (formüller, tablolar, kod) görüntüye de bak.

### 2. Slaytlardan konu ağacı ve kazanımlar
**Konu ağacı** (`01_topics.json`) en fazla 3 seviye olur. Sıra, dersin
işleniş sırasını izler.
```json
[
  {"key": "siralama", "name": "Sıralama Algoritmaları", "children": [
    {"key": "siralama.karsilastirma", "name": "Karşılaştırma Tabanlı Sıralama"},
    {"key": "siralama.dogrusal", "name": "Doğrusal Zamanlı Sıralama"}
  ]}
]
```
`ep topic import --course <id> --json data/analysis/<id>/01_topics.json`

**Kazanımlar** (`02_objectives.json`). Kazanım, öğrencinin yapabilmesi
gereken tek bir şeydir ve bir fiille başlar: "...yı verilen dizi üzerinde
adım adım izler". Çok geniş ("sıralamayı bilir") ya da çok dar ("slayt 14'teki
örneği hatırlar") olmamalı.
- Slayttaki her anlamlı içerik en az bir kazanıma bağlanmalı.
- Ortalama olarak her slayt destesinden 5-15 kazanım çıkar.
```json
[
  {"key": "siralama.karsilastirma.merge-izle", "topic_key": "siralama.karsilastirma",
   "text": "Merge sort'u verilen bir dizi üzerinde birleştirme adımlarıyla izler",
   "bloom_level": "apply", "source_document_id": 3, "source_pages": [12, 13, 14]}
]
```
`bloom_level` şunlardan biridir:
- `remember`: tanım, terim
- `understand`: açıklama, örnekleme
- `apply`: algoritmayı çalıştırma, hesaplama
- `analyze`: karmaşıklık analizi, durum ayırma
- `evaluate`: yaklaşımları karşılaştırıp seçme, doğruluk argümanı
- `create`: yeni algoritma ya da yapı tasarlama

`ep objective import --course <id> --json .../02_objectives.json`

### 3. Sınav ve ödev soruları (`03_questions.json`)
- Her soruyu ve anlamlı alt soruyu (2a, 2b) ayrı kaydet. Alt sorular aynı
  beceriyi ölçüyorsa birleştirip tek soru yap.
- `text`: sorunun tam metni, verilen veri dahil. Kısaltma.
- `points`: varsa puan. `solution`: varsa çözüm. Çözüm ayrı bir belgedeyse
  (örneğin `odev1_cozum.pdf`), etiketle eşleştirip sorunun kaydına yaz. Çözüm
  belgesinden ayrı soru oluşturma.
- `difficulty` alanını **her sınav sorusu için doldur**, profil bundan
  hesaplanır. Ödevlerde doldurmak isteğe bağlıdır.

| Alan | Nasıl puanlanır |
|---|---|
| `steps` | Tam çözüm için gereken ayrı işlem sayısı (her birleştirme, her tablo satırı, her ispat adımı) |
| `input_size` | Verilen verinin boyutu: dizi uzunluğu, düğüm/kenar sayısı. Kavramsal soruda 0 |
| `concept_count` | Birlikte kullanılması gereken ayrı kavram sayısı (en az 1) |
| `bloom_level` | Sorunun gerçekte istediği seviye. Kazanımınkiyle aynı olmak zorunda değil |
| `est_minutes` | İyi hazırlanmış bir öğrencinin süresi. Sınav süresi ve puan biliniyorsa, toplam süreyi puana oranla dağıt |
| `edge_cases` | Sorunun kasıtlı yerleştirdiği kenar durumlar, kısa etiketlerle: `"tekrar eden eleman"`, `"boş girdi"`, `"negatif ağırlık"` |

```json
[
  {"document_id": 5, "label": "3", "page_no": 2,
   "text": "Aşağıdaki diziyi merge sort ile sıralayın ve her birleştirme adımını gösterin: [38, 27, 43, 3, 9, 82, 10]",
   "points": 15, "solution": null,
   "difficulty": {"steps": 6, "input_size": 7, "concept_count": 1, "bloom_level": "apply",
                  "est_minutes": 8, "edge_cases": []}}
]
```
`ep question import --course <id> --json .../03_questions.json`

### 4. Soruları kazanımlara eşle ve kalıba soyutla (`04_archetypes.json`)
Her kaynak soru için şunları yap:
1. Sorunun ölçtüğü kazanımı bul. Hiçbir kazanıma uymuyorsa önce slaytlarda
   gözden kaçan bir içerik olup olmadığına bak. Gerçekten slayt dışıysa
   **bağlama**. Soru eşlenmemiş kalır, bunu raporda belirt.
2. Kalıbı çıkar:
   - `skill`: içerikten bağımsız, genelleştirilmiş beceri cümlesi.
     Örnek: "Karşılaştırma tabanlı bir sıralama algoritmasını verilen
     dizide adım adım izle".
   - `angle`: `compute`, `trace`, `compare`, `find_error`, `edge_case`,
     `explain` veya `design`.
   - `variation_axes`: yeni soru üretirken değiştirilebilecek eksenler.
     Her eksende en az 2 değer olur ve değerler slaytlarda geçen içerikten
     seçilir.
     Örnek: `{"algoritma": ["merge sort", "quicksort", "heapsort"], "girdi_durumu": ["rastgele", "sıralı", "ters sıralı", "tekrarlı"], "girdi_boyutu": ["6-8", "9-12"]}`.
   - `origin`: soru sınavdansa `exam`. Yalnızca ödevden geliyorsa
     `homework`. Bağlı sorulardan en az biri sınavdansa origin `exam`
     olmalı, CLI bunu denetler.
3. **Benzer kalıpları birleştir.** Aynı kazanımı aynı açıdan ölçen ve
   yalnızca eksen değerlerinde ayrışan sorular **tek kalıp** olur.
   `source_questions` alanında hepsi listelenir, eksen değerleri de
   birleştirilir. Farklı kazanımların kalıpları birleştirilmez.
```json
[
  {"key": "siralama.karsilastirma.merge-izle.trace",
   "objective_key": "siralama.karsilastirma.merge-izle",
   "skill": "Karşılaştırma tabanlı bir sıralama algoritmasını verilen dizide adım adım izle",
   "angle": "trace",
   "variation_axes": {"algoritma": ["merge sort", "quicksort", "heapsort"],
                      "girdi_durumu": ["rastgele", "ters sıralı", "tekrarlı"]},
   "origin": "exam",
   "source_questions": [{"document_id": 5, "label": "3"}, {"document_id": 7, "label": "1b"}]}
]
```
Güncelleme modunda daha önce kaydedilmiş benzer bir kalıp varsa yeni kalıp
açma. Mevcut kalıbı aynı anahtarla yeniden gönder ve yeni soruyu
`source_questions` alanına ekle. Bu liste her gönderimde baştan yazılır,
eski soruları da listede tut. İki mevcut kalıp sonradan aynı çıkarsa
`ep archetype merge --course <id> --into <kalacak> --from <diğeri>` kullan.

### 5. Eksik açılar için model kalıpları (`05_model_archetypes.json`)
Hedef: **her kazanım en az 2 farklı açıdan** kalıpla kapsansın. Buna sınavda
çıkmış kazanımlar da dahildir. Sınavda kazanım yalnızca `trace` açısından
sorulduysa ona `edge_case`, `compare` ya da `find_error` gibi farklı bir açı ekle.
- `origin: "model"` olur ve `source_questions` boş bırakılır.
- Açıyı kazanımın Bloom seviyesine ve içeriğine göre seç. `remember`
  seviyesindeki bir kazanıma `design` açısı verilmez.
- Kazanım zenginse 3-4 açı olabilir. Ama her açı gerçekten farklı bir
  düşünme biçimi ölçmeli. Aynı açıyı farklı kelimelerle tekrarlama.
- Model kalıpları da slayt içeriğinin dışına çıkmaz.

`ep archetype import --course <id> --json .../05_model_archetypes.json`

### 6. Zorluk profili
`ep profile compute --course <id>` çalıştır. Hesabı CLI yapar: sınav
sorularının `difficulty` alanlarının medyanını alır. Sınav belgesi yoksa bu
adım hata verir. Atla ve raporda belirt.

### 7. Kontrol ve rapor
`ep course check --course <id>` çalıştır.
- `objectives_without_archetypes` ya da `objectives_with_few_angles` boş
  değilse 5. adıma dön ve tamamla. `ok: true` olmadan bitirme.
- `questions_without_difficulty` boş değilse o sınav sorularının
  `difficulty` alanını doldurup soruları tekrar import et.

Kullanıcıya kısa bir özet ver:
- kaç konu, kazanım, kalıp ve kaynak soru yazıldı (oluşturulan, güncellenen, onaylı olduğu için atlanan)
- eşlenmeyen sorular ve nedenleri (slayt dışı içerik)
- zorluk profilinin özeti
- emin olmadığın eşlemeler (örneğin iki kazanıma da uyan sorular)

Sonunda kullanıcıya Streamlit'teki **Kazanım Haritası** sayfasında
inceleyip onaylamasını hatırlat.
