# ExamPrep

Üniversite dersleri için kişisel sınav hazırlık sistemi.
Girdi: slaytlar, ödevler, çıkmış sınavlar (PDF).
Çıktı: Anki desteleri (.apkg) ve haftalık testler.

## Mimari: API yok, motor Claude Code
Uygulama hiçbir LLM API'si çağırmaz. Analiz ve soru üretimi Claude Code
skill'leri (.claude/skills/) ile yapılır. Python kodu sadece deterministik
işleri yapar; Streamlit sadece arayüzdür.

- Claude Code skill'leri: PDF okuma, kazanım analizi, soru kalıbı çıkarma,
  soru üretimi, zorluk hakemliği, web keşfi (WebSearch)
- Python CLI (`python -m examprep ...`): ingest, veritabanı okuma/yazma,
  cevap doğrulama, benzerlik kontrolü, test planlama, Anki export
- Streamlit: ders oluşturma, PDF yükleme, kazanım haritasını gözden geçirme
  ve onaylama, test çözme, zorluk geri bildirimi, ilerleme ekranı

Skill'ler veritabanına doğrudan SQL yazmaz; her zaman CLI komutlarını
JSON girdiyle çağırır (ör. `python -m examprep archetype add --json file.json`).
CLI girdiyi Pydantic şemasıyla doğrular.

## Temel ilke
Kaynak sorular asla doğrudan sorulmaz. Her soru bir "soru kalıbına"
(QuestionArchetype: beceri + varyasyon eksenleri) soyutlanır, yeni sorular
bu kalıptan farklı bir kombinasyonla üretilir.
Örnek: sınavda merge sort izi çıktıysa, kalıp "karşılaştırma tabanlı sıralama
algoritmasını verilen dizide izle" olur; yeni soru quicksort veya heapsort ile
farklı bir dizi üzerinde sorulabilir.
Slaytlardaki tüm kazanımlar, sınavda hiç çıkmamış olsalar da kapsanır.

## Kullanım bağlamı
Tek kullanıcılı, yerel çalışan araç. Auth, deploy ve API anahtarı yok.

## Stack
Python 3.12, Streamlit, SQLite (SQLAlchemy), Pydantic, Typer (CLI),
PyMuPDF (PDF metin ve sayfa görüntüsü), genanki (Anki export),
yerel benzerlik için sentence-transformers (küçük, offline model).

## Veri modeli
Course > Topic > LearningObjective > QuestionArchetype > GeneratedQuestion > Attempt
Ayrıca: SourceDocument (type ∈ {slides, homework, exam}), DifficultyProfile (ders başına),
WeeklyPlan (sınav tarihine göre haftalara dağıtılmış kazanımlar)

## Kalıp kaynakları
- QuestionArchetype.origin ∈ {exam, homework, web, model}
- model: Claude, slayt içeriğinden her kazanım için farklı test açıları
  (hesaplama, izleme, karşılaştırma, hata bulma, kenar durum) türetir
- web: opsiyonel; web sorusu kopyalanmaz, archetype'a soyutlanır, source_url saklanır
- Kapsam kilidi: slayt kazanımlarına eşlenemeyen archetype atılır
- Benzer archetype'lar birleştirilir
- Test üretiminde kaynak kotası (varsayılan ~%50 exam/homework)

## Zorluk kalibrasyonu
- Her ders için çıkmış sınavlardan DifficultyProfile çıkarılır:
  steps, input_size, concept_count, bloom_level, est_minutes, edge_cases
- Üretimde aynı kazanımdan 2-3 gerçek sınav sorusu çapa olarak kullanılır
  (zorluğu eşle, içeriği değil)
- Hakem adımı üretilen soruyu profile göre puanlar; sapma büyükse
  parametreler ölçeklenir veya soru atılır
- Kullanıcı her denemede algılanan zorluğu işaretler (easy/exam_like/hard),
  profil bu geri bildirimle güncellenir

## Kalite kuralları
- `examprep similarity check`: üretilen soru kaynak sorulara fazla benziyorsa reddedilir
- `examprep verify`: algoritmik soruların cevapları Python ile hesaplanır,
  LLM cevabına güvenilmez

## Planlanan skill'ler
- /ders-analiz: bir dersin PDF'lerini oku, konu ağacı, kazanımlar,
  soru kalıpları ve zorluk profilini çıkar, CLI ile kaydet
- /hafta-testi: WeeklyPlan'a göre haftalık test üret (kota, hakem, doğrulama)
- /anki-uret: kazanımlardan kart üret, .apkg export et

## Aşamalar
1. İskelet + veri modeli + CLI + PDF ingest + Streamlit yükleme ekranı
2. /ders-analiz skill'i + Streamlit'te kazanım haritası onay ekranı
3. /hafta-testi skill'i + benzerlik ve doğrulama komutları
4. /anki-uret skill'i + Anki export
5. Test çözme ekranı + zorluk geri bildirimi
6. İlerleme takibi ve ağırlık güncelleme

## Çalışma tarzı
- Her aşamaya başlamadan önce plan sun, onay bekle
- Her modül için pytest testleri yazılır
