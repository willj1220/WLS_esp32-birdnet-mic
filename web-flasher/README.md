## Web flasher

Statická stránka pro nahrání firmware birdnet-esp32-rtsp-mic (BirdNET-Go / BirdNET-Pi, Seeed XIAO
ESP32-C3/S3/C5/C6) přímo z prohlížeče pomocí ESP Web Tools.

Aktuální připravené obrazy: **firmware 1.10.0** (2026-06-11).

ESP Web Tools podle připojeného čipu automaticky vybere položku manifestu `ESP32-C3`, `ESP32-S3`,
`ESP32-C5` nebo `ESP32-C6`. Neumí rozlišit různé desky se stejnou chip family, proto je manifest
určený pro Seeed XIAO desky s těmito čipy.

Poznámka k 1.10.0: obrazy přidávají XIAO ESP32-C3, XIAO ESP32-S3 a XIAO ESP32-C5 vedle původní
XIAO ESP32-C6. Fyzické zapojení mikrofonu je stejné podle XIAO pin labelů `D3`/`D1`/`D2`, ale GPIO
čísla se mezi čipy liší.

Poznámka k 1.9.3: obraz obsahuje doplněnou RTSP/UDP kompatibilitu pro BirdNET-Pi
(`RTP-Info`, `source`/`ssrc` a RTCP port handling). Bylo ověřeno proti čisté instalaci
`Nachtzuster/BirdNET-Pi` se streamem `/audio2` v BirdNET-Pi/UDP režimu.

Výchozí veřejné buildy:
- mají samostatný firmware pro XIAO ESP32-C3, XIAO ESP32-S3, XIAO ESP32-C5 a XIAO ESP32-C6,
- C6 build má zapnutou externí anténu přes RF switch GPIO3/GPIO14,
- C3/S3/C5 buildy nepoužívají firmware GPIO přepínání antény,
- nemá nastavené OTA heslo,
- patří jen do důvěryhodné lokální sítě.

Firmware 1.9.2 a novější obsahuje opravu velikosti buildu pro Arduino IDE: soubor
`esp32-birdnet-mic/build_opt.h` vypíná nepoužitá C++ exception/unwind metadata a drží těsné
defaultní 1.2 MB app partition na XIAO ESP32-C3/C6 pod limitem bez odebrání funkcí.

Firmware je určený pro I2S mikrofon **ICS-43434** jako referenční/testovanou volbu.
Mikrofon **INMP441** byl uživatelsky potvrzený jako kompatibilní bez změn firmwaru při stejném
I2S zapojení na stejných fyzických XIAO pinech (`SCK` -> D3, `WS` -> D1, `SD` -> D2); viz:
https://github.com/Sukecz/esp32-birdnet-mic/discussions/25

### Struktura
- `index.html` – hlavní stránka s tlačítkem „Flash“ a instrukcemi.
- `manifest.json` – manifest pro ESP Web Tools, zapisuje jen firmware části bez NVS a obsahuje C3/S3/C5/C6 buildy.
- `bootloader-<board>.bin`, `partitions-<board>.bin`, `boot_app0-<board>.bin` – systémové části pro USB web flash.
- `firmware-<board>.bin` – sloučený obraz (bootloader + partition + app), pouze pro ruční full flash.
- `firmware-app-<board>.bin` – app-only obraz pro OTA aktualizaci přes Web UI zařízení.
- `bootloader.bin`, `partitions.bin`, `boot_app0.bin`, `firmware.bin`, `firmware-app.bin` – kompatibilní C6 aliasy.
- `ota-version.txt` – jednoduchý text s verzí OTA buildu.

Manifest záměrně nepoužívá sloučený `firmware.bin` na offsetu `0x0`, protože by při aktualizaci
přepsal NVS oblast od `0x9000` vyplněnými `0xff` byty a smazal Wi-Fi i aplikační nastavení.
ESP Web Tools navíc u nerozpoznaného zařízení bere flash jako novou instalaci a defaultně maže celý
flash. Proto je v manifestu zapnuté `new_install_prompt_erase`; při aktualizaci je nutné zvolit
zachování existujících dat.

### OTA aktualizace bez USB
1. Otevři **https://esp32mic.msmeteo.cz**.
2. Do části **OTA update without USB** napiš IP adresu zařízení, například `192.168.1.80`.
3. Klikni **Open OTA update**.
4. Na stránce zařízení vyber jednu možnost:
   - **Automatic update**: zařízení si samo stáhne nejnovější board-specific app-only firmware z webu.
   - **Upload compiled file**: ručně vybereš app-only `.bin` soubor.

Automatické stažení používá plain HTTP URL podle board profilu s verzí firmware přímo v názvu
souboru, například `http://esp32mic.msmeteo.cz/firmware-app-c3-1.10.0.bin`. Server musí tyto soubory
vydat přes obyčejné HTTP bez přesměrování na HTTPS. HTTPS/TLS se do těsných výchozích XIAO
ESP32-C3/C6 partition nevejde. `firmware-app.bin` zůstává C6 kompatibilní alias pro starší firmware.

Na OTA stránku nenahrávej `firmware-<board>.bin` ani `firmware.bin`. To jsou USB merged image. Pro
OTA patří `firmware-app-<board>.bin`; `firmware-app.bin` je kompatibilní C6 alias.

### Jak připravit firmware-<board>.bin
Vygeneruj sloučený image, např.:
```bash
esptool.py --chip esp32c6 merge_bin \
  -o firmware-c6.bin \
  0x0 bootloader.bin \
  0x8000 partitions.bin \
  0x10000 firmware-app-c6.bin
```
Nebo použij výstup z `idf.py build` / `arduino-esp32` pokud produkuje merged bin přímo.

### Nasazení na web

1. Ulož `index.html`, `manifest.json`, všechny `bootloader*.bin`, `partitions*.bin`,
   `boot_app0*.bin`, `firmware*.bin`, `firmware-app*.bin` a `ota-version.txt` do
   kořene statického HTTPS hostingu.
2. Ujisti se, že MIME typy pro `.json` a `.bin` jsou správně (`application/json`, `application/octet-stream`).
3. Otevři stránku v Chrome/Edge (desktop), povol přístup k sériovému portu, klikni „Flash“.

### GitHub release
Verze se bere z `web-flasher/manifest.json`; do release patří flasher/OTA artefakty z této složky.

### Poznámky
- WebSerial funguje pouze na desktop Chromu/Edge (ne Safari, ne Firefox).
- Stránka musí běžet přes HTTPS (nebo `http://localhost` při lokálním testu).
