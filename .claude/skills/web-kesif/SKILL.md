---
name: web-kesif
description: Başka üniversitelerin sınav, Übungsblatt ve alıştırma sorularından ilham alarak mevcut kazanımlara yeni soru kalıpları (origin=web) ekler. Sorular kopyalanmaz; kalıba (beceri + açı + varyasyon eksenleri) soyutlanır ve source_url saklanır. Kullanıcı internetten ilham, başka üniversitelerin soruları ya da kalıp çeşitliliği istediğinde kullan.
argument-hint: <ders id> [konu anahtarı ya da kazanım anahtarı]
---

# /web-kesif

Mevcut kazanımlar için web'deki soru tiplerini bulur ve **kalıp olarak**
kaydeder. Kalıplar test üretiminde (özellikle Orta bölüm) kullanılır.
Okuma ve yazma işleri `.venv/bin/python -m examprep ...` (aşağıda `ep`) ile yapılır.

## Kurallar
- **Kopyalama yok.** Web'deki soru metni, verisi ya da çözümü veritabanına yazılmaz.
  Yalnızca soyut kalıp (`skill`, `angle`, `variation_axes`) ve `source_url` saklanır.
- **Kapsam kilidi:** her web kalıbı mevcut bir kazanıma (`objective_key`) bağlanır.
  Web içeriği yeni kazanım oluşturmaz. Bir kazanıma uymayan soru tipini atla.
- **Varyasyon değerleri** dersin içeriğinden seçilir (slaytlar ve çıkmış sorular).
  Web yalnızca soru **biçimi** için ilham verir.
- **Kaynak seçimi:** yalnızca herkese açık üniversite sayfaları (ders sayfaları,
  Übungsblätter, Altklausuren). Giriş gerektiren ya da paylaşımı açıkça
  yasaklanmış içerik kullanılmaz.

## Akış
1. `ep course map --course <id> --no-text` çalıştır. Hedef kazanımları seç: verilen
   konu ya da kazanım; yoksa sınav/ödev kökenli kalıbı az olan, ağırlığı yüksek
   kazanımlar (en fazla ~8).
2. Her kazanım için WebSearch ile 1–2 arama yap. Almanca ve İngilizce terimleri
   karıştır, örneğin:
   - `"Klausur" "Komplexitätstheorie" "NP-vollständig" Aufgabe Lösung`
   - `"Übungsblatt" Turingmaschine konstruieren`
   - `exam "polynomial-time reduction" "3-SAT" solution pdf`
   Sonuç yetersizse sayfayı oku (WebFetch ya da `web-fetch` agent).
3. Bulduğun her uygun soru tipi için:
   - Hangi kazanımı ölçtüğünü belirle.
   - Mevcut kalıplardan farklı bir **açı** ya da **biçim** getiriyor mu, kontrol
     et. Aynısı varsa atla.
   - Kalıbı yaz. Anahtar biçimi `<kazanım_key>.<açı>-web<n>`:
```json
{"key": "komplexitaet.npc.np-schwere-beweis.find_error-web1",
 "objective_key": "komplexitaet.npc.np-schwere-beweis",
 "skill": "Bir NP-Schwere kanıtındaki indirgemenin hangi koşulu ihlal ettiğini bul",
 "angle": "find_error",
 "variation_axes": {"hata": ["yön ters", "dönüşüm üstel", "yalnız tek yön"], "problemler": ["SAT → 3-SAT", "SubsetSum → Partition"]},
 "origin": "web",
 "source_url": "https://…"}
```
4. `data/analysis/<id>/web_NN.json` dosyasına yaz ve
   `ep archetype import --course <id> --json … --dry-run` ile doğrula, sonra gerçek
   import'u yap.
5. Rapor: hangi kazanımlara kaç kalıp eklendi, kaynak URL'ler, atlanan sonuçlar
   ve nedenleri.
