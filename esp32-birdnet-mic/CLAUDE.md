# WLS_esp32-birdnet-mic — Project Context

Fork of Sukecz/esp32-birdnet-mic, heavily modified for custom hardware.
RTSP stereo microphone streamer feeding BirdNET-Go for 24/7 bird audio monitoring.

## Hardware
- Board: generic ESP32-S3-WROOM-1 devkit, N16R8 (16MB flash, 8MB OPI PSRAM)
  - NOT a XIAO. No GPIO 3 broken out. GPIO 35-37 unavailable (octal PSRAM).
- ADC: WM8782-class I2S ADC board ("I2S ADC Audio Card Module" from Amazon)
  - Jumpered: SLAVE mode, I2S format, 24-bit, 48 kHz
  - MCLK comes FROM the ESP32 (12.288 MHz = 256*fs), NOT the board's onboard
    24.576 MHz crystal. The "TO I2S 24.578M" jumper selects this — do not change.
  - 16-bit jumper setting = right-justified mode = sign-bit corruption. Never use.
- Two mics: one per WM8782 channel (TRS tip=L, ring=R), each behind a TS472 preamp.
  Line-level input, no mic bias on the 3.5mm jack.

## Pin map (compiled into firmware, defines near top of .ino)
| Signal   | GPIO |
|----------|------|
| MCLK out | 4    |
| BCLK out | 21   |
| WS out   | 1    |
| DOUT in  | 2    |
CH_AUDIO1/CH_AUDIO2 defines map DMA slots to /audio1 & /audio2. If mics land on
wrong streams, swap those two defines (legacy I2S driver L/R slot order varies).

## Build & flash (Windows, arduino-cli)
compile: arduino-cli compile --clean --fqbn "esp32:esp32:esp32s3:FlashSize=16M,PSRAM=opi,PartitionScheme=custom,CDCOnBoot=cdc" esp32-birdnet-mic
upload:  arduino-cli upload -p COM5 --fqbn (same FQBN) esp32-birdnet-mic
monitor: arduino-cli monitor -p COM5 -c baudrate=115200
- PartitionScheme=custom uses esp32-birdnet-mic/partitions.csv (16MB, dual 6.25MB
  OTA slots). Reported max 16777216 is whole flash; keep app under 0x640000.
- Libraries: WiFiManager, PubSubClient. Core: esp32:esp32 (latest).

## CRITICAL build rule
After ANY edit to esp32-birdnet-mic/webui/index.html, regenerate
esp32-birdnet-mic/WebUI_gz.h (gzip -9 of index.html as a PROGMEM byte array,
WEBUI_INDEX_GZ / WEBUI_INDEX_GZ_LEN). The served UI is the .h, not the .html.

## Changes vs upstream (all committed)
1. Single board profile "esp32s3-devkit-wm8782" (XIAO profiles + C6 RF-switch code removed)
2. MCLK output added (mclk_multiple=256, mck_io_num) — ESP32 is I2S master incl. MCLK
3. Stereo capture (I2S_CHANNEL_FMT_RIGHT_LEFT): deinterleaved per-channel buffers,
   dual ring buffers, per-channel HPF state; /audio1 and /audio2 are independent mics
4. MAX_CLIENTS raised 3 -> 6 (UI dropdown + API validation updated to match)
5. getDefaultOtaUrl() returns "" — never auto-pull upstream XIAO binaries; manual OTA only
6. CPU 240 MHz option added (UI + API, S3 max)
7. Runtime settings (NVS + Web UI Advanced): debugSamples (dbgSamp),
   framesPerPacket (fpp; 0 = one RTP packet per DMA chunk)
8. Debug sample logging: producer task snapshots into volatile globals,
   loop() formats + simplePrintln (webui_pushLog is NOT thread-safe — never
   call it from the audio producer task)

## Conventions & gotchas
- Web UI settings pattern: NVS key in loadAudioSettings/saveAudioSettings +
  defaults block, JSON field in audio_status, /api/set handler in WebUI.cpp,
  HTML row + loadAudio populate + trackEdit/bindSaver in index.html JS
- sendRTPPacket(session, buf, nSamples) advances RTP timestamp per call —
  packet splitting is timestamp-safe
- Transport is negotiated per client from the SETUP Transport header (TCP
  interleaved or UDP); the "Target" dropdown is only the fallback when the
  client doesn't specify (BirdNET-Go=TCP, BirdNET-Pi=UDP)
- Acceptance test after audio-path changes (run on BirdNET-Go host):
  ffmpeg -rtsp_transport tcp -i rtsp://192.168.2.213:8554/audio1 -t 5 test.wav
  ffmpeg -i test.wav -af astats -f null - 2>&1 | grep -E "DC offset|Peak|RMS|Flat"
  Unplugged: peak < -40 dBFS, RMS < -70. Signal: peaks -12 to -6 dBFS.
- Consumer: BirdNET-Go in LXC at 192.168.1.61; device at 192.168.2.213
- NVS survives reflashes (settings + WiFi persist); "Defaults" in UI resets audio settings only