# ESP32-Fernbedienung: Entwurf, noch keine Firmware

Ziel ist die Steuerung des MG-P1SR-12P auch dann, wenn Home Assistant nicht
läuft. Das vorhandene BLE-Protokoll ist bereits am Panel geprüft.

## Zwei Betriebsweisen

Ein aktiver ESPHome-Bluetooth-Proxy kann die vorhandene Home-Assistant-
Integration über WLAN mit dem Panel verbinden. Die eigentliche Steuerlogik
läuft dann weiterhin in Home Assistant. Das ist eine Funkbrücke, aber keine
unabhängige Fernbedienung.

Für unabhängige Bedienung wäre ein ESPHome-Gerät mit einem eigenen
Mgroup-BLE-Client sinnvoll. GPIO-Tasten, ein Display oder eine lokale
Weboberfläche könnten den Client direkt bedienen. Home Assistant greift
zusätzlich über die native ESPHome-API auf die Schalter, Betriebsarten und RGB-
Beleuchtung zu. Der ESP übernimmt dann exklusiv die Bluetooth-Steuerung;
der bisherige direkte HA-BLE-Client darf nicht gleichzeitig dasselbe Panel
beanspruchen. Der Wechsel und die vorhandenen Automationsziele müssen bei
der späteren Einrichtung berücksichtigt werden.

## Anforderungen an den Treiber

- Als GATT-Client verbinden, Notifications auf effa abonnieren und mit
  Write Without Response schreiben. Keine bloßen BLE-Werbe-Broadcasts.
- Vor jedem Schaltbefehl den aktuellen Zustand abfragen und alle fremden
  Zustands- und Betriebsartbits erhalten. Warnblinker 7/8 atomar schalten.
- Schreibaktionen serialisieren und echte Rückmeldungen verwenden.
- Nach Start oder Wiederverbindung zuerst einlesen; keine gespeicherten
  Einschaltzustände oder fehlgeschlagenen Impulse automatisch wiederholen.
- Lokale Tasten unabhängig von HA- und WLAN-Verfügbarkeit ausführen.
  Insbesondere ESPHome-API-/WLAN-Neustarttimer für diesen Betrieb passend
  konfigurieren; Verbindungsverlust darf keine unbeabsichtigte Schaltung auslösen.
- Ein-/Ausschaltanforderungen für den HA-Versorgungskanal getrennt von einem
  bewusst freigegebenen endgültigen Ausschaltbefehl behandeln.

Ein ESP32 außerhalb des HA-Rechners könnte später auch die endgültige
Stromtrennung nach dem Shutdown übernehmen. Eine fehlende WLAN-Verbindung oder
ein fehlgeschlagener Ping ist aber kein Beleg für einen abgeschlossenen
Shutdown. Dafür sind ein verlässliches Abschaltsignal und eine unabhängige
Versorgung des ESP zu planen.

## Festgelegte Richtung und Hardwareprofile

Der Controller soll unabhängig von Home Assistant arbeiten. Die Tastenanzahl
wird nicht im BLE-Treiber fest verdrahtet. Eingänge bekommen Zuordnungen zu
Kanal-Ein/Aus/Umschalten, Warnblinker, RGB oder Abschaltanforderung. Taster
und rastende Schalter benötigen unterschiedliche Eingangsregeln.

Vorgesehene Profile sind ein ESP32-S3 mit 3x4-Tastenmatrix für zwölf Eingänge
und eine Variante mit vier GPIO-Eingängen, beispielsweise für einen geeigneten
Shelly Plus i4 DC. Beide verwenden denselben Protokollbaustein, aber ein
jeweils passend kompiliertes Firmware-Image. Ein i4 DC hat vier Eingänge für
externe Tasten/Schalter; er ist kein fertiges Gerät mit vier eingebauten Tasten.
Die genaue Pinbelegung und die BLE-Client-Funktion sind am ausgewählten Modell
zu verifizieren. Der i4 DC verwendet laut Hersteller ESP32-U4WDH und 5–24 V DC.

Als fertig aufgebauter weiterer Kandidat existiert DeepDeck mit ESP32 und
16 mechanischen Tasten. Davon könnten zwölf die Kanäle bedienen und vier
Zusatzfunktionen auslösen. Dafür wäre ebenfalls angepasste Firmware nötig.
Ein beliebiges Bluetooth-Makropad mit Tastaturprofil kann die GATT-Befehle des
Panels nicht ohne Weiteres senden.

Bei mehreren Bediengeräten ist zusätzlich eine zentrale BLE-Gateway-Rolle
sinnvoll. Weitere Geräte senden ihre Befehle direkt an diesen Controller,
ohne einen auf dem HA-Rechner laufenden Dienst vorauszusetzen. Damit gibt es
nur einen Bluetooth-Besitzer und eine zentrale Reihenfolge der Zustandsänderungen.
Das lokale Transportprotokoll wird erst im nächsten Entwurf festgelegt.

Referenzen: [Matrix-Keypad](https://esphome.io/components/matrix_keypad/),
[Shelly Plus i4 DC](https://www.shelly.com/it/products/shelly-plus-i4-dc),
[DeepDeck](https://github.com/DeepSea-Developments/DeepDeck.Ahuyama.fw).

## Noch zu entscheiden

Welches ESP32-Board steht zur Verfügung? Welche lokalen Bedienelemente werden
gewünscht? Soll der ESP dauerhaft versorgt werden, und welche Rolle soll er
beim späteren Abschalten übernehmen? Vor diesen Entscheidungen werden keine
GPIO-Pins festgelegt und kein konkretes Firmware-Image erstellt.

Quellen: [ESPHome BLE Client](https://esphome.io/components/ble_client/),
[Bluetooth Proxy](https://esphome.io/components/bluetooth_proxy/),
[native API](https://esphome.io/components/api/),
[WiFi](https://esphome.io/components/wifi/).
