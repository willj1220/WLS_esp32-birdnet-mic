#!/usr/bin/env python3
"""Round 3: DEBUG_SAMPLES + FRAMES_PER_PACKET/I2S_INTS_PER_PACKET/PAYLOAD_BYTES.
Run from the repo root AFTER patch_fork.py and patch_fork2.py:  python patch_fork3.py
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

s = rep(s,
"#define I2S_MCLK_PIN    4   // 256*fs master clock out to WM8782 (12.288 MHz @ 48 kHz)",
"""#define I2S_MCLK_PIN    4   // 256*fs master clock out to WM8782 (12.288 MHz @ 48 kHz)

// -- Packetization / diagnostics (WLS options)
#define DEBUG_SAMPLES        0   // 1 = log raw I2S words + shifted samples every 5 s (diagnose shift/format/wiring)
#define FRAMES_PER_PACKET    0   // 0 = one RTP packet per DMA chunk; >0 = fixed frames per RTP packet (e.g. 240 = 5 ms @ 48 kHz)
#if FRAMES_PER_PACKET > 0
#define I2S_INTS_PER_PACKET  (FRAMES_PER_PACKET * 2)                 // 32-bit stereo words per packet window
#define PAYLOAD_BYTES        (FRAMES_PER_PACKET * sizeof(int16_t))   // mono 16-bit RTP payload bytes per packet
#endif""", "defines block")

s = rep(s,
"""                i2s_16bit_buffer[ch][f] = (int16_t)amplified;
            }
        }""",
"""                i2s_16bit_buffer[ch][f] = (int16_t)amplified;
            }
        }

#if DEBUG_SAMPLES
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
#endif""", "debug instrumentation")

s = rep(s,
"""            bool delivered = false;
            for (uint8_t i = 0; i < MAX_CLIENTS; i++) {
                if (!clients[i].streaming) continue;
                if (clients[i].profileIndex != pi) continue;
                sendRTPPacket(clients[i], i2s_16bit_network_buffer[pi], samplesRead);
                if (clients[i].streaming) delivered = true;
            }
            if (delivered) {
                streamStats[pi].packetsSent++;
                audioPacketsSent++;
            }""",
"""            bool delivered = false;
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
#endif""", "packet slicing")

save(INO, s)
print("\nDONE. Commit and recompile.")