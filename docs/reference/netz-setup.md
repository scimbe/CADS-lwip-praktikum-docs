# Netz-Setup (S1/S2)

Das ITS-Board hängt per Ethernet direkt an eurem eigenen Rechner – entweder an
einer eingebauten Ethernet-Buchse oder an einem USB-Ethernet-Adapter. Im
Praktikum gibt es genau zwei Konfigurationen dieser Punkt-zu-Punkt-Verbindung:

| Setup | Termine | Rechner | Board |
|---|---|---|---|
| **S1 statisch** | 00–04, 07–09 | `192.168.33.10/24` auf dem Board-Adapter | `192.168.33.99/24` (Standard nach dem Flashen) |
| **S2 Internetfreigabe** | 05, 06, 10, 11 | Rechner teilt seinen Internetzugang und ist DHCP-Server und NAT-Router | Adresse per DHCP (`lab net dhcp`) |

Jede Versuchsseite nennt oben ihr Setup. Alle Befehle unten betreffen **nur**
die Schnittstelle, an der das Board hängt – euer WLAN oder euer normales
Netz bleibt unverändert.

--8<-- "issue-feedback.md"

## Board-Schnittstelle finden

Steckt den Adapter an und verbindet das Board, **bevor** ihr die Schnittstelle
sucht: manche Systeme zeigen eine Schnittstelle ohne Link gar nicht oder nur
als „inaktiv“ an.

=== "macOS"

    ```bash
    networksetup -listallhardwareports
    ```

    Gesucht ist der Eintrag mit dem Namen eures Adapters (z. B.
    `USB 10/100/1000 LAN`); `Device:` nennt den Gerätenamen (z. B. `en7`), die
    Zeile `Hardware Port:` den Dienstnamen für `networksetup`.

=== "Windows"

    ```powershell
    netsh interface ipv4 show interfaces
    ```

    Gesucht ist die Zeile mit Status `connected`, die beim Abziehen des Kabels
    auf `disconnected` wechselt (z. B. `Ethernet 2`). Der Name in der letzten
    Spalte wird unten als `"Ethernet 2"` eingesetzt.

=== "Linux"

    ```bash
    ip -br link
    ```

    USB-Adapter heißen meist `enx<MAC-Adresse>`, eingebaute Buchsen `enp…` oder
    `eth0`. Der Link muss `UP` bzw. `LOWER_UP` zeigen, sobald das Board läuft.

## S1 – statische Adresse

Der Rechner bekommt auf der Board-Schnittstelle die Adresse `192.168.33.10/24`,
das Board hat nach dem Flashen `192.168.33.99/24`. Ein Default-Gateway wird
**nicht** eingetragen: beide liegen im selben Subnetz, die Route dorthin legt
das Betriebssystem mit der Adresse automatisch an.

=== "macOS"

    **Dauerhaft (empfohlen)** über *Systemeinstellungen → Netzwerk → Adapter →
    Details → TCP/IP*: „IPv4 konfigurieren“ auf **Manuell**, IP-Adresse
    `192.168.33.10`, Teilnetzmaske `255.255.255.0`, Router leer lassen.

    Gleichwertig im Terminal (Dienstname aus `networksetup -listallhardwareports`):

    ```bash
    sudo networksetup -setmanual "USB 10/100/1000 LAN" 192.168.33.10 255.255.255.0
    # zurück zu DHCP:
    sudo networksetup -setdhcp "USB 10/100/1000 LAN"
    ```

    **Nur bis zum Abziehen/Neustart** als zusätzliche Adresse:

    ```bash
    sudo ifconfig en7 alias 192.168.33.10 255.255.255.0
    # entfernen:
    sudo ifconfig en7 -alias 192.168.33.10
    ```

=== "Windows"

    In einer **Eingabeaufforderung als Administrator**:

    ```powershell
    netsh interface ipv4 set address name="Ethernet 2" static 192.168.33.10 255.255.255.0
    # zurück zu DHCP:
    netsh interface ipv4 set address name="Ethernet 2" dhcp
    ```

    `netsh interface ipv4 add address …` fügt eine *zusätzliche* Adresse hinzu,
    funktioniert aber nur, wenn die Schnittstelle bereits statisch konfiguriert
    ist; auf einer DHCP-Schnittstelle bricht der Befehl ab. Für den Adapter,
    der nur das Board versorgt, ist `set address … static` deshalb der
    einfachere Weg. PowerShell-Alternative:

    ```powershell
    New-NetIPAddress -InterfaceAlias "Ethernet 2" -IPAddress 192.168.33.10 -PrefixLength 24
    ```

    Beim ersten Ping fragt die Windows-Firewall eventuell nach dem Netzwerktyp
    der neuen Verbindung; „Privat“ ist hier passend.

=== "Linux"

    **Nur bis zum Abziehen/Neustart:**

    ```bash
    sudo ip addr add 192.168.33.10/24 dev enx001122334455
    # entfernen:
    sudo ip addr del 192.168.33.10/24 dev enx001122334455
    ```

    **Dauerhaft mit NetworkManager** (eigene Verbindung, die ihr gezielt
    aktiviert):

    ```bash
    nmcli connection add type ethernet ifname enx001122334455 con-name rnlab-s1 \
        ipv4.method manual ipv4.addresses 192.168.33.10/24 ipv6.method disabled
    nmcli connection up rnlab-s1
    ```

    Läuft NetworkManager und verwaltet die Schnittstelle, kann er eine per
    `ip addr` gesetzte Adresse beim nächsten Link-Wechsel wieder entfernen –
    dann die `nmcli`-Variante nehmen.

**Prüfen:**

```bash
ping 192.168.33.99
python3 tools/rnlab.py check --board 192.168.33.99
```

`rnlab.py check` meldet u. a., über welche lokale Adresse euer Rechner das
Board erreichen würde. Steht dort nicht `192.168.33.10`, ist die Adresse auf der
falschen Schnittstelle gelandet.

## S2 – Internetfreigabe

Für DHCP, DNS/NAT und die Wetter-Versuche braucht das Board einen Weg ins
Internet. Euer Rechner teilt dazu seinen Internetzugang (meist WLAN) mit der
Board-Schnittstelle: er wird dort **DHCP-Server, DNS-Weiterleiter und
NAT-Router**. Das Board holt sich seine Adresse per DHCP – auf der seriellen
Konsole bzw. per Telnet:

```text
lab net dhcp
lab info
```

!!! warning "Vorher S1 zurücknehmen"
    Die Internetfreigabe konfiguriert die Board-Schnittstelle selbst. Eine
    noch gesetzte statische S1-Adresse stört dabei. Stellt die Schnittstelle
    vorher auf DHCP zurück bzw. entfernt die zusätzliche Adresse (siehe S1).
    Zurück zu S1 geht es umgekehrt: Freigabe aus, S1 einrichten, auf dem Board
    `lab net static`.

| Betriebssystem | Adresse des Rechners | Netz des Boards |
|---|---|---|
| macOS Internetfreigabe | `192.168.2.1` | `192.168.2.0/24` |
| Windows ICS | `192.168.137.1` | `192.168.137.0/24` |
| Linux NetworkManager `shared` | `10.42.0.1` | `10.42.0.0/24` |

=== "macOS"

    *Systemeinstellungen → Allgemein → Teilen → Internetfreigabe*
    (ältere Versionen: *Freigaben*): „Verbindung freigeben von“ **WLAN**, „Mit
    Computern über“ **euer Board-Adapter**, dann die Freigabe einschalten.

    macOS legt eine Bridge-Schnittstelle (meist `bridge100`) mit
    `192.168.2.1/24` an und vergibt Adressen aus diesem Netz. Anzeige:

    ```bash
    ifconfig bridge100
    ```

=== "Windows"

    *Systemsteuerung → Netzwerk- und Freigabecenter → Adaptereinstellungen
    ändern* (oder `ncpa.cpl`) → Rechtsklick auf den **Internet-Adapter**
    (z. B. WLAN) → *Eigenschaften → Freigabe*: „Anderen Benutzern im Netzwerk
    gestatten, diese Verbindung des Computers als Internetverbindung zu
    verwenden“ aktivieren und als Heimnetzwerkverbindung **euren
    Board-Adapter** (z. B. `Ethernet 2`) wählen.

    Windows setzt den Board-Adapter dabei fest auf `192.168.137.1/24`. Prüfen:

    ```powershell
    netsh interface ipv4 show addresses "Ethernet 2"
    ```

=== "Linux"

    NetworkManager startet für eine `shared`-Verbindung einen eigenen
    DHCP-/DNS-Dienst (dnsmasq) und richtet NAT ein:

    ```bash
    nmcli connection add type ethernet ifname enx001122334455 con-name rnlab-s2 \
        ipv4.method shared ipv6.method disabled
    nmcli connection up rnlab-s2
    # zurück zu S1:
    nmcli connection up rnlab-s1
    ```

    Der Rechner erhält `10.42.0.1/24`. Blockiert eine lokale Firewall
    (firewalld, ufw) DHCP oder das Weiterleiten, bekommt das Board keine
    Adresse bzw. kein Internet; bei firewalld hilft es, die Schnittstelle der
    Zone `trusted` zuzuordnen.

## Das Board finden

In S1 ist die Adresse bekannt: `192.168.33.99`. In S2 vergibt euer Rechner die
Adresse; ihr findet sie auf drei Wegen:

1. **Auf dem Board:** `lab info` auf der seriellen Konsole zeigt die per DHCP
   erhaltene Adresse.
2. **In der ARP-Tabelle des Rechners** (nach dem ersten Datenverkehr):

    === "macOS"

        ```bash
        arp -a -i bridge100
        ```

    === "Windows"

        ```powershell
        arp -a -N 192.168.137.1
        ```

    === "Linux"

        ```bash
        ip neigh show dev enx001122334455
        ```

3. **In den DHCP-Leases des Rechners:**

    === "macOS"

        ```bash
        cat /var/db/dhcpd_leases
        ```

    === "Windows"

        ICS führt keine für Benutzer lesbare Lease-Liste; hier `arp -a` nutzen
        oder in Wireshark auf `dhcp` filtern und das DHCP-ACK ablesen.

    === "Linux"

        ```bash
        cat /var/lib/NetworkManager/dnsmasq-enx001122334455.leases
        ```

Unabhängig vom Betriebssystem zeigt ein Wireshark-Mitschnitt auf der
Board-Schnittstelle mit dem Anzeigefilter `dhcp` den kompletten Ablauf
(Discover, Offer, Request, ACK) samt vergebener Adresse.

## Wireshark installieren

=== "macOS"

    Installer von [wireshark.org](https://www.wireshark.org/download.html) oder
    per Homebrew:

    ```bash
    brew install --cask wireshark
    ```

    Damit ohne `sudo` mitgeschnitten werden kann, muss **ChmodBPF**
    installiert sein (Teil des Installers bzw. bei Homebrew mit
    installiert); danach einmal ab- und wieder anmelden.

=== "Windows"

    Installer von [wireshark.org](https://www.wireshark.org/download.html).
    Im Installer **Npcap** mitinstallieren – ohne Npcap kann Wireshark unter
    Windows nicht mitschneiden.

=== "Linux"

    ```bash
    sudo apt install wireshark        # Debian/Ubuntu
    sudo dnf install wireshark        # Fedora
    sudo usermod -aG wireshark "$USER"
    ```

    Unter Debian/Ubuntu die Frage, ob Nicht-Superuser mitschneiden dürfen, mit
    **Ja** beantworten (nachträglich: `sudo dpkg-reconfigure wireshark-common`).
    Die Gruppenmitgliedschaft wirkt erst nach erneutem Anmelden.

Mitgeschnitten wird immer auf der **Board-Schnittstelle** (in S2 unter macOS
alternativ auf `bridge100`). Ein Mitschnittfilter wie `host 192.168.33.99`
hält die Aufzeichnung klein.

--8<-- "issue-feedback.md"
