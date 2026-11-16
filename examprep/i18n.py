"""Arayüz dili: Türkçe (varsayılan), Deutsch, English.

Yalnızca arayüz metinleri çevrilir. İçerik (kazanım metinleri, soru açıklamaları, kartlar)
üretildiği dilde kalır. Dil seçimi oturumda ve URL'de (?lang=de) saklanır.
"""

from enum import Enum

LANGS = {"tr": "Türkçe", "de": "Deutsch", "en": "English"}
DEFAULT_LANG = "tr"
STATE_KEY = "ui_lang"  # widget'tan bağımsız anahtar: Streamlit sayfa geçişinde widget durumunu temizleyebilir
WIDGET_KEY = "ui_lang_select"

S: dict[str, dict[str, str]] = {
    # --- Gezinme
    "nav.courses": {"tr": "Dersler", "de": "Kurse", "en": "Courses"},
    "nav.upload": {"tr": "PDF Yükle", "de": "PDF hochladen", "en": "Upload PDFs"},
    "nav.map": {"tr": "Kazanım Haritası", "de": "Lernziel-Karte", "en": "Learning-Objective Map"},
    "nav.tests": {"tr": "Testler", "de": "Tests", "en": "Tests"},
    "nav.language": {"tr": "Dil", "de": "Sprache", "en": "Language"},
    # --- Ortak
    "common.course": {"tr": "Ders", "de": "Kurs", "en": "Course"},
    "common.need_course": {"tr": "Önce 'Dersler' sayfasından bir ders oluşturun.",
                           "de": "Lege zuerst auf der Seite 'Kurse' einen Kurs an.",
                           "en": "Create a course on the 'Courses' page first."},
    "common.save": {"tr": "Kaydet", "de": "Speichern", "en": "Save"},
    "common.edit": {"tr": "Düzenle", "de": "Bearbeiten", "en": "Edit"},
    "common.delete": {"tr": "Sil", "de": "Löschen", "en": "Delete"},
    "common.approve": {"tr": "Onayla", "de": "Freigeben", "en": "Approve"},
    "common.unapprove": {"tr": "Onayı kaldır", "de": "Freigabe aufheben", "en": "Revoke approval"},
    "common.page": {"tr": "Sayfa", "de": "Seite", "en": "Page"},
    "common.none": {"tr": "yok", "de": "keine", "en": "none"},
    # --- Dersler
    "courses.title": {"tr": "Dersler", "de": "Kurse", "en": "Courses"},
    "courses.new": {"tr": "Yeni ders", "de": "Neuer Kurs", "en": "New course"},
    "courses.name": {"tr": "Ders adı *", "de": "Kursname *", "en": "Course name *"},
    "courses.code": {"tr": "Ders kodu", "de": "Kurskürzel", "en": "Course code"},
    "courses.has_date": {"tr": "Sınav tarihi belli", "de": "Prüfungstermin steht fest", "en": "Exam date is known"},
    "courses.date": {"tr": "Sınav tarihi", "de": "Prüfungstermin", "en": "Exam date"},
    "courses.create": {"tr": "Oluştur", "de": "Anlegen", "en": "Create"},
    "courses.created": {"tr": "'{name}' oluşturuldu (id: {id}).", "de": "'{name}' angelegt (ID: {id}).",
                        "en": "'{name}' created (id: {id})."},
    "courses.name_empty": {"tr": "Ders adı boş olamaz.", "de": "Der Kursname darf nicht leer sein.",
                           "en": "Course name must not be empty."},
    "courses.exists": {"tr": "Bu isimde bir ders zaten var.", "de": "Ein Kurs mit diesem Namen existiert bereits.",
                       "en": "A course with this name already exists."},
    "courses.existing": {"tr": "Mevcut dersler", "de": "Vorhandene Kurse", "en": "Existing courses"},
    "courses.col_code": {"tr": "Kod", "de": "Kürzel", "en": "Code"},
    "courses.col_docs": {"tr": "Belge sayısı", "de": "Dokumente", "en": "Documents"},
    "courses.empty": {"tr": "Henüz ders yok.", "de": "Noch keine Kurse.", "en": "No courses yet."},
    # --- Yükleme
    "upload.files": {"tr": "PDF dosyaları", "de": "PDF-Dateien", "en": "PDF files"},
    "upload.types": {"tr": "Dosya türleri", "de": "Dokumenttypen", "en": "Document types"},
    "upload.process": {"tr": "İşle", "de": "Verarbeiten", "en": "Process"},
    "upload.processing": {"tr": "İşleniyor: {name}", "de": "Verarbeite: {name}", "en": "Processing: {name}"},
    "upload.duplicate": {"tr": "{name}: bu dosya zaten yüklü, atlandı.", "de": "{name}: bereits hochgeladen, übersprungen.",
                         "en": "{name}: already uploaded, skipped."},
    "upload.scanned": {"tr": "{name}: {n} sayfa işlendi; taranmış sayfalar /ders-analiz sırasında görüntüden okunacak.",
                       "de": "{name}: {n} Seiten verarbeitet; gescannte Seiten werden bei /ders-analiz aus dem Bild gelesen.",
                       "en": "{name}: {n} pages processed; scanned pages will be read from the image during /ders-analiz."},
    "upload.done_file": {"tr": "{name}: {n} sayfa işlendi.", "de": "{name}: {n} Seiten verarbeitet.",
                         "en": "{name}: {n} pages processed."},
    "upload.done": {"tr": "Tamamlandı", "de": "Fertig", "en": "Done"},
    "upload.uploaded": {"tr": "Yüklenen belgeler", "de": "Hochgeladene Dokumente", "en": "Uploaded documents"},
    "upload.col_file": {"tr": "Dosya", "de": "Datei", "en": "File"},
    "upload.col_type": {"tr": "Tür", "de": "Typ", "en": "Type"},
    "upload.col_status": {"tr": "Durum", "de": "Status", "en": "Status"},
    "upload.no_docs": {"tr": "Bu derse henüz belge yüklenmedi.", "de": "Für diesen Kurs wurden noch keine Dokumente hochgeladen.",
                       "en": "No documents uploaded for this course yet."},
    "upload.preview": {"tr": "Önizleme", "de": "Vorschau", "en": "Preview"},
    "upload.document": {"tr": "Belge", "de": "Dokument", "en": "Document"},
    "upload.no_image": {"tr": "Sayfa görüntüsü bulunamadı.", "de": "Seitenbild nicht gefunden.", "en": "Page image not found."},
    "upload.scanned_page": {"tr": "Taranmış sayfa: metin /ders-analiz sırasında görüntüden okunacak.",
                            "de": "Gescannte Seite: Der Text wird bei /ders-analiz aus dem Bild gelesen.",
                            "en": "Scanned page: the text will be read from the image during /ders-analiz."},
    "upload.text": {"tr": "Çıkarılan metin", "de": "Extrahierter Text", "en": "Extracted text"},
    # --- Kazanım haritası
    "map.title": {"tr": "Kazanım Haritası", "de": "Lernziel-Karte", "en": "Learning-Objective Map"},
    "map.no_analysis": {"tr": "Bu ders için henüz analiz yok. Claude Code'da `/ders-analiz {id}` çalıştırın.",
                        "de": "Für diesen Kurs gibt es noch keine Analyse. Führe in Claude Code `/ders-analiz {id}` aus.",
                        "en": "No analysis for this course yet. Run `/ders-analiz {id}` in Claude Code."},
    "map.objectives": {"tr": "Kazanım", "de": "Lernziele", "en": "Objectives"},
    "map.archetypes": {"tr": "Kalıp", "de": "Aufgabenmuster", "en": "Question patterns"},
    "map.source_questions": {"tr": "Kaynak soru", "de": "Altfragen", "en": "Past questions"},
    "map.pending": {"tr": "Onay bekleyen", "de": "Offen", "en": "Pending approval"},
    "map.no_archetype_list": {"tr": "Kalıbı olmayan kazanımlar: {items}", "de": "Lernziele ohne Muster: {items}",
                              "en": "Objectives without patterns: {items}"},
    "map.few_angles_list": {"tr": "{n}'den az açıyla kapsanan kazanımlar: {items}",
                            "de": "Lernziele mit weniger als {n} Blickwinkeln: {items}",
                            "en": "Objectives covered by fewer than {n} angles: {items}"},
    "map.profile": {"tr": "Zorluk profili ({n} sınav sorusundan)", "de": "Schwierigkeitsprofil (aus {n} Klausuraufgaben)",
                    "en": "Difficulty profile (from {n} exam questions)"},
    "map.steps": {"tr": "Adım", "de": "Schritte", "en": "Steps"},
    "map.input_size": {"tr": "Girdi boyutu", "de": "Eingabegröße", "en": "Input size"},
    "map.concepts": {"tr": "Kavram", "de": "Konzepte", "en": "Concepts"},
    "map.bloom_scale": {"tr": "Bloom (1-6)", "de": "Bloom (1-6)", "en": "Bloom (1-6)"},
    "map.minutes": {"tr": "Süre (dk)", "de": "Zeit (min)", "en": "Time (min)"},
    "map.edge_cases": {"tr": "Kenar durumlar: {items}", "de": "Randfälle: {items}", "en": "Edge cases: {items}"},
    "map.overwrite_note": {"tr": "Düzenlediğin bir kaydı onaylamazsan, /ders-analiz tekrar çalıştığında üzerine yazılabilir. Onaylı kayıtlar korunur.",
                           "de": "Bearbeitete, aber nicht freigegebene Einträge kann /ders-analiz überschreiben. Freigegebene Einträge bleiben erhalten.",
                           "en": "Edited records that are not approved may be overwritten by /ders-analiz. Approved records are kept."},
    "map.pending_only": {"tr": "Yalnızca onay bekleyenleri göster", "de": "Nur offene Einträge anzeigen", "en": "Show pending only"},
    "map.unmapped": {"tr": "Eşlenmemiş kaynak sorular ({n})", "de": "Nicht zugeordnete Altfragen ({n})", "en": "Unmapped past questions ({n})"},
    "map.unmapped_note": {"tr": "Hiçbir kazanıma bağlanamayan sorular.", "de": "Fragen ohne zugeordnetes Lernziel.",
                          "en": "Questions not linked to any objective."},
    "map.approve_all": {"tr": "Tümünü onayla", "de": "Alles freigeben", "en": "Approve all"},
    "map.approve_all_help": {"tr": "Konu, alt konular, kazanımlar ve kalıplar", "de": "Thema, Unterthemen, Lernziele und Muster",
                             "en": "Topic, subtopics, objectives and patterns"},
    "map.topic_approved": {"tr": "Konu onaylandı", "de": "Thema freigegeben", "en": "Topic approved"},
    "map.delete_topic_note": {"tr": "Alt konular, kazanımlar ve kalıplar da silinir.",
                              "de": "Unterthemen, Lernziele und Muster werden ebenfalls gelöscht.",
                              "en": "Subtopics, objectives and patterns are deleted too."},
    "map.delete_objective_note": {"tr": "Kazanımın kalıpları da silinir; kaynak sorular kalır ve eşlenmemiş olur.",
                                  "de": "Die Muster des Lernziels werden gelöscht; Altfragen bleiben (nicht zugeordnet).",
                                  "en": "The objective's patterns are deleted; past questions remain (unmapped)."},
    "map.no_archetypes": {"tr": "Bu kazanımın kalıbı yok. `/ders-analiz` tekrar çalıştırılınca model kalıpları eklenir.",
                          "de": "Dieses Lernziel hat keine Muster. Ein erneuter Lauf von `/ders-analiz` ergänzt sie.",
                          "en": "This objective has no patterns. Re-running `/ders-analiz` adds them."},
    "map.warn_none": {"tr": "⚠️ kalıp yok", "de": "⚠️ keine Muster", "en": "⚠️ no patterns"},
    "map.warn_angle": {"tr": "⚠️ tek açı", "de": "⚠️ nur ein Blickwinkel", "en": "⚠️ single angle"},
    "map.weight": {"tr": "ağırlık {w}", "de": "Gewicht {w}", "en": "weight {w}"},
    "map.manual": {"tr": " (elle)", "de": " (manuell)", "en": " (manual)"},
    "map.past_basis": {"tr": "📜 çıkmış sorulardan", "de": "📜 aus Altklausuren", "en": "📜 from past exams"},
    "map.slide_pages": {"tr": "slayt sayfaları: {pages}", "de": "Folienseiten: {pages}", "en": "slide pages: {pages}"},
    "map.approved": {"tr": "✅ onaylı", "de": "✅ freigegeben", "en": "✅ approved"},
    "map.unapproved": {"tr": "⬜ onay bekliyor", "de": "⬜ offen", "en": "⬜ pending"},
    "map.origin": {"tr": "kaynak: {origin}", "de": "Herkunft: {origin}", "en": "origin: {origin}"},
    "map.source_url": {"tr": "Kaynak: {url}", "de": "Quelle: {url}", "en": "Source: {url}"},
    "map.source_toggle": {"tr": "Kaynak sorular ({n})", "de": "Altfragen ({n})", "en": "Past questions ({n})"},
    "map.points": {"tr": "{p} puan", "de": "{p} Punkte", "en": "{p} points"},
    "map.question_head": {"tr": "Soru {label}", "de": "Aufgabe {label}", "en": "Question {label}"},
    "map.difficulty": {"tr": "Adım {steps} · girdi {input} · kavram {concepts} · {bloom} · ~{minutes} dk · kenar durum: {edges}",
                       "de": "Schritte {steps} · Eingabe {input} · Konzepte {concepts} · {bloom} · ~{minutes} min · Randfälle: {edges}",
                       "en": "Steps {steps} · input {input} · concepts {concepts} · {bloom} · ~{minutes} min · edge cases: {edges}"},
    "map.show_solution": {"tr": "Çözümü göster", "de": "Lösung anzeigen", "en": "Show solution"},
    "map.unlink": {"tr": "Bu kalıptan ayır", "de": "Vom Muster lösen", "en": "Unlink from pattern"},
    "map.unlinked": {"tr": "Soru kalıptan ayrıldı", "de": "Frage vom Muster gelöst", "en": "Question unlinked"},
    "map.delete_question": {"tr": "Soruyu sil", "de": "Frage löschen", "en": "Delete question"},
    "map.pattern": {"tr": "Kalıp: {skill}", "de": "Muster: {skill}", "en": "Pattern: {skill}"},
    "map.dlg_rename": {"tr": "Konuyu yeniden adlandır", "de": "Thema umbenennen", "en": "Rename topic"},
    "map.dlg_objective": {"tr": "Kazanımı düzenle", "de": "Lernziel bearbeiten", "en": "Edit objective"},
    "map.dlg_archetype": {"tr": "Kalıbı düzenle", "de": "Muster bearbeiten", "en": "Edit pattern"},
    "map.dlg_delete": {"tr": "Silinsin mi?", "de": "Löschen?", "en": "Delete?"},
    "map.name": {"tr": "Ad", "de": "Name", "en": "Name"},
    "map.objective": {"tr": "Kazanım", "de": "Lernziel", "en": "Objective"},
    "map.bloom": {"tr": "Bloom seviyesi", "de": "Bloom-Stufe", "en": "Bloom level"},
    "map.manual_weight": {"tr": "Ağırlığı elle ayarla (hesaplanan: {w})", "de": "Gewicht manuell setzen (berechnet: {w})",
                          "en": "Set weight manually (computed: {w})"},
    "map.weight_label": {"tr": "Ağırlık", "de": "Gewicht", "en": "Weight"},
    "map.skill": {"tr": "Beceri", "de": "Fähigkeit", "en": "Skill"},
    "map.angle": {"tr": "Açı", "de": "Blickwinkel", "en": "Angle"},
    "map.axes": {"tr": "Varyasyon eksenleri", "de": "Variationsachsen", "en": "Variation axes"},
    "map.axes_help": {"tr": "Her satır bir eksen: `eksen: değer1 {sep} değer2 {sep} ...` (en az 2 değer)",
                      "de": "Eine Achse pro Zeile: `Achse: Wert1 {sep} Wert2 {sep} ...` (mind. 2 Werte)",
                      "en": "One axis per line: `axis: value1 {sep} value2 {sep} ...` (at least 2 values)"},
    "map.will_delete": {"tr": "**{label}** silinecek.", "de": "**{label}** wird gelöscht.", "en": "**{label}** will be deleted."},
    "map.deleted": {"tr": "Silindi", "de": "Gelöscht", "en": "Deleted"},
    "map.topic_updated": {"tr": "Konu güncellendi", "de": "Thema aktualisiert", "en": "Topic updated"},
    "map.objective_updated": {"tr": "Kazanım güncellendi", "de": "Lernziel aktualisiert", "en": "Objective updated"},
    "map.archetype_updated": {"tr": "Kalıp güncellendi", "de": "Muster aktualisiert", "en": "Pattern updated"},
    # --- Testler
    "tests.title": {"tr": "Testler", "de": "Tests", "en": "Tests"},
    "tests.none": {"tr": "Hazır test yok. Claude Code'da `/kazanim-testi {id}` ile yeni bir test üretebilirsin.",
                   "de": "Kein fertiger Test. Erzeuge in Claude Code mit `/kazanim-testi {id}` einen neuen Test.",
                   "en": "No test available. Generate one in Claude Code with `/kazanim-testi {id}`."},
    "tests.new_hint": {"tr": "Yeni test: Claude Code'da `/kazanim-testi {id}`", "de": "Neuer Test: `/kazanim-testi {id}` in Claude Code",
                       "en": "New test: `/kazanim-testi {id}` in Claude Code"},
    "tests.kind_kazanim": {"tr": "Kazanım testi", "de": "Lernzieltest", "en": "Objective test"},
    "tests.kind_open": {"tr": "Açık uçlu (eski)", "de": "Offene Fragen (alt)", "en": "Open questions (legacy)"},
    "tests.n_questions": {"tr": "{n} soru", "de": "{n} Fragen", "en": "{n} questions"},
    "tests.show_answers": {"tr": "Cevapları göster", "de": "Antworten anzeigen", "en": "Show answers"},
    "tests.answer": {"tr": "Cevap", "de": "Antwort", "en": "Answer"},
    "tests.tab_cards": {"tr": "1 · Kartlar", "de": "1 · Karten", "en": "1 · Cards"},
    "tests.tab_test": {"tr": "2 · Test", "de": "2 · Test", "en": "2 · Test"},
    "tests.tab_result": {"tr": "3 · Sonuç", "de": "3 · Ergebnis", "en": "3 · Results"},
    "tests.cards_intro": {"tr": "Testten önce bu testin ölçtüğü **{o} kazanımın {c} kartını** tekrar et.",
                          "de": "Wiederhole vor dem Test die **{c} Karten zu {o} Lernzielen**, die dieser Test prüft.",
                          "en": "Before the test, review the **{c} cards for the {o} objectives** this test measures."},
    "tests.no_cards": {"tr": "Bu test için henüz kart yok.", "de": "Für diesen Test gibt es noch keine Karten.",
                       "en": "No cards for this test yet."},
    "tests.view": {"tr": "Görünüm", "de": "Ansicht", "en": "View"},
    "tests.view_single": {"tr": "Kart kart", "de": "Einzeln", "en": "One by one"},
    "tests.view_list": {"tr": "Liste", "de": "Liste", "en": "List"},
    "tests.anki": {"tr": "Anki destesi (.apkg)", "de": "Anki-Stapel (.apkg)", "en": "Anki deck (.apkg)"},
    "tests.card_progress": {"tr": "Kart {i} / {n}", "de": "Karte {i} / {n}", "en": "Card {i} / {n}"},
    "tests.flip": {"tr": "Cevabı göster", "de": "Antwort zeigen", "en": "Show answer"},
    "tests.again": {"tr": "↻ Tekrar et", "de": "↻ Wiederholen", "en": "↻ Again"},
    "tests.known": {"tr": "✓ Biliyorum", "de": "✓ Gewusst", "en": "✓ Got it"},
    "tests.submitted": {"tr": "Gönderildi: **{s} / {n}** doğru. Ayrıntılar 'Sonuç' sekmesinde.",
                        "de": "Abgegeben: **{s} / {n}** richtig. Details im Tab 'Ergebnis'.",
                        "en": "Submitted: **{s} / {n}** correct. Details in the 'Results' tab."},
    "tests.retake": {"tr": "Testi yeniden çöz", "de": "Test erneut lösen", "en": "Retake test"},
    "tests.question_n": {"tr": "Soru {n}", "de": "Frage {n}", "en": "Question {n}"},
    "tests.submit": {"tr": "Testi gönder", "de": "Test abgeben", "en": "Submit test"},
    "tests.blank": {"tr": "{n} soru boş bırakıldı", "de": "{n} Fragen unbeantwortet", "en": "{n} questions left blank"},
    "tests.no_result": {"tr": "Testi gönderdiğinde sonuçlar burada görünecek.", "de": "Nach der Abgabe erscheinen hier die Ergebnisse.",
                        "en": "Results will appear here after you submit."},
    "tests.submission": {"tr": "Gönderim", "de": "Abgabe", "en": "Submission"},
    "tests.total": {"tr": "Toplam", "de": "Gesamt", "en": "Total"},
    "tests.duration": {"tr": "Süre: {m} dk {s} sn", "de": "Dauer: {m} min {s} s", "en": "Time: {m} min {s} s"},
    "tests.weak": {"tr": "Eksik kazanımlar", "de": "Lücken", "en": "Objectives to review"},
    "tests.weak_item": {"tr": "{text} · {w}/{n} yanlış", "de": "{text} · {w}/{n} falsch", "en": "{text} · {w}/{n} wrong"},
    "tests.no_card_obj": {"tr": "Bu kazanım için kart yok.", "de": "Keine Karten zu diesem Lernziel.", "en": "No cards for this objective."},
    "tests.all_correct": {"tr": "Bütün sorular doğru!", "de": "Alles richtig!", "en": "All answers correct!"},
    "tests.questions": {"tr": "Sorular", "de": "Fragen", "en": "Questions"},
    "tests.only_wrong": {"tr": "Yalnızca yanlışlar", "de": "Nur falsche", "en": "Wrong only"},
    "tests.blank_mark": {"tr": "⬜ boş", "de": "⬜ leer", "en": "⬜ blank"},
    "tests.your_answer": {"tr": "senin cevabın", "de": "deine Antwort", "en": "your answer"},
    "tests.explanation": {"tr": "Açıklama", "de": "Erklärung", "en": "Explanation"},
    "tests.objective": {"tr": "Kazanım: {text}", "de": "Lernziel: {text}", "en": "Objective: {text}"},
    "tests.difficulty": {"tr": "Zorluk", "de": "Schwierigkeit", "en": "Difficulty"},
    # --- Enum etiketleri
    "bloom.remember": {"tr": "Hatırlama", "de": "Erinnern", "en": "Remember"},
    "bloom.understand": {"tr": "Anlama", "de": "Verstehen", "en": "Understand"},
    "bloom.apply": {"tr": "Uygulama", "de": "Anwenden", "en": "Apply"},
    "bloom.analyze": {"tr": "Analiz", "de": "Analysieren", "en": "Analyze"},
    "bloom.evaluate": {"tr": "Değerlendirme", "de": "Bewerten", "en": "Evaluate"},
    "bloom.create": {"tr": "Yaratma", "de": "Erschaffen", "en": "Create"},
    "angle.compute": {"tr": "Hesaplama", "de": "Berechnen", "en": "Compute"},
    "angle.trace": {"tr": "İzleme", "de": "Nachvollziehen", "en": "Trace"},
    "angle.compare": {"tr": "Karşılaştırma", "de": "Vergleichen", "en": "Compare"},
    "angle.find_error": {"tr": "Hata bulma", "de": "Fehler finden", "en": "Find the error"},
    "angle.edge_case": {"tr": "Kenar durum", "de": "Randfall", "en": "Edge case"},
    "angle.explain": {"tr": "Açıklama", "de": "Erklären", "en": "Explain"},
    "angle.design": {"tr": "Tasarım", "de": "Entwerfen", "en": "Design"},
    "origin.exam": {"tr": "Sınav", "de": "Klausur", "en": "Exam"},
    "origin.homework": {"tr": "Ödev", "de": "Übung", "en": "Homework"},
    "origin.web": {"tr": "Web", "de": "Web", "en": "Web"},
    "origin.model": {"tr": "Model", "de": "Modell", "en": "Model"},
    "doc.slides": {"tr": "Slayt", "de": "Folien", "en": "Slides"},
    "doc.homework": {"tr": "Ödev", "de": "Übung", "en": "Homework"},
    "doc.exam": {"tr": "Sınav", "de": "Klausur", "en": "Exam"},
    "docstatus.processed": {"tr": "İşlendi", "de": "Verarbeitet", "en": "Processed"},
    "docstatus.needs_ocr": {"tr": "Taranmış sayfa var", "de": "Enthält Scans", "en": "Contains scans"},
    "docstatus.failed": {"tr": "Hata", "de": "Fehler", "en": "Failed"},
    "tier.basic": {"tr": "Bölüm 1 · Temel", "de": "Teil 1 · Grundlagen", "en": "Part 1 · Basics"},
    "tier.medium": {"tr": "Bölüm 2 · Orta", "de": "Teil 2 · Mittel", "en": "Part 2 · Intermediate"},
    "tier.exam": {"tr": "Bölüm 3 · Sınav düzeyi", "de": "Teil 3 · Klausurniveau", "en": "Part 3 · Exam level"},
    "tiershort.basic": {"tr": "Temel", "de": "Grundlagen", "en": "Basics"},
    "tiershort.medium": {"tr": "Orta", "de": "Mittel", "en": "Intermediate"},
    "tiershort.exam": {"tr": "Sınav düzeyi", "de": "Klausurniveau", "en": "Exam level"},
    "tiernote.basic": {"tr": "Kısa sorular: tanım, temel özellik, küçük örnek.", "de": "Kurze Fragen: Definition, Grundeigenschaft, kleines Beispiel.",
                       "en": "Short questions: definitions, basic properties, small examples."},
    "tiernote.medium": {"tr": "Uygulama ve analiz soruları.", "de": "Anwenden und Analysieren.", "en": "Application and analysis."},
    "tiernote.exam": {"tr": "Çıkmış sınav sorularıyla aynı zorlukta.", "de": "Auf dem Niveau der Altklausuren.",
                      "en": "At the level of past exam questions."},
    "cardkind.definition": {"tr": "Tanım", "de": "Definition", "en": "Definition"},
    "cardkind.fact": {"tr": "Bilgi", "de": "Fakt", "en": "Fact"},
    "cardkind.example": {"tr": "Örnek", "de": "Beispiel", "en": "Example"},
    "cardkind.pitfall": {"tr": "Sık hata", "de": "Typischer Fehler", "en": "Common mistake"},
    "perceived.easy": {"tr": "Kolay", "de": "Leicht", "en": "Easy"},
    "perceived.exam_like": {"tr": "Sınav gibi", "de": "Klausurnah", "en": "Exam-like"},
    "perceived.hard": {"tr": "Zor", "de": "Schwer", "en": "Hard"},
}

# Enum sınıfı → anahtar öneki
_ENUM_PREFIX = {"BloomLevel": "bloom", "Angle": "angle", "ArchetypeOrigin": "origin", "DocType": "doc",
                "DocStatus": "docstatus", "Tier": "tier", "CardKind": "cardkind", "PerceivedDifficulty": "perceived"}


def current_lang() -> str:
    try:
        import streamlit as st

        lang = st.session_state.get(STATE_KEY, DEFAULT_LANG)
    except Exception:  # Streamlit dışında (CLI, testler)
        lang = DEFAULT_LANG
    return lang if lang in LANGS else DEFAULT_LANG


def t(key: str, lang: str | None = None, **kwargs) -> str:
    entry = S[key]
    text = entry.get(lang or current_lang()) or entry[DEFAULT_LANG]
    return text.format(**kwargs) if kwargs else text


def label(member: Enum | str, prefix: str | None = None, lang: str | None = None) -> str:
    """Enum üyesinin arayüz etiketi: label(BloomLevel.apply) → 'Uygulama' / 'Anwenden' / 'Apply'."""
    if isinstance(member, Enum):
        prefix = prefix or _ENUM_PREFIX[type(member).__name__]
        member = member.value
    return t(f"{prefix}.{member}", lang=lang)


def init_lang() -> None:
    """Dil seçimini URL'den (?lang=) oturuma taşır."""
    import streamlit as st

    if STATE_KEY not in st.session_state:
        q = st.query_params.get("lang", DEFAULT_LANG)
        st.session_state[STATE_KEY] = q if q in LANGS else DEFAULT_LANG


def language_selector() -> None:
    """Kenar çubuğunda dil seçici; seçim oturumda ve URL'de (?lang=) saklanır."""
    import streamlit as st

    init_lang()

    def changed() -> None:
        st.session_state[STATE_KEY] = st.session_state[WIDGET_KEY]
        st.query_params["lang"] = st.session_state[WIDGET_KEY]

    langs = list(LANGS)
    st.sidebar.selectbox("🌐 " + t("nav.language"), langs, index=langs.index(current_lang()),
                         format_func=LANGS.get, key=WIDGET_KEY, on_change=changed)
    if st.query_params.get("lang") != current_lang():
        st.query_params["lang"] = current_lang()
