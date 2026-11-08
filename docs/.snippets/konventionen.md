!!! info "Konventionen in diesem Praktikum"
    - **Werkzeuge** ruft ihr aus dem Wurzelverzeichnis des Doku-Repositorys
      auf: `python3 tools/rnlab.py …` – unter Windows `py tools\rnlab.py …`.
    - **Ping** immer über `python3 tools/rnlab.py ping …`, nicht über das
      `ping` des Systems: gleiche Optionen auf allen Systemen, Statistik mit
      Standardabweichung und Perzentilen, unter Windows mit
      Mikrosekunden-Auflösung ([Details](/reference/rnlab-tool.md#ping)).
    - **Tasten des Boards** fernbedienen: `lab key <taste>` auf der
      [seriellen Konsole](/reference/serielle-konsole.md) oder per Telnet
      ([Tastennamen](/reference/serielle-konsole.md#tasten-des-boards-fernbedienen)).
    - **Firmware-Stellen** stehen als Pfad in eurem Fork, z. B.
      `apps/rnlab/src/l03_ipv4_subnetting.c`, dazu ein Link auf den Startstand
      `praktikum/start` im öffentlichen Repository
      [cads-zero-firmware](https://github.com/scimbe/cads-zero-firmware).
    - **Host-Tests** im Terminal des Firmware-Labs aus `cads-zero`:
      `cmake --preset host` legt `build/host` an (nach einem frischen Start
      oder `git clean` nötig), danach `cmake --build build/host` und `ctest`.
      `ctest` zählt die Testdatei eines Versuchs als *einen* Test; die
      Einzeltests stehen in der Zeile `N Tests M Failures` darüber.
    - **macOS:** Meldet `rnlab.py lab` oder `check` „No route to host“, obwohl
      `ping` geht, fehlt die Freigabe *Lokales Netzwerk* für euer Terminal
      ([Details](/reference/rnlab-tool.md#macos-no-route-to-host-trotz-ping)).
