# Mgroup Panel für Home Assistant

Lokale Bluetooth-Integration für das **MG-P1SR-12P**. Zwölf Kanalschalter und ein gemeinsamer Warnblinker mit
konfigurierbaren Kanalnamen, Zustandsrückmeldungen und Wiederverbindung.
Aktuelles Installationspaket: [mgroup_light-0.3.0.zip](https://github.com/highTowerSU/mgroup-light/releases/download/v0.3.0/mgroup_light-0.3.0.zip).
Getestetes Zielsystem: Home Assistant OS, Core 2026.10.4, lokaler Bluetooth-Adapter.
Unterstützt wird das Modell MG-P1SR-12P mit zwölf Kanälen.

## Verhalten

Die Einrichtung fragt ausschließlich den Zustand ab. Sie verändert keine
Ausgänge und stellt beim Neustart keine zuvor gespeicherten Zustände wieder her.
Schaltaktionen lesen zunächst den aktuellen Gesamtzustand. Sie ändern nur das
angeforderten Zustandsbits und erhalten die Kanalbetriebsarten sowie alle übrigen
Kanäle und lesen danach die Rückmeldung. Gleichzeitig eingehende Aktionen
werden nacheinander ausgeführt.

Der zusätzliche Schalter **Warnblinker** schaltet Kanal 7 und 8 mit einem
gemeinsamen F5-Telegramm ein oder aus. Er zeigt „ein“ an, wenn beide Blinker
eingeschaltet sind. Die einzelnen Blinkerschalter bleiben bedienbar.

Die vorhandene Betriebsart eines Kanals bleibt aktiv, auch bei Impuls- oder
Blinkfunktionen. Die Integration stellt diese Betriebsarten nicht um.
Ist der Gesamtschalter am Panel aus, wird ein Kanalbefehl abgewiesen; die
Integration aktiviert den Gesamtschalter nicht automatisch.
Bei Funkverlust werden die Entitäten als nicht verfügbar angezeigt.
Fehlgeschlagene Schaltbefehle werden nicht automatisch wiederholt.
Wird das Panel im passiven Scan nicht gefunden, fordert die Integration bei HA
ein aktives Suchfenster ausschließlich für seine Adresse an (bis zu 25 Sekunden).

## Installation über die Weboberfläche

Die Integration unterstützt den Import als **benutzerdefiniertes HACS-Repository**.
Repository: [highTowerSU/mgroup-light](https://github.com/highTowerSU/mgroup-light). Ein ZIP lässt sich in Home Assistant selbst nicht als
Integration hochladen. Die Vorbereitung für HACS folgt den
[HACS-Vorgaben](https://hacs.dev/docs/publish/integration/).

1. In HACS über das Menü **Benutzerdefinierte Repositories** `https://github.com/highTowerSU/mgroup-light`
   hinzufügen, Kategorie **Integration** wählen und **Mgroup Panel** herunterladen.
2. Home Assistant neu starten.
3. Unter **Einstellungen → Geräte & Dienste** das automatisch erkannte Panel
   bestätigen. Alternativ **Integration hinzufügen → Mgroup Panel** wählen.
4. Ein gefundenes Panel auswählen oder dessen Bluetooth-Adresse manuell eingeben.
5. Nach erfolgreicher Verbindung die zwölf Kanalnamen vergeben und abschließen.
   Der Warnblinker für Kanal 7 und 8 wird automatisch hinzugefügt.

Die Namen lassen sich später über **Konfigurieren** ändern. Das Panel muss
in Bluetooth-Reichweite eines HA-Adapters oder eines aktiven Bluetooth-Proxys
liegen. Eine andere App darf die Verbindung nicht belegen.

Bei bereits eingerichteten Panels bleiben Adressen, Kanalnamen und Entitäts-IDs
bei einem Update erhalten. Eine erneute Ersteinrichtung ist nicht erforderlich.

### Veröffentlichung vorbereiten

```sh
python3 tools/build_repository.py --repository https://github.com/OWNER/REPOSITORY
```

Das erzeugt `dist/mgroup_light-repository.zip` mit Integrationscode, README,
HACS-Metadaten und Tests. Das Manifest enthält die angegebene Repository-Adresse
für Dokumentation und Fehlerberichte sowie den Repository-Eigentümer als
Codeowner. Bei einer Organisation den verantwortlichen GitHub-Benutzer im
Manifest eintragen. Archiv entpacken und den Inhalt im angegebenen Repository
veröffentlichen. HACS lädt anschließend den Standardbranch; Release-ZIPs werden
nicht vorausgesetzt. Eine Aufnahme in den allgemeinen HACS-Katalog ist ein
separater Schritt, sie erfolgt nicht automatisch.

Das Veröffentlichungsarchiv enthält keine Geräte-Mitschnitte, Zugangsdaten,
Original-App oder lokal erstellten Installationsnachweise.

### Manuelle Installation

Den Ordner `custom_components/mgroup_light` aus dem Installationspaket nach
`/config/custom_components/mgroup_light` kopieren und Home Assistant neu starten.
Danach dieselbe Ersteinrichtung über **Geräte & Dienste** verwenden.
Zum Entfernen den Integrationseintrag löschen, danach bei Bedarf den Ordner
entfernen und HA neu starten. Das Panel wird beim Entladen nicht geschaltet.

## Prüfung

```sh
python3 -m pip install -r requirements-test.txt
python3 -m unittest discover -s tests -v
python3 -m compileall -q custom_components tools
```

Die 30 Tests verwenden echte zuvor gelesene Telegramme sowie einen simulierten
Bluetooth-Transport. Sie prüfen insbesondere Betriebsarterhaltung,
gleichzeitige Kanalbefehle, Verbindungsabbrüche, fehlende Rückmeldungen und die
aktive Suche bei fehlender oder veralteter Gerätesichtung.
Die zusätzlichen Formularprüfungen decken Geräteauswahl, Doppeleinrichtung,
Verbindungsfehler und die Vergabe der Namen bei der Ersteinrichtung ab.
Ein direkter Schaltversuch an Kanal 7 und die zwölf Kanalschalter sowie der
Warnblinker wurden auf dem genannten Zielsystem geprüft. Wiederkehrende
Statusabfragen erfolgen im Abstand von 30 Sekunden.
