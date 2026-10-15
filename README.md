# Movie Shortlist – Kodi-Add-on für den Filmabend

**Movie Shortlist** (`plugin.video.movieshortlist`) sammelt Filme aus der vorhandenen
Kodi-Filmbibliothek in einer Auswahlliste. Beim gemeinsamen Stöbern merkt man Kandidaten
über das Kontextmenü vor und sucht anschließend in einer übersichtlichen Liste den Film
des Abends aus.

* Zielplattform: Kodi 21.x „Omega“ (getestet gegen die API von Kodi 21, `xbmc.python` 3.0.1)
* Plattformunabhängig (Windows 11, Linux, Android, macOS …), reines Python 3
* Lokale SQLite- und externe MySQL/MariaDB-Videobibliotheken
* Liest die Bibliothek nur, verändert sie nie
* Keine Online-Dienste, keine Konten, keine Scraper-Abfragen

---

## 1. Installation

1. ZIP-Datei [`dist/plugin.video.movieshortlist-1.0.0.zip`](dist/plugin.video.movieshortlist-1.0.0.zip)
   herunterladen und auf den Kodi-Rechner kopieren.
2. Kodi → **Einstellungen → System → Add-ons** → **Unbekannte Quellen** einschalten
   (einmalig, Sicherheitsabfrage mit „Ja“ bestätigen).
3. Kodi → **Einstellungen → Add-ons → Aus ZIP-Datei installieren** → ZIP-Datei auswählen.
4. Nach der Meldung „Add-on installiert“ ist alles aktiv – ein Neustart ist nicht nötig.

Es gibt **nur ein Add-on mit einer ID**. Kodi erlaubt mehrere Erweiterungspunkte in einem
Add-on; Movie Shortlist enthält:

| Erweiterungspunkt            | Datei               | Aufgabe                                           |
|------------------------------|---------------------|---------------------------------------------------|
| `xbmc.python.pluginsource`   | `main.py`           | Video-Add-on mit Menü und Filmliste               |
| `kodi.context.item`          | `context_add.py`, `context_remove.py` | Kontextmenüeinträge in der Bibliothek |
| `xbmc.service`               | `service.py`        | Stellt nach Kodi-Start/Profilwechsel den Kontextmenü-Status her |

Das ZIP lässt sich jederzeit neu bauen: `python3 tools/build_zip.py`.

---

## 2. Bedienung

### Filme vormerken

1. In der Filmbibliothek (Liste, Poster, Infowand, Fanart, Filmreihen, Widgets auf dem
   Startbildschirm, Suchergebnisse …) einen Film markieren.
2. Kontextmenü öffnen (Taste **C**, Fernbedienung „Menü“/langes Drücken von OK, Rechtsklick).
3. **„Zur Filmauswahl hinzufügen“** wählen → kurze Benachrichtigung mit Filmplakat.

Ist der Film bereits vorgemerkt, steht an dieser Stelle **„Aus Filmauswahl entfernen“**.
Es gibt keine Rückfragen und die aktuelle Ansicht bleibt unverändert (keine Aktualisierung,
die Markierung bleibt stehen).

### Filmauswahl ansehen

**Add-ons → Video-Add-ons → Movie Shortlist**:

| Menüpunkt                         | Funktion |
|-----------------------------------|----------|
| **Filmauswahl anzeigen (n)**      | Alle vorgemerkten Filme in den normalen Kodi-Filmansichten |
| **Zufälligen Film auswählen**     | Zeigt den Kodi-Infodialog eines zufälligen Films; abgespielt wird erst nach „Abspielen“/„Fortsetzen“ |
| **Sortierung: …**                 | Sortierung wählen (wird gespeichert) |
| **Filmauswahl leeren**            | Nach der Rückfrage „Möchtest du alle Filme aus der Filmauswahl entfernen?“ (Ja/Nein) |

Im Kontextmenü eines Films **innerhalb** der Filmauswahl:
„Aus Filmauswahl entfernen“, „Zufälligen Film auswählen“, „Sortierung ändern“.
Entfernt wird ausschließlich der Eintrag in der Filmauswahl – nie der Film aus der
Bibliothek oder vom Datenträger.

Sortierungen: Reihenfolge des Hinzufügens (neueste zuerst) · Filmtitel (alphabetisch,
berücksichtigt den Kodi-Sortiertitel, Umlaute/Akzente werden wie Grundbuchstaben sortiert)
· Erscheinungsjahr (neueste zuerst) · IMDb-Bewertung (höchste zuerst) · Laufzeit
(kürzeste zuerst). Filme ohne den jeweiligen Wert stehen immer am Ende.

Tipp fürs Sofa: Den Menüpunkt „Filmauswahl anzeigen“ per Kontextmenü → „Zu Favoriten
hinzufügen“ ablegen oder in Estuary als Hauptmenü-/Widget-Eintrag verwenden.

### Einstellungen

* **Sortierung der Filmauswahl** (identisch mit dem Menüpunkt „Sortierung“)
* **Ausführliche Protokollierung** – nur zur Fehlersuche; ansonsten schreibt das Add-on
  nur Warnungen/Fehler und wenige Statusmeldungen ins Kodi-Log.

---

## 3. Wie die Kontextmenü-Integration funktioniert

Kontextmenü-Add-ons werden in `addon.xml` über den Erweiterungspunkt `kodi.context.item`
deklariert. Kodi entscheidet **ohne Python-Code** anhand einer `<visible>`-Bedingung, ob
ein Eintrag angezeigt wird; erst beim Auswählen wird das Skript gestartet, das den
markierten Eintrag als `sys.listitem` erhält.

Damit Kodi „hinzufügen“ bzw. „entfernen“ korrekt anzeigen kann, veröffentlicht das Add-on
die IDs der vorgemerkten Filme als Fenstereigenschaften des Home-Fensters
(`Window(Home).Property(movieshortlist.slot1)` … `slot50`). Die Bedingung vergleicht jeden
Slot exakt mit der `ListItem.DBID` des markierten Films:

```
String.IsEqual(ListItem.DBType,movie) + !String.IsEmpty(ListItem.DBID)
+ !String.StartsWith(Container.FolderPath,plugin://plugin.video.movieshortlist/)
+ ![String.IsEqual(Window(Home).Property(movieshortlist.slot1),ListItem.DBID) | … slot50 …]
```

Warum so und nicht mit einer einzigen Liste und `String.Contains`? Ein Teilstring-Vergleich
würde Film-ID 12 auch in „112“ finden und damit falsche Einträge anzeigen. `String.IsEqual`
mit einer Infolabel-Angabe als zweitem Parameter ist seit Kodi 17 offiziell unterstützt;
die Reihenfolge (Fenstereigenschaft zuerst, `ListItem.DBID` als zweiter Parameter) wurde
anhand des Kodi-21-Quellcodes (`GUIInfoManager.cpp`) so gewählt, dass `ListItem.DBID`
sicher gegen den markierten Eintrag ausgewertet wird. Die Bedingungen werden mit
`tools/update_context_conditions.py` erzeugt.

Die Slots werden gesetzt beim Hinzufügen/Entfernen/Leeren, beim Öffnen des Add-ons und
durch den kleinen Dienst nach dem Laden eines Kodi-Profils (beim Abmelden werden sie
gelöscht, damit ein anderes Profil nicht die fremde Liste sieht). Der Dienst wartet nur auf
das Beenden-Signal und verbraucht keine Rechenzeit.

---

## 4. Wiedergabe – wie aus der Bibliothek

Die Einträge der Filmauswahl sind „echte“ Bibliothekseinträge aus Kodis Sicht:

* Der Pfad des Listeneintrags ist die **Originaldatei** des Bibliotheksfilms
  (z. B. `smb://nas/Filme/Alien (1979)/Alien.mkv`, `stack://…`, ISO, BDMV).
* Das Info-Tag enthält `dbid`, `mediatype=movie` und `FilenameAndPath`.
* Kodi wendet deshalb die normale **Standardaktion beim Auswählen** (Abspielen /
  Fortsetzen / Auswahl / Information) an und zeigt den gewohnten Fortsetzen-Dialog.
* **Externe Player** aus `playercorefactory.xml` (MPC-BE, MPC-HC …) werden von Kodi anhand
  des Dateipfads gewählt – genau wie in der Bibliothek; „Abspielen mit …“ im Kontextmenü
  steht ebenfalls zur Verfügung.
* Wiedergabefortschritt und Gesehen-Status speichert **Kodi selbst** für diese Datei
  (`CSaveFileState` verwendet den Dateipfad) und damit für den Bibliotheksfilm. Das Add-on
  schreibt nichts in die Datenbank.

Angezeigt werden (alles live per JSON-RPC aus der Bibliothek, ohne Scraper):
Poster, Fanart und weitere Grafiken, Titel, Originaltitel, Jahr, Laufzeit, Genre, Handlung,
Tagline, FSK, Regie, Drehbuch, Studio, Land, Besetzung mit Fotos, Filmreihe, Tags,
IMDb-/TMDb-/weitere Bewertungen (inkl. der Standardbewertung der Bibliothek), eigene
Bewertung, Top 250, Gesehen-Status, Wiedergabefortschritt, zuletzt gesehen, hinzugefügt
am, Video-/Audio-/Untertitel-Streamdaten (Auflösungs-/Codec-Flags in Estuary), Trailer.
Die Ansicht ist als Inhaltstyp „movies“ deklariert, daher bietet Estuary alle Filmansichten
(Poster, Liste, Infowand, Wand, Fanart …).

---

## 5. Daten, Profile und MariaDB

* Gespeichert wird nur eine kleine JSON-Datei im Add-on-Profilordner
  `special://profile/addon_data/plugin.video.movieshortlist/shortlist.json`. Kodi löst
  `special://profile` pro Kodi-Profil auf → **jedes Profil hat seine eigene Liste**.
* Je Film werden nur `movieid` und zur Wiedererkennung Titel, Jahr, Dateipfad, Unique-IDs
  (IMDb/TMDb) und der Zeitpunkt des Hinzufügens gespeichert – keine Metadatenkopien.
* Die Liste übersteht Neustarts; geleert wird sie nur manuell.
* Schreiben erfolgt atomar (temporäre Datei + Umbenennen) mit einer einfachen Sperrdatei,
  damit Kontextmenü und Add-on gleichzeitig arbeiten können.
* Beim Anzeigen wird jeder Film per `VideoLibrary.GetMovieDetails` geprüft:
  * Gehört die ID inzwischen zu einem anderen Film (z. B. nach Neuaufbau der Bibliothek),
    wird der Film anhand Dateipfad/Unique-ID/Titel+Jahr **wiedergefunden** und die ID
    aktualisiert.
  * Ist der Film nicht mehr vorhanden, wird er still aus der Filmauswahl entfernt und eine
    Hinweismeldung angezeigt – ohne Fehler oder Abstürze.
* Ist die Videodatenbank nicht erreichbar (z. B. MariaDB-Server aus), erscheint
  „Die Videobibliothek ist nicht erreichbar“; die Liste bleibt dabei **unverändert**.
* Da ausschließlich Kodis JSON-RPC-API verwendet wird, funktioniert alles identisch mit
  SQLite und MySQL/MariaDB.

---

## 6. Fehlerbehandlung (Überblick)

| Situation | Verhalten |
|-----------|-----------|
| Film ohne Poster/Fanart | Kodi-Standardsymbol, Skin-Hintergrund |
| Fehlende Bewertungen | Feld bleibt leer; beim Sortieren nach IMDb am Ende |
| Keine IMDb-/TMDb-ID | Kein Problem, Wiedererkennung über Dateipfad oder Titel+Jahr |
| Film aus Kodi entfernt | Wird beim nächsten Anzeigen entfernt + Hinweis |
| Leere Filmauswahl | Hinweis-Eintrag in der Liste bzw. Meldung bei Zufallsauswahl/Leeren |
| MariaDB nicht erreichbar | Meldung, Liste bleibt erhalten, nichts wird gelöscht |
| Beschädigte `shortlist.json` | Datei wird als `shortlist.json.corrupt-<Zeit>` gesichert, Liste beginnt leer, Hinweis |
| Einzelne defekte Einträge | Werden übersprungen, Rest bleibt erhalten |
| Profilwechsel | Eigene Liste je Profil, Kontextmenü-Status wird neu gesetzt |
| Unerwartete Ausnahme | Meldung „siehe Kodi-Log“ + vollständiger Traceback im Log |

---

## 7. Bekannte Einschränkungen

1. **Kontextmenü-Umschaltung für max. 50 Filme.** Kodi wertet Sichtbarkeitsbedingungen
   ohne Python aus, daher gibt es eine feste Anzahl Vergleichs-Slots (die 50 zuletzt
   hinzugefügten Filme). Bei mehr als 50 Filmen zeigt die Bibliothek für ältere Einträge
   „hinzufügen“ statt „entfernen“; ein erneutes Hinzufügen wird aber erkannt
   („… ist bereits in der Filmauswahl“), und innerhalb der Filmauswahl funktioniert das
   Entfernen immer. Für einen Filmabend ist das praktisch nicht relevant.
2. **Direkt nach dem Kodi-Start** (bis der Dienst gestartet ist, ca. 1–2 Sekunden) kann
   noch „hinzufügen“ für bereits vorgemerkte Filme erscheinen – Duplikate werden trotzdem
   verhindert.
3. **Sortierung**: Die Reihenfolge wird über das Add-on gesteuert (Menüpunkt bzw.
   Einstellung). Kodis eigene Sortierauswahl im Seitenmenü bietet hier bewusst keine
   weiteren Optionen, um zwei konkurrierende Sortierungen zu vermeiden.
4. **Videoversionen (Kodi 21)**: Hat ein Film mehrere Versionen, wird – wie von JSON-RPC
   geliefert – die Standardversion abgespielt; Kodis Versionsauswahl erscheint nicht.
5. **Externe Player** melden Kodi keinen Wiedergabefortschritt; das ist in der Bibliothek
   genauso (Gesehen-Status gemäß Kodis Einstellungen für externe Player).
6. **Mehrere Kodi-Geräte mit gemeinsamer MariaDB** haben jeweils ihre eigene Filmauswahl,
   da die Liste im lokalen Profilordner liegt (die Datenbank wird ja nicht verändert).
7. Kodis eigene Kontextmenüeinträge (z. B. „Als gesehen markieren“, „Informationen“)
   stehen auch in der Filmauswahl zur Verfügung und wirken – wie in der Bibliothek – auf
   den Bibliotheksfilm. Das Add-on selbst schreibt niemals in die Bibliothek.

---

## 8. Getestete Funktionen

Getestet wurde **automatisiert** (die Tests laufen ohne Kodi mit nachgebildeten
Kodi-Modulen) sowie durch **statische Prüfung gegen die echte Kodi-21-API**:

* Alle verwendeten Kodi-Funktionen/Signaturen wurden mit `mypy` gegen
  **Kodistubs 21.0.0** (offizielle API-Stubs von Kodi 21) geprüft – keine erfundenen APIs.
* Kontextmenü-Mechanik, Wiedergabepfad, Fortschrittsspeicherung, Infodialog-„Abspielen“
  und JSON-RPC-Fehlercodes wurden im **Kodi-21-Quellcode (Branch „Omega“)** nachvollzogen.
* Alle angeforderten JSON-RPC-Felder sind gültige `Video.Fields.Movie` von Kodi 21.
* `kodi-addon-checker` (Branch omega) für Manifest/Struktur.

Automatisierte Tests (`python3 -m unittest discover -s tests`, 38 Tests):

| Bereich | Geprüft |
|---------|---------|
| Speicherung | Hinzufügen, Entfernen, Leeren, keine Duplikate, nur Referenzen gespeichert, Persistenz über Neustart, getrennte Profile, beschädigte Datei, defekte Einträge, verwaiste Sperrdatei |
| Bibliothek | DB nicht erreichbar (nichts wird gelöscht), entfernter Film, neue ID nach Neuaufbau, wiederverwendete ID, unbekannter Film, ausschließlich lesende JSON-RPC-Methoden |
| Sortierung | Alle fünf Sortierungen inkl. fehlender Werte und Umlaute |
| Liste | Hauptmenü, Inhaltstyp „movies“, Originaldateipfad + dbid, Metadaten/Bewertungen/Grafiken, fehlende Poster/Bewertungen/IDs, Fortschritt, leere Liste |
| Aktionen | Leeren nur nach „Ja“, Entfernen + Aktualisieren, Zufallsauswahl ohne Autostart und ohne direkte Wiederholung, Sortierwechsel, Fehlermeldung bei Ausnahme |
| Kontextmenü | Hinzufügen/Entfernen über `sys.listitem`, Fallback über Infolabels, Ablehnung von Nicht-Filmen, keine Container-Aktualisierung in der Bibliothek, Dienst |
| Manifest | Erweiterungspunkte, Dateien vorhanden, Slot-Anzahl, **Auswertung der Sichtbarkeitsbedingung** (exakter Vergleich, ID 12 ≠ 112, nicht in Episoden/Add-on), alle Texte in de_de und en_gb |

**Noch nicht durchgeführt:** ein Test auf einer echten Kodi-21.2-Installation unter
Windows 11 mit MPC-BE/MPC-HC und MariaDB (in der Entwicklungsumgebung steht kein Kodi zur
Verfügung). Empfohlene Abnahme-Checkliste:

- [ ] ZIP installieren, Add-on erscheint unter Video-Add-ons
- [ ] Kontextmenü in Poster-/Listen-/Infowand-Ansicht: hinzufügen → Meldung, Ansicht bleibt
- [ ] Gleicher Film: Eintrag lautet jetzt „Aus Filmauswahl entfernen“
- [ ] Filmauswahl in Poster/Liste/Infowand/Fanart, Bewertungen und Fortschrittsbalken sichtbar
- [ ] Film starten, stoppen, erneut auswählen → Fortsetzen-Dialog; Fortschritt auch in der Bibliothek
- [ ] Externer Player per `playercorefactory.xml` wird verwendet
- [ ] Zufallsauswahl → Infodialog → Abspielen
- [ ] Sortierungen, Leeren mit Ja/Nein, Kodi-Neustart, Profilwechsel
- [ ] MariaDB-Server stoppen → Meldung, Liste bleibt erhalten

---

## 9. Projektstruktur

```
plugin.video.movieshortlist/          ← Inhalt des ZIP
├── addon.xml                         Manifest (Plugin, Kontextmenü, Dienst, Metadaten)
├── main.py                           Einstieg Video-Add-on
├── context_add.py / context_remove.py  Einstieg Kontextmenü
├── service.py                        Einstieg Dienst
├── resources/
│   ├── settings.xml
│   ├── language/resource.language.de_de/strings.po
│   ├── language/resource.language.en_gb/strings.po
│   ├── media/                        icon.png, fanart.jpg, Menüsymbole
│   └── lib/
│       ├── common.py                 Add-on, Texte, Log, Benachrichtigungen
│       ├── storage.py                JSON-Speicherung im Profilordner
│       ├── library.py                Lesender JSON-RPC-Zugriff
│       ├── shortlist.py              Abgleich Liste ↔ Bibliothek
│       ├── listing.py                ListItems wie in der Bibliothek
│       ├── sorting.py                Sortierungen
│       ├── properties.py             Fenstereigenschaften für das Kontextmenü
│       ├── plugin.py                 Menü, Liste, Aktionen
│       ├── context.py                Kontextmenü-Aktionen
│       └── service.py                Dienst
tests/                                Unit-Tests mit Kodi-Nachbildung
tools/build_zip.py                    Baut dist/plugin.video.movieshortlist-<version>.zip
tools/update_context_conditions.py    Erzeugt die <visible>-Bedingungen in addon.xml
dist/                                 Installierbares ZIP
```

Lizenz: MIT
