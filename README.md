# Mgroup Panel für Home Assistant

Lokale Bluetooth-Integration für das **MG-P1SR-12P**. Zwölf Kanalschalter und ein gemeinsamer Warnblinker mit
konfigurierbaren Kanalnamen, Zustandsrückmeldungen und Wiederverbindung.
Aktuelles Installationspaket: [mgroup_light-0.4.1.zip](https://github.com/highTowerSU/mgroup-light/releases/download/v0.4.1/mgroup_light-0.4.1.zip).
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

## Betriebsarten und Beleuchtung

Jeder Kanal hat eine Betriebsart-Auswahl: **Dauerbetrieb**, **Momenttaster**,
**Blinken (Flash)** oder **Stroboskop**. Der Kanal muss beim Ändern ausgeschaltet
sein. Der konfigurierte HA-Versorgungskanal ist zusätzlich gegen Änderungen der
Betriebsart geschützt. Die übrigen Kanalzustände bleiben erhalten.

Die Entität **Tastenbeleuchtung** liest die gemeinsame RGB-Palette und die
Helligkeit über F1–F4 ein. Eine einzelne Farbe wird als RGB-Farbe angezeigt;
bei einer Palette mit mehreren Farben steht die vollständige Palette in den
Attributen. Der momentan sichtbare Farbton eines laufenden Farbwechsels wird
vom Protokoll nicht als Messwert gemeldet. Eine Farbauswahl setzt eine statische
RGB-Farbe. Ein/Aus der Beleuchtung verändert deren Helligkeit und erhält den
Geräte-Power-Status. Fehlende RGB-Rückmeldung macht nur die Lichtentität
unverfügbar. Schreibbefehle werden anschließend zurückgelesen.

## Abschaltanforderung für Home Assistant

Unter **Konfigurieren** lassen sich zwei optionale Kanäle wählen (0 = deaktiviert):

- **HA-Versorgungskanal:** Ein Software-Ausschaltbefehl erzeugt ausschließlich
  `mgroup_light_shutdown_requested` und lässt den Ausgang eingeschaltet.
- **Anforderungskanal:** Ein beobachteter Wechsel von aus nach ein erzeugt
  dasselbe Ereignis. Dafür einen unbeschalteten Ausgang verwenden. Auch ein
  Schaltbefehl aus der App kann den Wechsel verursachen; das Protokoll meldet
  keine eindeutige Herkunft des Tastendrucks.

Zusätzlich gibt es **Herunterfahren anfordern** als Button-Entität. Die Integration
führt selbst keinen Host-Shutdown aus. Das übernimmt eine Automation, zum
Beispiel der [mitgelieferte Blueprint](blueprints/automation/mgroup_light/shutdown_request.yaml).
Das Ereignis enthält `address`, `source` und `channel`. Die erste Zustandsmeldung
nach Start oder Wiederverbindung löst keine Abschaltanforderung aus.

Ein physischer Schaltvorgang am stromversorgenden Ausgang lässt sich über
Bluetooth nicht abfangen. Nach `hassio.host_shutdown` kann HA selbst keinen
nachfolgenden Bluetooth-Ausschaltbefehl mehr ausführen. Zum Puffern oder
anschließenden Trennen der Versorgung ist unabhängige Hardware nötig.

## Optionale StromPi-2-Anzeige

**Konfigurieren → StromPi 2 an lokalem GPIO 21 überwachen** ergänzt ein eigenes
Gerät **StromPi 2** mit dem Binärsensor **USV-Signal**. Es werden ausschließlich
die Eingangsregister von BCM21 über `/dev/gpiomem` gelesen; Pinmodus und Ausgänge
werden nicht verändert. Der T-PIN-Jumper muss tatsächlich mit BCM21 verbunden
sein. High bedeutet dann fehlende Micro-USB-Primärversorgung. Ohne diese
Verbindung kann ein Pegel keine zuverlässige Aussage zur Stromversorgung liefern.

Diese optionale Anzeige ist für Raspberry Pis mit der älteren gpiomem-Schnittstelle
vorgesehen, getestet auf einem Pi 3. Ohne Zugriff auf `/dev/gpiomem` bleibt sie
unverfügbar. Es werden keine Spannungs-, Strom- oder Akkustandswerte erfunden.
Die Überwachung löst selbst keinen Shutdown aus. Insbesondere bei Betrieb allein
über den Weitbereichseingang darf High keine automatisch aktivierte
Ausfall-Automation auslösen. Die Eingangspriorität und ein Abschalttimer sind beim
StromPi 2 nicht per Software einstellbar; siehe [Herstelleranleitung](https://www.joy-it.net/files/files/Produkte/RB-StromPI2/Anleitung-Strompi2.pdf).

Der [StromPi-2-Aufbauvorschlag](STROMPI2.md) beschreibt die Versorgung über
dauerhafte 12 V und eine zusätzliche geschaltete 5-V-Quelle.

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

Die 64 Tests verwenden echte zuvor gelesene Telegramme sowie einen simulierten
Bluetooth-Transport. Sie prüfen insbesondere Betriebsarterhaltung,
gleichzeitige Kanalbefehle, Verbindungsabbrüche, fehlende Rückmeldungen und die
aktive Suche bei fehlender oder veralteter Gerätesichtung.
Die zusätzlichen Formularprüfungen decken Geräteauswahl, Doppeleinrichtung,
Verbindungsfehler und die Vergabe der Namen bei der Ersteinrichtung ab.
Ein direkter Schaltversuch an Kanal 7 und die zwölf Kanalschalter sowie der
Warnblinker wurden auf dem genannten Zielsystem geprüft. Wiederkehrende
Statusabfragen erfolgen im Abstand von 30 Sekunden.
