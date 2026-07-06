#!/usr/bin/env python3
"""Round 2: 240 MHz CPU option + full-16MB partition table.
Run from the repo root AFTER patch_fork.py:  python patch_fork2.py
"""
import gzip, os, sys

CPP = os.path.join("esp32-birdnet-mic", "WebUI.cpp")
HTML = os.path.join("esp32-birdnet-mic", "webui", "index.html")
GZH = os.path.join("esp32-birdnet-mic", "WebUI_gz.h")
PARTS = os.path.join("esp32-birdnet-mic", "partitions.csv")

def load(p):
    with open(p, "r", encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n")

def save(p, s):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)

def rep(s, old, new, label):
    n = s.count(old)
    if n != 1:
        sys.exit(f"FAILED [{label}]: expected 1 match, found {n}.")
    print(f"  ok: {label}")
    return s.replace(old, new)

s = load(CPP)
s = rep(s,
 'if (argToUInt(v) && v >= 40 && v <= 160) { cpuFrequencyMhz = (uint8_t)v; setCpuFrequencyMhz(cpuFrequencyMhz); saveAudioSettings(); applied = true; }',
 'if (argToUInt(v) && v >= 40 && v <= 240) { cpuFrequencyMhz = (uint8_t)v; setCpuFrequencyMhz(cpuFrequencyMhz); saveAudioSettings(); applied = true; }  // 240 = S3 max',
 "cpu validation")
save(CPP, s)

s = load(HTML)
s = rep(s, """<select id='sel_cpu'>
<option>80</option>
<option>120</option>
<option selected>160</option>
</select>""",
"""<select id='sel_cpu'>
<option>80</option>
<option>120</option>
<option selected>160</option>
<option>240</option>
</select>""", "cpu dropdown")
save(HTML, s)

save(PARTS, """# ESP32-S3 N16R8: full 16MB, dual OTA app slots
# Name,   Type, SubType, Offset,   Size
nvs,      data, nvs,     0x9000,   0x5000
otadata,  data, ota,     0xe000,   0x2000
app0,     app,  ota_0,   0x10000,  0x640000
app1,     app,  ota_1,   0x650000, 0x640000
spiffs,   data, spiffs,  0xc90000, 0x360000
coredump, data, coredump,0xff0000, 0x10000
""")
print("  ok: partitions.csv created")

raw = open(HTML, "rb").read().replace(b"\r\n", b"\n")
gz = gzip.compress(raw, 9, mtime=0)
lines = []
for i in range(0, len(gz), 12):
    c = gz[i:i+12]
    lines.append("  " + ", ".join(f"0x{b:02x}" for b in c) + ("," if i + 12 < len(gz) else ""))
out = ["#pragma once", "#include <Arduino.h>", "#include <pgmspace.h>", "",
       "static const uint8_t WEBUI_INDEX_GZ[] PROGMEM = {"] + lines + \
      ["};", "", f"static const size_t WEBUI_INDEX_GZ_LEN = {len(gz)};"]
save(GZH, "\n".join(out) + "\n")
print(f"  ok: WebUI_gz.h regenerated ({len(gz)} bytes gzipped)")
print("\nDONE. Commit, then compile with the 16MB-aware command below.")