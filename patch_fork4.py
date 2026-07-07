#!/usr/bin/env python3
"""Round 4: promote DEBUG_SAMPLES and FRAMES_PER_PACKET to Web UI settings (NVS-persisted).
Run from the repo root AFTER patch_fork.py, patch_fork2.py, patch_fork3.py.
"""
import gzip, os, sys

INO = os.path.join("esp32-birdnet-mic", "esp32-birdnet-mic.ino")
CPP = os.path.join("esp32-birdnet-mic", "WebUI.cpp")
HTML = os.path.join("esp32-birdnet-mic", "webui", "index.html")
GZH = os.path.join("esp32-birdnet-mic", "WebUI_gz.h")

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

s = load(INO)

s = rep(s, """// -- Packetization / diagnostics (WLS options)
#define DEBUG_SAMPLES        0   // 1 = log raw I2S words + shifted samples every 5 s (diagnose shift/format/wiring)
#define FRAMES_PER_PACKET    0   // 0 = one RTP packet per DMA chunk; >0 = fixed frames per RTP packet (e.g. 240 = 5 ms @ 48 kHz)
#if FRAMES_PER_PACKET > 0
#define I2S_INTS_PER_PACKET  (FRAMES_PER_PACKET * 2)                 // 32-bit stereo words per packet window
#define PAYLOAD_BYTES        (FRAMES_PER_PACKET * sizeof(int16_t))   // mono 16-bit RTP payload bytes per packet
#endif""",
"""// -- Packetization / diagnostics (WLS options, runtime-configurable via Web UI, NVS-persisted)
bool debugSamples = false;        // log raw I2S words + shifted samples every 5 s
uint16_t framesPerPacket = 0;     // 0 = one RTP packet per DMA chunk; >0 = fixed frames per RTP packet (e.g. 240 = 5 ms @ 48 kHz)""",
"runtime vars")

s = rep(s, """#if DEBUG_SAMPLES
        static uint32_t lastSampleDebug = 0;
        if (millis() - lastSampleDebug > 5000) {""",
"""        if (debugSamples) {
        static uint32_t lastSampleDebug = 0;
        if (millis() - lastSampleDebug > 5000) {""", "debug open")

s = rep(s, """                          i2sShiftBits, currentGainFactor, peakAbs);
        }
#endif""",
"""                          i2sShiftBits, currentGainFactor, peakAbs);
        }
        }""", "debug close")

s = rep(s, """            bool delivered = false;
#if FRAMES_PER_PACKET > 0
            for (int off = 0; off < samplesRead; off += FRAMES_PER_PACKET) {
                int n = samplesRead - off;
                if (n > FRAMES_PER_PACKET) n = FRAMES_PER_PACKET;
                for (uint8_t i = 0; i < MAX_CLIENTS; i++) {
                    if (!clients[i].streaming) continue;
                    if (clients[i].profileIndex != pi) continue;
                    sendRTPPacket(clients[i], &i2s_16bit_network_buffer[pi][off], n);
                    if (clients[i].streaming) delivered = true;
                }
                if (delivered) {
                    streamStats[pi].packetsSent++;
                    audioPacketsSent++;
                }
            }
#else
            for (uint8_t i = 0; i < MAX_CLIENTS; i++) {
                if (!clients[i].streaming) continue;
                if (clients[i].profileIndex != pi) continue;
                sendRTPPacket(clients[i], i2s_16bit_network_buffer[pi], samplesRead);
                if (clients[i].streaming) delivered = true;
            }
            if (delivered) {
                streamStats[pi].packetsSent++;
                audioPacketsSent++;
            }
#endif""",
"""            int step = (framesPerPacket > 0 && (int)framesPerPacket < samplesRead) ? (int)framesPerPacket : samplesRead;
            for (int off = 0; off < samplesRead; off += step) {
                int n = samplesRead - off;
                if (n > step) n = step;
                bool delivered = false;
                for (uint8_t i = 0; i < MAX_CLIENTS; i++) {
                    if (!clients[i].streaming) continue;
                    if (clients[i].profileIndex != pi) continue;
                    sendRTPPacket(clients[i], &i2s_16bit_network_buffer[pi][off], n);
                    if (clients[i].streaming) delivered = true;
                }
                if (delivered) {
                    streamStats[pi].packetsSent++;
                    audioPacketsSent++;
                }
            }""", "runtime slicing")

s = rep(s, '    cpuFrequencyMhz = audioPrefs.getUChar("cpuFreq", 160);',
'''    cpuFrequencyMhz = audioPrefs.getUChar("cpuFreq", 160);
    debugSamples = audioPrefs.getBool("dbgSamp", false);
    framesPerPacket = audioPrefs.getUShort("fpp", 0);''', "nvs load")

s = rep(s, '    audioPrefs.putUChar("cpuFreq", cpuFrequencyMhz);',
'''    audioPrefs.putUChar("cpuFreq", cpuFrequencyMhz);
    audioPrefs.putBool("dbgSamp", debugSamples);
    audioPrefs.putUShort("fpp", framesPerPacket);''', "nvs save")

s = rep(s, "    cpuFrequencyMhz = 160;",
"""    cpuFrequencyMhz = 160;
    debugSamples = false;
    framesPerPacket = 0;""", "defaults")

save(INO, s)

s = load(CPP)

s = rep(s, "extern uint8_t cpuFrequencyMhz;",
"""extern uint8_t cpuFrequencyMhz;
extern bool debugSamples;
extern uint16_t framesPerPacket;""", "externs")

s = rep(s, '''    json += "\\"hp_cutoff_hz\\":" + String((uint32_t)highpassCutoffHz) + ",";''',
'''    json += "\\"hp_cutoff_hz\\":" + String((uint32_t)highpassCutoffHz) + ",";
    json += "\\"debug_samples\\":" + String(debugSamples?"true":"false") + ",";
    json += "\\"frames_per_packet\\":" + String((uint32_t)framesPerPacket) + ",";''', "json fields")

s = rep(s, '''    else if (key == "hp_cutoff") {
        handled = true;
        uint32_t v;
        if (argToUInt(v) && v >= 10 && v <= 10000) { extern uint16_t highpassCutoffHz; highpassCutoffHz = (uint16_t)v; extern void updateHighpassCoeffs(); updateHighpassCoeffs(); saveAudioSettings(); applied = true; }
    }''',
'''    else if (key == "hp_cutoff") {
        handled = true;
        uint32_t v;
        if (argToUInt(v) && v >= 10 && v <= 10000) { extern uint16_t highpassCutoffHz; highpassCutoffHz = (uint16_t)v; extern void updateHighpassCoeffs(); updateHighpassCoeffs(); saveAudioSettings(); applied = true; }
    }
    else if (key == "debug_samples") {
        handled = true;
        String v = web.arg("value");
        if (v == "on" || v == "off") { debugSamples = (v == "on"); saveAudioSettings(); applied = true; }
    }
    else if (key == "frames_per_packet") {
        handled = true;
        uint32_t v;
        if (argToUInt(v) && (v == 0 || (v >= 32 && v <= 2048))) { framesPerPacket = (uint16_t)v; saveAudioSettings(); applied = true; }
    }''', "api handlers")

save(CPP, s)

s = load(HTML)

s = rep(s, """<tr id='row_shift_hint' style='display:none'>
<td colspan='2'>
<div class='hint' id='txt_shift_hint'>
</div>
</td>
</tr>""",
"""<tr id='row_shift_hint' style='display:none'>
<td colspan='2'>
<div class='hint' id='txt_shift_hint'>
</div>
</td>
</tr>
<tr>
<td class='k'>
<span id='t_debug_samples'>Debug Samples (serial)</span>
</td>
<td class='v'>
<div class='field'>
<select id='sel_debug_samples'>
<option value='off'>off</option>
<option value='on'>on</option>
</select>
<button id='btn_debug_samples_set' onclick="setv('debug_samples',sel_debug_samples.value)">Set</button>
</div>
</td>
</tr>
<tr>
<td class='k'>
<span id='t_fpp'>Frames / RTP Packet</span>
</td>
<td class='v'>
<div class='field'>
<input id='in_fpp' type='number' step='1' min='0' max='2048'>
<span class='unit'>0=chunk</span>
<button id='btn_fpp_set' onclick="setv('frames_per_packet',in_fpp.value)">Set</button>
</div>
</td>
</tr>""", "html rows")

s = rep(s, " $('lat').textContent=j.latency_ms.toFixed(1)+' ms';",
""" const dsv=$('sel_debug_samples'); if(dsv){ const editing=(edits['debug_samples']&&now<edits['debug_samples']); if(!(locks['debug_samples']&&now<locks['debug_samples']) && !editing) dsv.value=j.debug_samples?'on':'off'; toggleDirty(dsv,'debug_samples'); } const fpp=$('in_fpp'); if(fpp){ const editing=(edits['frames_per_packet']&&now<edits['frames_per_packet']); if(!(locks['frames_per_packet']&&now<locks['frames_per_packet']) && !editing) fpp.value=(typeof j.frames_per_packet==='number')?j.frames_per_packet:0; toggleDirty(fpp,'frames_per_packet'); } $('lat').textContent=j.latency_ms.toFixed(1)+' ms';""", "js populate")

s = rep(s, "bindSaver($('in_hp_cutoff'),'hp_cutoff');",
"bindSaver($('in_hp_cutoff'),'hp_cutoff'); bindSaver($('in_fpp'),'frames_per_packet');", "js bindsaver")

s = rep(s, "trackEdit($('in_hp_cutoff'),'hp_cutoff');trackEdit",
"trackEdit($('in_hp_cutoff'),'hp_cutoff'); trackEdit($('sel_debug_samples'),'debug_samples'); trackEdit($('in_fpp'),'frames_per_packet');trackEdit", "js trackedit")

save(HTML, s)

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
print("\nDONE. Commit and recompile.")