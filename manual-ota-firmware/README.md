# Manual OTA firmware

This folder contains the current app-only firmware files for manual OTA update through the device
Web UI.

Open the device update page:

```text
http://<device-ip>/ota
```

Choose **Upload compiled file** and select the file matching your board:

```text
firmware-app-c3.bin    XIAO ESP32-C3
firmware-app-s3.bin    XIAO ESP32-S3
firmware-app-c5.bin    XIAO ESP32-C5
firmware-app-c6.bin    XIAO ESP32-C6
```

`firmware-app.bin` is kept as a compatibility alias for the XIAO ESP32-C6 build.
