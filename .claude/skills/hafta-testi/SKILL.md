---
name: hafta-testi
description: Bir dersin kazanım haritasındaki tüm malzemeden (o ana kadar yüklenmiş her şey) yeni bir kümülatif test üretir. Yeni eklenen kazanımları öne çıkarır, eski konuları tekrar olarak katar, ~%20 çıkmış soru ekler. Her soru kalıptan yeni bir kombinasyonla yazılır, algoritmik cevaplar Python ile doğrulanır, kaynak sorulara benzerlik kontrol edilir ve zorluk ayrı bir hakem tarafından puanlanır. Kullanıcı test, deneme sınavı ya da "bu haftanın testi" istediğinde kullan.
argument-hint: <ders id> [soru sayısı, varsayılan 10]
---

# /hafta-testi

Bir test taslağını slot slot doldurur ve kontrollerden geçirir. Bütün okuma ve
yazma işleri `.venv/bin/python -m examprep ...` (aşağıda `ep`) ile yapılır.
**Veritabanına doğrudan yazma.**

Taslağı Python oluşturur. Senin işin her slot için iyi bir soru yazmak, hakemi
çalıştırmak ve reddedilen soruları düzeltmek.

## Kurallar

- **Toplu yaz.** Her adımın çıktısını `data/tests/<test_id>/NN_<ad>.json`
  dosyasına yaz ve tek komutla gönder.
- **Dil:** soru metni (`prompt`) dersin sınav dilinde (Almanca) ve sınav
  üslubunda olur. `explanation` Türkçe yazılır, terimler Almanca kalır.
- **Kapsam kilidi:** soru yalnızca slottaki kalıbın becerisini ölçer.
  - `params` alanında yalnız `variation_axes` içindeki eksenler ve değerler kullanılır.
  - Somut veri (dizi, formül, makine) soruda serbestçe seçilir ama slayt içeriğinin dışına çıkmaz.
- **Kopya yok:** `anchors` ve çıkmış sorular **zorluğu eşlemek** içindir, içerik
  kopyalanmaz. Benzerlik eşiğini aşan soru otomatik reddedilir.
- **Tekrar yok:** `used_params` içinde geçen kombinasyonları yeniden kullanma.
- **Cevaba güvenme, hesaplat:** hesaplama, izleme ya da örnek içeren her soruya
  uygun doğrulayıcı için bir `check` bloğu ekle (bkz. "Doğrulayıcılar").
  Yalnız gerçekten kavramsal sorular (açıklama, ispat) `check` içermez.

## Akış

### 0. Hazırlık
1. Ders adı verildiyse `ep course list` ile id'yi bul.
2. `ep course check --course <id>` çalıştır. Kalıbı olan kazanım yoksa dur ve
   önce `/ders-analiz` çalıştırılmasını öner.

### 1. Taslak
`ep test compose --course <id> --size <n>` çalıştır ve çıktıyı
`data/tests/<test_id>/00_blueprint.json` olarak kaydet. Her slotta şunlar bulunur:
- `slot_type`:
  - `new`: hiç test edilmemiş kazanım
  - `review`: tekrar
  - `past`: çıkmış soru
- kazanım, kalıp (`skill`, `angle`, `variation_axes`, `origin`), `used_params`
- `anchors`: aynı kazanımdan sınav soruları, metin ve zorluk bilgisiyle
- `target_difficulty`: steps, input_size, est_minutes, bloom_level (1–6), edge_cases
- `past` slotlarında `past_question` ve varsa `past_solution`

### 2. Soruları yaz (`01_questions.json`)
Her slot için bir kayıt:
```json
{"slot_id": 12,
 "prompt": "Gegeben sei die Instanz … Lösen Sie … mit dynamischer Programmierung.",
 "answer": "Optimaler Wert 9, S = {B, C}",
 "answer_type": "open",
 "explanation": "Tablo satır satır: … (Türkçe çözüm)",
 "params": {"eleman_sayisi": "4", "M": "6-8"},
 "check": {"checker": "knapsack.dp_table", "input": {…}, "expected": {"value": 9}}}
```
- **Zorluğu hedefe göre ayarla:** steps, input_size ve est_minutes hedefin yarısı
  ile iki katı arasında olmalı; Bloom seviyesi hedeften en fazla 1 sapmalı.
  Hedefteki `edge_cases` uygun düşüyorsa birini soruya yerleştir.
- `answer_type`:
  - `numeric`: tek sayı ya da `a/b`.
  - `choice`: `choices` alanı ile; seyrek kullan, sınavlar açık uçlu.
  - `open`: diğer her şey. `answer` kısa ve kontrol edilebilir sonucu verir, tam çözüm `explanation`'a yazılır.
- **`past` slotları:** `prompt` ve `params` verme, soru metni aynen kullanılır.
  `answer` ve `explanation` olarak örnek çözüm yaz. Varsa `past_solution`'dan
  yararlan. Hesaplamalıysa `check` ekle.
- `ep gen import --json data/tests/<id>/01_questions.json`

### 3. Otomatik kontroller
```
ep verify run <test_id>          # check bloklarını çalıştırır; uyuşmayan reddedilir
ep similarity check <test_id>    # kaynak sorulara kosinüs benzerliği ≥ eşik → reddedilir
```

### 4. Hakem (ayrı subagent)
Soruyu yazan kendi sorusunu puanlamaz. Bunun yerine Agent aracıyla **tek bir**
`general-purpose` subagent başlat ve testin bütün taslak sorularını ona ver
(`ep test show <test_id>` içinde `status == "draft"` olanlar):
- Her soru için `question_id`, `prompt` ve `answer` ver. **Hedef zorluğu ve çapaları
  verme**, hakem bağımsız puanlamalı.
- Puanlama ölçütü (`/ders-analiz` ile aynı):
  - `steps`: tam çözümdeki ayrı işlem sayısı
  - `input_size`: verilen verinin boyutu; kavramsal soruda 0
  - `concept_count`: birlikte kullanılan kavram sayısı
  - `bloom_level`: remember / understand / apply / analyze / evaluate / create
  - `est_minutes`: iyi hazırlanmış bir öğrencinin süresi
  - `edge_cases`: kısa etiketler
- Hakemden yalnızca şu JSON listesini iste:
  `[{"question_id": …, "scores": {…}, "comment": "…"}]`.
  Ayrıca açık bir hata görürse (yanlış cevap, belirsiz soru) `comment` alanına yazmasını iste.
- Sonucu `02_judge.json` olarak kaydet ve `ep gen judge --json …` çalıştır. Sapmayı
  CLI hesaplar ve `ok`, `scale_up`, `scale_down` ya da `reject` kararı verir.
- Hakem `comment` alanında cevabın yanlış olduğunu söylediyse, karar `ok` olsa bile
  soruyu düzelt: 5. adımdaki gibi yeniden yaz.

### 5. Reddedilenleri düzelt (slot başına en fazla 3 deneme)
`ep test show <test_id>` ile `question.status == "rejected"` ya da sorusu olmayan
slotları bul ve `reject_reason`'a göre yeniden yaz:

| Neden | Ne yap |
|---|---|
| `doğrulama (…)` | Doğrulayıcının hesapladığı (`verification.computed`) sonuç doğrudur. Cevabı ve açıklamayı ona göre düzelt ya da veriyi değiştir |
| `benzerlik` | Farklı bir eksen kombinasyonu ve farklı somut veri seç, soruyu yeniden kur |
| `hakem: scale_up` / `scale_down` | Girdi boyutunu ya da adım sayısını hedefe çek |
| `hakem: reject` | Sorunun istediği bilişsel seviyeyi hedef Bloom seviyesine getir |

Yeni sorular `03_retry.json`, `04_retry.json`… dosyalarına yazılır ve 3. ve 4. adımlar
yalnız taslak sorular için tekrarlanır. CLI zaten yalnız `draft` olanlara bakar.

### 6. Tamamla
`ep test finalize <test_id>` çalıştır. Deneme hakkı biten slot varsa
`--allow-partial` ile o slotları çıkar ve raporda belirt.

### 7. Rapor
Kısa bir özet ver:
- test id ve soru sayısı; kaç soru yeni kazanımdan, kaç tekrar, kaç çıkmış soru
- konu dağılımı
- kaç sorunun cevabı kodla doğrulandı, kaçı kavramsal (yalnızca hakem görüşü)
- reddedilip yeniden yazılanlar ve nedenleri
- testin Streamlit'te **Testler** sayfasında görüntülenebileceği

## Doğrulayıcılar

Güncel liste `ep verify list` ile alınır. `input` sorudaki veriyle **birebir**
aynı olmalı. `expected` cevapta iddia edilen sonuçtur; yalnızca iddia ettiğin
alanları yaz.

| checker | input | expected (örnek alanlar) |
|---|---|---|
| `knapsack.solve` | `items: [{name, w, g}], M, method: optimal\|greedy_value\|greedy_ratio` | `value, items, is_optimal, optimal_value` |
| `knapsack.dp_table` | `items, M` (satır i = ilk i eleman, sütun h = 0..M) | `table, value` |
| `tm.run` | `transitions: [[durum, oku, yeni_durum, yaz, R\|L\|N]], start, accept, reject, blank: "_", input` ya da `inputs: [...]` | `tape, final_state, accepted, steps` ya da `runs: {girdi: {...}}` |
| `tm.runtime` | `transitions, N, alphabet` | `wc, bc, av` (av kesir olabilir: `"7/4"`) |
| `ram.run` | `program: ["R[-1] = R[0]", "IF R[-1] = 0: END (A)", "L: GOTO A", …], registers: {"0": 3, …}` | `registers: {"1": 0, …}, steps` |
| `sat.solve` | `cnf: [[1, -2, 3], …]` (i = x_i, −i = ¬x_i) | `satisfiable, count` |
| `sat.eval` | `cnf, assignment: {"1": true, …}` | `value` |
| `sat.2sat` | `cnf` (≤ 2 literal) | `satisfiable` |
| `sat.horn` | `cnf` (klozda ≤ 1 pozitif literal) | `satisfiable, true_vars` |
| `sat.to3sat` | `cnf` (orijinal), isteğe bağlı `cnf_3` (dönüşmüş) | `clauses, new_vars` (+ cnf_3 eşdeğerlik kontrolü) |
| `reduction.3sat_subsetsum` | `cnf` (tam 3 literal), `variant: slides\|exam` | `values` (çoklu küme), `target`, `element_count` |
| `average_case.expected` | `algorithm: compare_bits\|increment\|first_one, N` | `expected` (`"7/4"`), `limit` |
| `asymptotic.order` | `functions: ["n/log(n)", "sqrt(n)", "factorial(n)"]` (sympy yazımı, `eps` > 0) | `order: [[en yavaş], …, [en hızlı]]`; Θ-eşitler aynı grupta |

Uygun doğrulayıcı yoksa `check` ekleme. O soru "kavramsal" sayılır ve yalnızca
hakemden geçer. Raporda bunu belirt.
