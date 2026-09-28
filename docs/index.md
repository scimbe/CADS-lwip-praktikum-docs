# lwIP-Praktikum auf cads-zero

In diesem Praktikum baut ihr Netzwerkfunktionen selbst in die Firmware eines
Mikrocontroller-Boards ein und prüft sie anschließend von eurem eigenen Rechner
aus nach. Grundlage ist der TCP/IP-Stack [lwIP](https://savannah.nongnu.org/projects/lwip/)
auf dem ITS-Board (STM32F429, Ethernet-PHY LAN8742A, Display ILI9486) mit der
Firmware **cads-zero** ([Quelltext](https://github.com/scimbe/cads-zero-firmware/tree/praktikum/start)).

Jeder Termin folgt demselben Muster: Ihr notiert **vor** der Messung einen
Erwartungswert, ergänzt die Firmware um ein kleines Stück Protokolllogik,
messt mit Wireshark und dem Host-Werkzeug
[`rnlab.py`](reference/rnlab-tool.md) und erklärt die Abweichung zwischen
Erwartung und Messung.

--8<-- "issue-feedback.md"

## Termine

| Termin | # | Thema | Skript | Netz-Setup | Firmware-Aufgabe (Kern) |
|---|---|---|---|---|---|
| T01 | [00](labs/00-onboarding.md) | Onboarding | 5.2, 5.9 | S1 | Image wählen, Fork, bauen/flashen, `lab info`, ping |
| T02 | [01](labs/01-schichten-kapselung.md) | Schichten & Kapselung | 5.6, 5.9 | S1 | Frame-Dekoder Ethernet → IPv4 → ICMP/UDP/TCP |
| T03 | [02](labs/02-ethernet-arp.md) | Ethernet & ARP | 5.15 | S1 | ARP-Cache-Dump, Gratuitous ARP, ARP-Parser |
| T04 | [03](labs/03-ipv4-subnetting.md) | IPv4 & Subnetting | 5.11–5.14 | S1 | IPv4-Eingangsfilter, Netzmaske, `rnlab_same_subnet()` |
| T05 | [04](labs/04-icmp.md) | ICMP | 5.16 | S1 | Eigener Echo-Responder, RTT-Statistik |
| T06 | [05](labs/05-dhcp.md) | DHCP | 5.22 | S2 | DHCP-Zustand, Lease, T1/T2 |
| T07 | [06](labs/06-dns-nat.md) | DNS & NAT | 5.21, 5.23 | S2 | Namensauflösung, DNS-Antwort-Parser |
| T08 | [07](labs/07-udp-transport.md) | UDP-Transport | 5.25 | S1 | UDP-Sink mit Verlust-/Reorder-Zählern |
| T09 | [08](labs/08-tcp-flusskontrolle.md) | TCP-Flusskontrolle | 5.26–5.30 | S1 | TCP-Sink, Empfangsfenster `TCP_WND` |
| T10 | [09](labs/09-congestion-control.md) | Congestion Control | 5.31 | S1 | cwnd/ssthresh-Trace, gezielte Verluste |
| T11 | [10](labs/10-http-wetter-1.md) | HTTP-Client für Wetterdaten | 5.36, 5.23 | S2 | HTTP/1.0-Client, JSON-Extraktor |
| T12 | [11](labs/11-wetter-app.md) | Wetter-App | 5.36 | S2 | GUI-App mit zyklischem Abruf |

Die Kapitelangaben beziehen sich auf das Skript zur Vorlesung Rechnernetze.
Die beiden Netz-Setups **S1** (statische Adresse) und **S2** (Internetfreigabe
des eigenen Rechners) sind für macOS, Windows und Linux in der
[Netz-Setup-Referenz](reference/netz-setup.md) beschrieben.

## Voraussetzungen

- **Hardware:** ITS-Board mit Ethernet, USB-Kabel zum Board, ein
  Ethernet-Anschluss am eigenen Rechner (eingebaut oder USB-Ethernet-Adapter)
  und ein Patchkabel.
- **Eigener Rechner** mit macOS, Windows oder Linux – alle drei sind
  gleichwertig unterstützt. Für die Netzwerkkonfiguration braucht ihr
  Administratorrechte; die Messwerkzeuge selbst laufen ohne.
- **Wireshark** und **Python 3.9 oder neuer** (nur Standardbibliothek) auf dem
  eigenen Rechner, siehe [Netz-Setup](reference/netz-setup.md#wireshark-installieren)
  und [`rnlab.py`](reference/rnlab-tool.md).
- **Chrome oder Chromium** zum Flashen und für die
  [serielle Konsole](reference/serielle-konsole.md) aus dem
  [Firmware-Labor-Image](reference/firmware-lab-image.md).
- Grundkenntnisse in C sowie der Stoff der Vorlesung bis zum jeweiligen
  Skriptkapitel.

## Bewertung

!!! note "Wird noch festgelegt"
    Die Bewertungs- und Abnahmekriterien werden vor Beginn des Semesters an
    dieser Stelle veröffentlicht.

--8<-- "konventionen.md"

## Umgebung & Zugang

Gebaut und geflasht wird im browserbasierten Image **CADS Firmware-Labor**
(code-server mit Toolchain). Board und Ethernet hängen dabei an eurem eigenen
Rechner; gemessen wird ebenfalls dort. Details:
[Firmware-Labor-Image](reference/firmware-lab-image.md).

--8<-- "issue-feedback.md"
