---
name: kazanim-testi
description: Bir dersin kazanım haritasındaki tüm malzemeden MEB kazanım testi tarzında şıklı bir test (varsayılan 35 soru: 20 temel, 10 orta, 5 çıkmış soruya paralel) ve testin ölçtüğü kazanımlar için tekrar kartları üretir. Doğru şıklar mümkün olduğunca Python ile doğrulanır, kopya kontrolü yapılır, zorluk ve şık kalitesini ayrı bir hakem denetler. Kullanıcı test, deneme, kazanım testi, kart ya da "yeni test" istediğinde kullan.
argument-hint: <ders id> [--temel 20 --orta 10 --sinav 5]
---

# /kazanim-testi

Bir test taslağını doldurur: şıklı sorular ve kartlar. Tüm okuma ve yazma
işleri `.venv/bin/python -m examprep ...` (aşağıda `ep`) ile yapılır.
**Veritabanına doğrudan yazma.**

Amaç kullanıcının konuyu **öğrenmesi**. Sorular kısa ve net, açıklamalar
öğretici olmalı.

## Kurallar

- **Dil:** soru metni, şıklar ve kartın ön yüzü **Almanca** (sınav dili).
  `explanation` ve kartın arka yüzü **Türkçe**, terimler Almanca kalır.
- **Biçim:** Markdown + LaTeX. Satır içi formül `$n^2 \log n$`, ayrı satırda
  `$$…$$`. Pseudocode üç ters tırnaklı kod bloğunda.
- **Soruda ipucu yok:** kazanım adı, kalıp adı ya da konu başlığı soruya yazılmaz.
- **Tam 4 şık (A–D) ve tam bir doğru şık.** `answer`, `choices` içindeki doğru
  şıkkın metniyle birebir aynıdır.
  - Yanlış şıklar tipik hatalardan seçilir: ters indirgeme yönü, eksik adım,
    karıştırılan tanım, off-by-one.
  - "Alle/Keine der genannten" kullanma.
  - Şıkları benzer uzunlukta tut.
  - Doğru şıkkın konumunu (A/B/C/D) test boyunca dengeli dağıt.
- **Kapsam kilidi:** soru yalnızca slottaki kalıbın becerisini ölçer. `params`
  alanında yalnız `variation_axes` içindeki eksenler ve değerler kullanılır.
  `used_params` içindeki kombinasyonları yeniden kullanma.
- **Kopya yok:** çapa ve paralel sorular zorluğu ve yapıyı gösterir, metin ve
  veri kopyalanmaz. Benzerlik kontrolü kopyayı reddeder.
- **Cevaba güvenme, hesaplat:** hesap ya da izleme içeren sorularda doğru şıkkın
  iddia ettiği sonucu `check` bloğuyla doğrulat (bkz. "Doğrulayıcılar").
  Yanlış şıkların değerleri hesaplanan sonuçtan farklı olmalı.
- **Toplu yaz:** dosyalar `data/tests/<test_id>/` altına yazılır. 35 soruyu
  bölümlere göre ayırabilirsin: `01a_basic.json`, `01b_medium.json`, `01c_exam.json`.

## Akış

### 0. Hazırlık
1. Ders adı verildiyse `ep course list` ile id'yi bul.
2. `ep course check --course <id>` çalıştır. Kalıbı olan kazanım yoksa dur ve
   önce `/ders-analiz` çalıştırılmasını öner.

### 1. Taslak
`ep test compose --course <id> [--temel 20 --orta 10 --sinav 5]` çalıştır ve
çıktıyı `data/tests/<test_id>/00_blueprint.json` olarak kaydet.
- `slots[].tier`: `basic`, `medium` ya da `exam`. Slotlar konu sırasındadır.
- `slots[].parallel_question`: `exam` slotlarında paralel yazılacak çıkmış soru
  (metni ve zorluğuyla).
- `slots[].anchors`: `medium` slotlarında zorluk çapası sorular.
- `objectives[]`: testin ölçtüğü kazanımlar ve her birinin `active_cards` sayısı.

### 2. Soruları yaz
Her slot için bir kayıt:
```json
{"slot_id": 7,
 "prompt": "Welche Aussage über $f(n) = 3n^2 + 5n$ ist korrekt?",
 "answer": "$f \\in \\Theta(n^2)$",
 "answer_type": "choice",
 "choices": ["$f \\in \\Theta(n)$", "$f \\in \\Theta(n^2)$", "$f \\in o(n^2)$", "$f \\in \\omega(n^2)$"],
 "explanation": "Doğru: … Neden diğerleri yanlış: A) … C) … D) …",
 "params": {"…": "…"},
 "check": {"checker": "…", "input": {…}, "expected": {…}}}
```
Bölümlere göre:

| tier | Hedef | Yazım |
|---|---|---|
| `basic` | remember/understand (en çok küçük bir apply), ≤ 3 adım, ~1 dk | Tek kavram: tanım, temel özellik, mini örnek, "hangisi doğru/yanlış". Kısa kök |
| `medium` | apply/analyze, 2–8 adım, 2–4 dk | Küçük bir örnek üzerinde hesaplama, izleme ya da karşılaştırma; çapalar zorluk ölçüsüdür |
| `exam` | `parallel_question` ile aynı zorluk (hakem sapmayı kontrol eder) | Aynı beceri ve yapı, yeni veri. Açık uçlu ispat sorusu şıklı hale getirilir: "Welche Reduktion zeigt korrekt …", "Welcher Schritt ist fehlerhaft", "Welcher Wert ergibt sich für …" |

`explanation` öğretici olmalı: doğru şık neden doğru (kısa çözüm yolu) ve her
yanlış şık hangi hatayı temsil ediyor.

`ep gen import --json data/tests/<id>/01a_basic.json` (her dosya için ayrı).

### 3. Kartlar
`objectives[]` içinde `active_cards < 2` olan her kazanım için 2–4 kart yaz
(`02_cards.json`):
```json
[{"objective_key": "laufzeit.o-notation", "kind": "definition",
  "front": "Was bedeutet $f \\in O(g)$?",
  "back": "**Üst sınır:** $\\exists c>0, n_0$: $\\forall n \\ge n_0$: $f(n) \\le c\\,g(n)$. Örnek: $3n^2 \\in O(n^2)$ ($c=4$)."}]
```
- `kind`: `definition` (tanım), `fact` (temel olgu/teorem), `example` (mini
  örnek, çözümüyle), `pitfall` (sık yapılan hata).
- Ön yüz kısa bir Almanca soru ya da terim. Arka yüz en fazla ~60 kelime Türkçe,
  terimler Almanca.
- Kartlar testteki soruların cevabını vermez, konuyu öğretir.
- `ep card import --course <id> --json …` çalıştır. Aynı ön yüz tekrar eklenmez.

### 4. Otomatik kontroller
```
ep verify run <test_id>
ep similarity check <test_id>
```

### 5. Hakem (ayrı subagent)
Soruyu yazan kendi sorusunu puanlamaz. Agent aracıyla **tek bir**
`general-purpose` subagent başlat. Girdi dosyası
`data/tests/<id>/judge_input.json` olsun:
- taslak sorular: `question_id`, `prompt`, `choices`, `answer` (doğru olarak
  işaretlenen şık)
- yeni kartlar: `card_id`, `front`, `back`

Hedef zorluğu, bölümü ve çapaları **verme**. Hakemden yalnızca JSON iste:
```json
{"questions": [{"question_id": 1, "scores": {"steps": 1, "input_size": 0, "concept_count": 1,
                "bloom_level": "remember", "est_minutes": 1, "edge_cases": []},
                "answer_ok": true, "single_correct": true, "distractors_ok": true, "comment": ""}],
 "bad_cards": [{"card_id": 5, "reason": "…"}]}
```
- `answer_ok`: işaretli şık gerçekten doğru mu.
- `single_correct`: başka bir şık da doğru sayılabilir mi.
- `distractors_ok`: yanlış şıklar makul ve açıkça yanlış mı.

`questions` listesini `03_judge.json` dosyasına yazıp `ep gen judge --json …`
çalıştır. `bad_cards` varsa `ep card reject --json …` çalıştır ve o kazanımlar
için yeni kart yaz.

### 6. Reddedilenleri düzelt (slot başına en fazla 3 deneme)
`ep test show <test_id>` ile `question.status == "rejected"` ya da sorusu olmayan
slotları bul:

| Neden | Ne yap |
|---|---|
| `doğrulama (…)` | `verification.computed` doğrudur; doğru şıkkı ya da veriyi düzelt |
| `benzerlik` | farklı veri ve kombinasyon seç, soruyu yeniden kur |
| `hakem: scale_up` / `scale_down` | bölümün aralığına çek (basic kısalt, medium biraz büyüt) |
| `hakem: reject` | şık sorunu (cevap yanlış, iki doğru şık, zayıf yanlış şıklar) ya da Bloom sapması; `comment`'e göre düzelt |

Yeniden yazılan sorular `04_retry.json`… dosyalarına yazılır; 4. ve 5. adımlar
yalnız taslaklar için tekrarlanır.

### 7. Tamamla ve raporla
`ep test finalize <test_id>` çalıştır. Deneme hakkı biten slot varsa
`--allow-partial` ile o slotları çıkar.

Kısa rapor:
- soru sayısı (bölüm bazında), ölçülen kazanım ve kart sayısı
- kaç doğru şık kodla doğrulandı
- yeniden yazılanlar ve nedenleri
- testin Streamlit'te **Testler** sayfasında olduğu: kartlar → test → gönder → sonuç

## Doğrulayıcılar

`ep verify list` güncel listeyi verir. `input` sorudaki veriyle birebir aynı
olur, `expected` doğru şıkkın iddia ettiği sonuçtur.

| checker | input | expected |
|---|---|---|
| `knapsack.solve` | `items: [{name, w, g}], M, method: optimal\|greedy_value\|greedy_ratio` | `value, items, is_optimal, optimal_value` |
| `knapsack.dp_table` | `items, M` | `table, value` |
| `tm.run` | `transitions: [[durum, oku, yeni_durum, yaz, R\|L\|N]], start, accept, reject, blank: "_", input \| inputs` | `tape, final_state, accepted, steps` \| `runs` |
| `tm.runtime` | `transitions, N, alphabet` | `wc, bc, av` |
| `ram.run` | `program: [...], registers: {...}` | `registers, steps` |
| `sat.solve` / `sat.eval` / `sat.2sat` / `sat.horn` | `cnf` (+ `assignment`) | `satisfiable, count` / `value` / `satisfiable` / `satisfiable, true_vars` |
| `sat.to3sat` | `cnf`, isteğe bağlı `cnf_3` | `clauses, new_vars` |
| `reduction.3sat_subsetsum` | `cnf`, `variant: slides\|exam` | `values, target, element_count` |
| `average_case.expected` | `algorithm: compare_bits\|increment\|first_one, N` | `expected, limit` |
| `asymptotic.order` | `functions` (sympy yazımı) | `order` (Θ-sınıfı grupları, artan) |

Uygun doğrulayıcı yoksa `check` ekleme; o soru yalnızca hakemden geçer.
