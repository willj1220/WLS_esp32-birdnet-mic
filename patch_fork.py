#!/usr/bin/env python3
"""Apply stereo-split + 6-client changes to WLS_esp32-birdnet-mic fork.
Run from the repo root:  python patch_fork.py
Requires the fork to already contain the board-profile/MCLK version.
"""
import gzip, os, sys

INO = os.path.join("esp32-birdnet-mic", "esp32-birdnet-mic.ino")
CPP = os.path.join("esp32-birdnet-mic", "WebUI.cpp")
HTML = os.path.join("esp32-birdnet-mic", "webui", "index.html")
GZH = os.path.join("esp32-birdnet-mic", "WebUI_gz.h")

def load(p):
    with open(p, "r", encoding="utf-8", newline="") as f:
        s = f.read()
    return s.replace("\r\n", "\n")

def save(p, s):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)

def rep(s, old, new, label):
    n = s.count(old)
    if n != 1:
        sys.exit(f"FAILED [{label}]: expected 1 match, found {n}. Wrong file state?")
    print(f"  ok: {label}")
    return s.replace(old, new)

# ---------------- esp32-birdnet-mic.ino ----------------
s = load(INO)

s = rep(s, """int32_t* i2s_32bit_buffer = nullptr;
int16_t* i2s_16bit_buffer = nullptr;
int16_t* i2s_16bit_network_buffer = nullptr;
RingbufHandle_t audioRingBuffer = nullptr;""",
"""// Stereo capture: each WM8782 input channel feeds its own RTSP stream.
// If your mics come out on the wrong streams, swap these two defines.
#define CH_AUDIO1 0   // DMA slot index feeding /audio1
#define CH_AUDIO2 1   // DMA slot index feeding /audio2

int32_t* i2s_32bit_buffer = nullptr;                       // interleaved stereo frames
int16_t* i2s_16bit_buffer[2] = {nullptr, nullptr};         // per-channel mono
int16_t* i2s_16bit_network_buffer[2] = {nullptr, nullptr}; // per-channel network order
RingbufHandle_t audioRingBuffer[2] = {nullptr, nullptr};""", "globals")

s = rep(s, "static const uint8_t MAX_CLIENTS = 3;",
"static const uint8_t MAX_CLIENTS = 6;  // hard cap; ~1.2KB static per session, ~770 kbps Wi-Fi TX per TCP client",
"max clients")

s = rep(s, "Biquad hpf;", "Biquad hpf[2];  // independent filter state per channel", "hpf decl")

s = rep(s, """    if (!highpassEnabled) {
        hpf.reset();""",
"""    if (!highpassEnabled) {
        hpf[0].reset();
        hpf[1].reset();""", "hpf disable reset")

s = rep(s, """    hpf.b0 = b0 / a0;
    hpf.b1 = b1 / a0;
    hpf.b2 = b2 / a0;
    hpf.a1 = a1 / a0;
    hpf.a2 = a2 / a0;
    hpf.reset();""",
"""    for (uint8_t ch = 0; ch < 2; ch++) {
        hpf[ch].b0 = b0 / a0;
        hpf[ch].b1 = b1 / a0;
        hpf[ch].b2 = b2 / a0;
        hpf[ch].a1 = a1 / a0;
        hpf[ch].a2 = a2 / a0;
        hpf[ch].reset();
    }""", "hpf coeffs")

s = rep(s, """    if (i2s_32bit_buffer) { free(i2s_32bit_buffer); i2s_32bit_buffer = nullptr; }
    if (i2s_16bit_buffer) { free(i2s_16bit_buffer); i2s_16bit_buffer = nullptr; }
    if (i2s_16bit_network_buffer) { free(i2s_16bit_network_buffer); i2s_16bit_network_buffer = nullptr; }

    i2s_32bit_buffer = (int32_t*)malloc(currentBufferSize * sizeof(int32_t));
    i2s_16bit_buffer = (int16_t*)malloc(currentBufferSize * sizeof(int16_t));
    i2s_16bit_network_buffer = (int16_t*)malloc(currentBufferSize * sizeof(int16_t));
    if (!i2s_32bit_buffer || !i2s_16bit_buffer || !i2s_16bit_network_buffer) {
        simplePrintln("FATAL: Memory allocation failed after parameter change!");
        if (i2s_32bit_buffer) { free(i2s_32bit_buffer); i2s_32bit_buffer = nullptr; }
        if (i2s_16bit_buffer) { free(i2s_16bit_buffer); i2s_16bit_buffer = nullptr; }
        if (i2s_16bit_network_buffer) { free(i2s_16bit_network_buffer); i2s_16bit_network_buffer = nullptr; }
        return false;
    }""",
"""    if (i2s_32bit_buffer) { free(i2s_32bit_buffer); i2s_32bit_buffer = nullptr; }
    for (uint8_t ch = 0; ch < 2; ch++) {
        if (i2s_16bit_buffer[ch]) { free(i2s_16bit_buffer[ch]); i2s_16bit_buffer[ch] = nullptr; }
        if (i2s_16bit_network_buffer[ch]) { free(i2s_16bit_network_buffer[ch]); i2s_16bit_network_buffer[ch] = nullptr; }
    }

    // Stereo: 2 interleaved 32-bit words per frame, currentBufferSize frames per channel
    i2s_32bit_buffer = (int32_t*)malloc((size_t)currentBufferSize * 2 * sizeof(int32_t));
    bool allocOk = (i2s_32bit_buffer != nullptr);
    for (uint8_t ch = 0; ch < 2; ch++) {
        i2s_16bit_buffer[ch] = (int16_t*)malloc(currentBufferSize * sizeof(int16_t));
        i2s_16bit_network_buffer[ch] = (int16_t*)malloc(currentBufferSize * sizeof(int16_t));
        if (!i2s_16bit_buffer[ch] || !i2s_16bit_network_buffer[ch]) allocOk = false;
    }
    if (!allocOk) {
        simplePrintln("FATAL: Memory allocation failed after parameter change!");
        if (i2s_32bit_buffer) { free(i2s_32bit_buffer); i2s_32bit_buffer = nullptr; }
        for (uint8_t ch = 0; ch < 2; ch++) {
            if (i2s_16bit_buffer[ch]) { free(i2s_16bit_buffer[ch]); i2s_16bit_buffer[ch] = nullptr; }
            if (i2s_16bit_network_buffer[ch]) { free(i2s_16bit_network_buffer[ch]); i2s_16bit_network_buffer[ch] = nullptr; }
        }
        return false;
    }""", "restartI2S alloc")

s = rep(s, "    i2s_config.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;",
"    i2s_config.channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT;  // stereo: one mic per channel",
"channel format")

s = rep(s, """void flushAudioRingBuffer() {
    if (!audioRingBuffer) return;
    size_t itemSize = 0;
    void* item = nullptr;
    uint32_t flushed = 0;
    while ((item = xRingbufferReceive(audioRingBuffer, &itemSize, 0)) != nullptr) {
        vRingbufferReturnItem(audioRingBuffer, item);
        flushed++;
    }
    if (flushed > 0) {
        audioRingBufferFlushCount += flushed;
    }
}""",
"""void flushAudioRingBuffer() {
    size_t itemSize = 0;
    void* item = nullptr;
    uint32_t flushed = 0;
    for (uint8_t pi = 0; pi < 2; pi++) {
        if (!audioRingBuffer[pi]) continue;
        while ((item = xRingbufferReceive(audioRingBuffer[pi], &itemSize, 0)) != nullptr) {
            vRingbufferReturnItem(audioRingBuffer[pi], item);
            flushed++;
        }
    }
    if (flushed > 0) {
        audioRingBufferFlushCount += flushed;
    }
}""", "flush")

s = rep(s, """    while (!audioProducerStopRequested) {
        size_t bytesRead = 0;
        esp_err_t result = i2s_read(I2S_NUM_0, i2s_32bit_buffer,
                                    currentBufferSize * sizeof(int32_t),
                                    &bytesRead, pdMS_TO_TICKS(100));
        if (audioProducerStopRequested) break;

        if (result != ESP_OK || bytesRead == 0) {
            audioI2SErrorCount++;
            vTaskDelay(pdMS_TO_TICKS(1));
            continue;
        }

        int samplesRead = bytesRead / sizeof(int32_t);
        if (samplesRead <= 0) continue;

        // If HPF params changed dynamically, recompute in the producer context.
        if (highpassEnabled && (hpfConfigSampleRate != currentSampleRate || hpfConfigCutoff != highpassCutoffHz)) {
            updateHighpassCoeffs();
        }

        bool clipped = false;
        float peakAbs = 0.0f;
        for (int i = 0; i < samplesRead; i++) {
            float sample = (float)(i2s_32bit_buffer[i] >> i2sShiftBits);
            if (highpassEnabled) sample = hpf.process(sample);
            float amplified = sample * currentGainFactor;
            float aabs = fabsf(amplified);
            if (aabs > peakAbs) peakAbs = aabs;
            if (aabs > 32767.0f) clipped = true;
            if (amplified > 32767.0f) amplified = 32767.0f;
            if (amplified < -32768.0f) amplified = -32768.0f;
            i2s_16bit_buffer[i] = (int16_t)amplified;
        }""",
"""    while (!audioProducerStopRequested) {
        size_t bytesRead = 0;
        esp_err_t result = i2s_read(I2S_NUM_0, i2s_32bit_buffer,
                                    (size_t)currentBufferSize * 2 * sizeof(int32_t),
                                    &bytesRead, pdMS_TO_TICKS(100));
        if (audioProducerStopRequested) break;

        if (result != ESP_OK || bytesRead == 0) {
            audioI2SErrorCount++;
            vTaskDelay(pdMS_TO_TICKS(1));
            continue;
        }

        int wordsRead = bytesRead / sizeof(int32_t);
        int framesRead = wordsRead / 2;  // stereo frames
        if (framesRead <= 0) continue;

        // If HPF params changed dynamically, recompute in the producer context.
        if (highpassEnabled && (hpfConfigSampleRate != currentSampleRate || hpfConfigCutoff != highpassCutoffHz)) {
            updateHighpassCoeffs();
        }

        bool clipped = false;
        float peakAbs = 0.0f;
        for (int f = 0; f < framesRead; f++) {
            for (uint8_t ch = 0; ch < 2; ch++) {
                float sample = (float)(i2s_32bit_buffer[f * 2 + ch] >> i2sShiftBits);
                if (highpassEnabled) sample = hpf[ch].process(sample);
                float amplified = sample * currentGainFactor;
                float aabs = fabsf(amplified);
                if (aabs > peakAbs) peakAbs = aabs;
                if (aabs > 32767.0f) clipped = true;
                if (amplified > 32767.0f) amplified = 32767.0f;
                if (amplified < -32768.0f) amplified = -32768.0f;
                i2s_16bit_buffer[ch][f] = (int16_t)amplified;
            }
        }""", "producer loop")

s = rep(s, """        if (!audioRingBuffer || !hasActiveRtspStream()) {
            continue;
        }

        size_t payloadBytes = (size_t)samplesRead * sizeof(int16_t);
        if (xRingbufferSend(audioRingBuffer, i2s_16bit_buffer, payloadBytes, 0) == pdTRUE) {
            audioRingBufferChunkCount++;
        } else {
            audioRingBufferDropCount++;
        }
    }""",
"""        if ((!audioRingBuffer[0] && !audioRingBuffer[1]) || !hasActiveRtspStream()) {
            continue;
        }

        size_t payloadBytes = (size_t)framesRead * sizeof(int16_t);
        const uint8_t chForProfile[2] = {CH_AUDIO1, CH_AUDIO2};
        for (uint8_t pi = 0; pi < 2; pi++) {
            if (!audioRingBuffer[pi]) continue;
            if (xRingbufferSend(audioRingBuffer[pi], i2s_16bit_buffer[chForProfile[pi]], payloadBytes, 0) == pdTRUE) {
                audioRingBufferChunkCount++;
            } else {
                audioRingBufferDropCount++;
            }
        }
    }""", "producer send")

s = rep(s, """    if (audioRingBuffer) {
        vRingbufferDelete(audioRingBuffer);
        audioRingBuffer = nullptr;
    }
    audioRingBufferCapacityBytes = 0;
    audioProducerStopRequested = false;
}""",
"""    for (uint8_t pi = 0; pi < 2; pi++) {
        if (audioRingBuffer[pi]) {
            vRingbufferDelete(audioRingBuffer[pi]);
            audioRingBuffer[pi] = nullptr;
        }
    }
    audioRingBufferCapacityBytes = 0;
    audioProducerStopRequested = false;
}""", "stop producer")

s = rep(s, """    audioRingBufferCapacityBytes = computeAudioRingBufferCapacity();
    audioRingBuffer = xRingbufferCreate(audioRingBufferCapacityBytes, RINGBUF_TYPE_BYTEBUF);
    if (!audioRingBuffer) {
        simplePrintln("Audio RB alloc failed");
        audioRingBufferCapacityBytes = 0;
        return false;
    }""",
"""    audioRingBufferCapacityBytes = computeAudioRingBufferCapacity();
    for (uint8_t pi = 0; pi < 2; pi++) {
        audioRingBuffer[pi] = xRingbufferCreate(audioRingBufferCapacityBytes, RINGBUF_TYPE_BYTEBUF);
        if (!audioRingBuffer[pi]) {
            simplePrintln("Audio RB alloc failed");
            if (pi == 1 && audioRingBuffer[0]) {
                vRingbufferDelete(audioRingBuffer[0]);
                audioRingBuffer[0] = nullptr;
            }
            audioRingBufferCapacityBytes = 0;
            return false;
        }
    }""", "start producer create")

s = rep(s, """    if (rc != pdPASS) {
        simplePrintln("Audio producer failed");
        vRingbufferDelete(audioRingBuffer);
        audioRingBuffer = nullptr;
        audioRingBufferCapacityBytes = 0;
        return false;
    }""",
"""    if (rc != pdPASS) {
        simplePrintln("Audio producer failed");
        for (uint8_t pi = 0; pi < 2; pi++) {
            if (audioRingBuffer[pi]) {
                vRingbufferDelete(audioRingBuffer[pi]);
                audioRingBuffer[pi] = nullptr;
            }
        }
        audioRingBufferCapacityBytes = 0;
        return false;
    }""", "start producer fail")

s = rep(s, """void streamAudio() {
    bool anyStreaming = false;
    for (uint8_t i = 0; i < MAX_CLIENTS; i++) {
        if (clients[i].streaming) { anyStreaming = true; break; }
    }
    if (!anyStreaming) return;
    if (!audioRingBuffer) return;

    uint8_t chunksProcessed = 0;
    while (chunksProcessed < 4) {
        size_t itemSize = 0;
        int16_t* audioChunk = (int16_t*)xRingbufferReceive(audioRingBuffer, &itemSize, 0);
        if (!audioChunk) break;

        int samplesRead = itemSize / sizeof(int16_t);
        if (samplesRead > currentBufferSize) samplesRead = currentBufferSize;

        // Prepare one network-order copy and reuse for all active client sessions.
        for (int i = 0; i < samplesRead; ++i) {
            uint16_t s = (uint16_t)audioChunk[i];
            s = (uint16_t)((s << 8) | (s >> 8));
            i2s_16bit_network_buffer[i] = (int16_t)s;
        }
        bool deliveredProfile[2] = {false, false};
        for (uint8_t i = 0; i < MAX_CLIENTS; i++) {
            if (!clients[i].streaming) continue;
            uint8_t pi = clients[i].profileIndex;
            sendRTPPacket(clients[i], i2s_16bit_network_buffer, samplesRead);
            if (clients[i].streaming) {
                deliveredProfile[pi] = true;
            }
        }
        bool deliveredAny = false;
        for (uint8_t pi = 0; pi < 2; pi++) {
            if (!deliveredProfile[pi]) continue;
            streamStats[pi].packetsSent++;
            deliveredAny = true;
        }
        if (deliveredAny) {
            audioPacketsSent++;
        }
        vRingbufferReturnItem(audioRingBuffer, (void*)audioChunk);
        chunksProcessed++;
    }
}""",
"""void streamAudio() {
    bool anyStreaming = false;
    for (uint8_t i = 0; i < MAX_CLIENTS; i++) {
        if (clients[i].streaming) { anyStreaming = true; break; }
    }
    if (!anyStreaming) return;

    // Drain both rings in lockstep so an unused stream never backs up its buffer.
    for (uint8_t pi = 0; pi < 2; pi++) {
        if (!audioRingBuffer[pi]) continue;

        uint8_t chunksProcessed = 0;
        while (chunksProcessed < 4) {
            size_t itemSize = 0;
            int16_t* audioChunk = (int16_t*)xRingbufferReceive(audioRingBuffer[pi], &itemSize, 0);
            if (!audioChunk) break;

            int samplesRead = itemSize / sizeof(int16_t);
            if (samplesRead > currentBufferSize) samplesRead = currentBufferSize;

            // Network-order copy, reused for all clients on this stream.
            for (int i = 0; i < samplesRead; ++i) {
                uint16_t s = (uint16_t)audioChunk[i];
                s = (uint16_t)((s << 8) | (s >> 8));
                i2s_16bit_network_buffer[pi][i] = (int16_t)s;
            }
            bool delivered = false;
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
            vRingbufferReturnItem(audioRingBuffer[pi], (void*)audioChunk);
            chunksProcessed++;
        }
    }
}""", "streamAudio")

s = rep(s, """    // Allocate buffers with current size
    i2s_32bit_buffer = (int32_t*)malloc(currentBufferSize * sizeof(int32_t));
    i2s_16bit_buffer = (int16_t*)malloc(currentBufferSize * sizeof(int16_t));
    i2s_16bit_network_buffer = (int16_t*)malloc(currentBufferSize * sizeof(int16_t));
    if (!i2s_32bit_buffer || !i2s_16bit_buffer || !i2s_16bit_network_buffer) {
        simplePrintln("FATAL: Memory allocation failed!");
        ESP.restart();
    }""",
"""    // Allocate buffers with current size (stereo capture, per-channel outputs)
    i2s_32bit_buffer = (int32_t*)malloc((size_t)currentBufferSize * 2 * sizeof(int32_t));
    bool bootAllocOk = (i2s_32bit_buffer != nullptr);
    for (uint8_t ch = 0; ch < 2; ch++) {
        i2s_16bit_buffer[ch] = (int16_t*)malloc(currentBufferSize * sizeof(int16_t));
        i2s_16bit_network_buffer[ch] = (int16_t*)malloc(currentBufferSize * sizeof(int16_t));
        if (!i2s_16bit_buffer[ch] || !i2s_16bit_network_buffer[ch]) bootAllocOk = false;
    }
    if (!bootAllocOk) {
        simplePrintln("FATAL: Memory allocation failed!");
        ESP.restart();
    }""", "setup alloc")

save(INO, s)

# ---------------- WebUI.cpp ----------------
s = load(CPP)
s = rep(s,
'        if (argToUInt(v) && v >= 1 && v <= 3) { maxActiveClients = (uint8_t)v; saveAudioSettings(); applied = true; }',
'        if (argToUInt(v) && v >= 1 && v <= 6) { maxActiveClients = (uint8_t)v; saveAudioSettings(); applied = true; }  // keep in sync with MAX_CLIENTS',
"api max_clients")
save(CPP, s)

# ---------------- webui/index.html ----------------
s = load(HTML)
s = rep(s, """<select id='sel_max_clients'>
<option>1</option>
<option selected>2</option>
<option>3</option>""",
"""<select id='sel_max_clients'>
<option>1</option>
<option selected>2</option>
<option>3</option>
<option>4</option>
<option>5</option>
<option>6</option>""", "dropdown")
save(HTML, s)

# ---------------- Regenerate WebUI_gz.h ----------------
with open(HTML, "rb") as f:
    raw = f.read().replace(b"\r\n", b"\n")
gz = gzip.compress(raw, 9, mtime=0)
lines = []
for i in range(0, len(gz), 12):
    chunk = gz[i:i+12]
    lines.append("  " + ", ".join(f"0x{b:02x}" for b in chunk) + ("," if i + 12 < len(gz) else ""))
out = ["#pragma once", "#include <Arduino.h>", "#include <pgmspace.h>", "",
       "static const uint8_t WEBUI_INDEX_GZ[] PROGMEM = {"] + lines + \
      ["};", "", f"static const size_t WEBUI_INDEX_GZ_LEN = {len(gz)};"]
save(GZH, "\n".join(out) + "\n")
print(f"  ok: WebUI_gz.h regenerated ({len(gz)} bytes gzipped)")

print("\nALL CHANGES APPLIED. Now: git add -A && git commit && recompile.")