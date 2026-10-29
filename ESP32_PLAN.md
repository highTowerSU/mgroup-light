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

## Noch zu entscheiden

Welches ESP32-Board steht zur Verfügung? Welche lokalen Bedienelemente werden
gewünscht? Soll der ESP dauerhaft versorgt werden, und welche Rolle soll er
beim späteren Abschalten übernehmen? Vor diesen Entscheidungen werden keine
GPIO-Pins festgelegt und kein konkretes Firmware-Image erstellt.

Quellen: [ESPHome BLE Client](https://esphome.io/components/ble_client/),
[Bluetooth Proxy](https://esphome.io/components/bluetooth_proxy/),
[native API](https://esphome.io/components/api/),
[WiFi](https://esphome.io/components/wifi/).
