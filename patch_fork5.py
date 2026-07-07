#!/usr/bin/env python3
"""Round 5: Debug Samples output -> Web UI Logs card (race-free via loop()).
Run from the repo root AFTER patch_fork4.py:  python patch_fork5.py
"""
import os, sys

INO = os.path.join("esp32-birdnet-mic", "esp32-birdnet-mic.ino")

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

s = rep(s, """bool debugSamples = false;        // log raw I2S words + shifted samples every 5 s
uint16_t framesPerPacket = 0;     // 0 = one RTP packet per DMA chunk; >0 = fixed frames per RTP packet (e.g. 240 = 5 ms @ 48 kHz)""",
"""bool debugSamples = false;        // log raw I2S words + shifted samples every 5 s (Web UI Logs + serial)
uint16_t framesPerPacket = 0;     // 0 = one RTP packet per DMA chunk; >0 = fixed frames per RTP packet (e.g. 240 = 5 ms @ 48 kHz)

// Snapshot written by the audio producer task, formatted+logged from loop() (webui_pushLog is not thread-safe)
volatile bool debugSampleReady = false;
volatile uint32_t dbgRaw[4] = {0, 0, 0, 0};
volatile int32_t dbgShiftedL = 0, dbgShiftedR = 0;
volatile int16_t dbgOutL = 0, dbgOutR = 0;
volatile float dbgPeak = 0.0f;""", "snapshot globals")

s = rep(s, """        if (debugSamples) {
        static uint32_t lastSampleDebug = 0;
        if (millis() - lastSampleDebug > 5000) {
            lastSampleDebug = millis();
            Serial.printf("[DBG] raw32 L/R/L/R: %08lx %08lx %08lx %08lx | shifted L=%ld R=%ld | out16 L=%d R=%d | shift=%u gain=%.2f peak=%.0f\\n",
                          (unsigned long)i2s_32bit_buffer[0], (unsigned long)i2s_32bit_buffer[1],
                          (unsigned long)i2s_32bit_buffer[2], (unsigned long)i2s_32bit_buffer[3],
                          (long)(i2s_32bit_buffer[0] >> i2sShiftBits), (long)(i2s_32bit_buffer[1] >> i2sShiftBits),
                          (int)i2s_16bit_buffer[0][0], (int)i2s_16bit_buffer[1][0],
                          i2sShiftBits, currentGainFactor, peakAbs);
        }
        }""",
"""        if (debugSamples && !debugSampleReady) {
            static uint32_t lastSampleDebug = 0;
            if (millis() - lastSampleDebug > 5000) {
                lastSampleDebug = millis();
                for (int d = 0; d < 4; d++) dbgRaw[d] = (uint32_t)i2s_32bit_buffer[d];
                dbgShiftedL = (int32_t)(i2s_32bit_buffer[0] >> i2sShiftBits);
                dbgShiftedR = (int32_t)(i2s_32bit_buffer[1] >> i2sShiftBits);
                dbgOutL = i2s_16bit_buffer[0][0];
                dbgOutR = i2s_16bit_buffer[1][0];
                dbgPeak = peakAbs;
                debugSampleReady = true;  // consumed and logged from loop()
            }
        }""", "producer snapshot")

s = rep(s, """    if (millis() - lastTempCheck > 60000) { // 1 min
        checkTemperature();
        lastTempCheck = millis();
    }""",
"""    if (millis() - lastTempCheck > 60000) { // 1 min
        checkTemperature();
        lastTempCheck = millis();
    }

    if (debugSampleReady) {
        char dbgLine[176];
        snprintf(dbgLine, sizeof(dbgLine),
                 "[DBG] raw32 L/R/L/R: %08lx %08lx %08lx %08lx | shifted L=%ld R=%ld | out16 L=%d R=%d | shift=%u gain=%.2f peak=%.0f",
                 (unsigned long)dbgRaw[0], (unsigned long)dbgRaw[1],
                 (unsigned long)dbgRaw[2], (unsigned long)dbgRaw[3],
                 (long)dbgShiftedL, (long)dbgShiftedR,
                 (int)dbgOutL, (int)dbgOutR,
                 i2sShiftBits, currentGainFactor, dbgPeak);
        simplePrintln(String(dbgLine));
        debugSampleReady = false;
    }""", "loop log push")

save(INO, s)
print("\nDONE. Commit and recompile.")