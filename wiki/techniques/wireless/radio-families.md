---
title: "Radio Families (Non-WiFi)"
type: technique
tags: [wireless, ble, bluetooth, zigbee, z-wave, lorawan, sub-ghz]
phase: exploitation
date_created: 2026-11-20
---


# Radio families beyond Wi-Fi

Distilled from five claude-red wireless skills. Operator promotes; never auto-promoted. Common thread: NONE of these families has a native IDS; the whole band is unmonitored by default, and most devices treat physical proximity as authentication.

## BLE

Trust-boundary flaw of the class: the BLE link itself treated as the trust boundary, privileged operations exposed on GATT characteristics writable by any nearby device.

Workflow: discover + enumerate GATT -> test every characteristic for unauth read/write/notify -> identify pairing method -> MITM if Just Works -> reverse companion app for proprietary formats.

```bash
sudo bettercap -eval "ble.recon on; events.show 60; ble.show"
sudo bettercap -eval "ble.recon on; ble.enum AA:BB:CC:DD:EE:FF"
# bluetoothctl: scan on / connect / menu gatt / list-attributes
gatttool -b <MAC> -I   # primary; char-desc; char-read-uuid; char-write-req <handle> <hex>
gatttool -b <MAC> --char-write-req --handle=0x0010 --value=0x01
```

16-bit UUIDs = SIG standard services; custom 128-bit UUIDs = vendor commands, the attack surface.

Pairing matrix:

| Method | Security | Attack |
|---|---|---|
| Just Works | none, authenticates anything | trivial MITM during pairing |
| Numeric Comparison | user confirms 6-digit | UI manipulation only |
| Passkey Entry | 6-digit code | brute in some pairing variants |
| OOB | NFC/QR | out of scope for RF attacker |

LE Legacy Pairing TK is crackable from a captured exchange; LE Secure Connections (4.2+, ECDH) is strong UNLESS Just Works is forced. Sniff with Sniffle (TI CC1352, multi-channel) or Ubertooth, then `crackle -i pairing.pcap -o decrypted.pcap` (recovers LTK in seconds for Legacy/Just Works; returns "strong key, no recovery" for Secure Connections). Active relay: btproxy / mirage-action-with-mitm makes you the legitimate peer for both sides.

Device classes: smart locks (unauth `unlock` write, replayable rolling tokens, hardcoded LTK via chip-off), cars (BLE phone-as-key relay, Tesla research 2022), medical (unauth GATT telemetry = proximity PHI read; careful coordinated disclosure), beacons (default passwords `0000`/`12345678`, rebrand attacks). Companion app: jadx the APK, grep `writeCharacteristic`.

## Bluetooth Classic (BR/EDR)

Legacy cars, industrial sensors, audio gear, older medical. Workflow: hcitool inq/scan -> sdptool browse -> per-profile unauth test -> KNOB applicability.

| Profile | UUID | Attack |
|---|---|---|
| OPP | 0x1105 | BlueSnarf/BlueBug (legacy, mostly extinct) |
| OBEX FTP | 0x1106 | filesystem browse/write on legacy |
| HSP/HFP | 0x1108/0x111E | eavesdrop active call audio |
| SPP | 0x1101 | industrial/IoT debug ports, usually unauthenticated |
| HID | 0x1124 | keyboard/mouse impersonation |
| A2DP | 0x110B/0x110A | audio injection/eavesdrop |

```bash
sudo rfcomm bind /dev/rfcomm0 AA:BB:CC:DD:EE:FF 1   # SPP, channel 1
sudo screen /dev/rfcomm0 9600                       # device CLI / debug menu
```

- KNOB (CVE-2019-9506): force 1-byte encryption key negotiation, trivially brute the link key. internalblue (Broadcom firmware patch). Alive on pre-2019 BCM chipsets, automotive stacks, cheap audio.
- BlueBorne (CVE-2017-1000251 family): stack buffer overflows (BlueZ, Android, Windows, iOS); patched 2017-2018 but unpatched embedded Linux is common. Armis scanner checks patch level.
- HID spoofing: `hciconfig hci0 class 0x000540; sdptool add HID` -> keystroke injection on paired host.
- Non-discoverable devices need redfang address brute (~7h per OUI prefix).

## Zigbee / Thread / Matter (802.15.4 mesh)

Zigbee crypto-key-reuse is the chronic flaw; Thread ships stronger defaults (IPv6/6LoWPAN + PSKc); Matter unifies commissioning with real crypto but implementation pitfalls remain.

Hardware: TI CC2531 (cheap), CC2652/Sonoff Dongle E (modern), ApiMote + KillerBee, HackRF.

```bash
zbstumbler -i 0              # find networks
zbdump -c 11 -w zigbee.pcap  # channel 11-26, 2.4 GHz
# Wireshark dot15d4 + zbee_nwk dissectors
```

Touchlink commissioning abuse (consumer Zigbee 3.0 lighting): leaked master key `0x9F5595F10257C8A469CBF42BC93FEE31` derives the transport key protecting the network-key exchange during commissioning; capture the commissioning frames, recover the network key. Z3sec toolkit:

```bash
python z3sec_inter_pan.py --command "factory_reset_request" --device <addr>
python z3sec_inter_pan.py --command "join_network" --network <PANID>
```

Outcomes: remote factory reset (mass DoS), steal devices into your network, read network keys. Network-key capture during joins: sniff coordinator + joiner; Zigbee 1.x default trust-center link key `ZigBeeAlliance09` decrypts the exchange; modern networks use device-specific install codes. With the network key, issue ZCL commands as any device (door lock unlock, switch, level, network flood) via scapy-dot15d4 crafted frames.

Thread: attack the commissioner, not the mesh. PSKc theft from companion apps (Apple Home, Nest), credential reuse to join, 6LoWPAN routing attacks (rank manipulation, sinkhole). Matter: setup-code replay if the commissioning window is not closed, BLE-MITM during initial commissioning, fabric-attestation flaws in early implementations.

## Z-Wave (sub-GHz mesh, 908 MHz US / 868 MHz EU)

S0 flaw: network key derived from a fixed all-zero PSK during inclusion of the first device. Sniff the ~2-second inclusion window (trigger via factory-reset of a node if needed) -> derive session key -> decrypt all past and future S0 traffic. S2 (Z-Wave Plus v2, mandatory 2017): Curve25519 ECDH, DSK verified out-of-band (sticker/QR). S2 attack surface is implementation: inclusion-mode-always-open misconfig, firmware verification bugs, ECDH side channels on constrained chips, DSK on a sticker (physical access).

Unauthenticated nodes: older sensors/switches accept cleartext commands:

```python
from scapy.contrib.zwave import *   # scapy-zwave community fork
frame = ZWave(home_id=0x12345678)/ZWaveBasic(set_value=0xff)
sendp(frame, iface='ezwave0')
```

Hub pivots (often easier than RF): SmartThings, Hubitat, Vera, Home Assistant, Z-Wave JS UI. Home Assistant `~/.homeassistant/zwave_js.json` holds keys; older Hubitat web UI default password. Hub compromise = PSK + command authority over every paired device.

Tools: EZ-Wave (HackRF firmware, `ezwave-sniff -f 908.4MHz -o capture.pcap`), RTL-SDR passive sniffing, Aeotec Z-Stick as legitimate node. Default home-ID brute only works on default-config lab gear.

## LoRaWAN + sub-GHz proprietary (433/868/915 MHz)

Hardware ladder: RTL-SDR (RX recon) -> Flipper Zero (quick replay) -> YARD Stick One (TX sub-GHz) -> HackRF One (full transceiver) -> LoRa gateway (standards-compliant testing).

LoRaWAN: OTAA devices derive session keys at join (Join-Request/Accept encrypted with AppKey; extract AppKey from firmware -> recover NwkSKey/AppSKey -> decrypt + inject). ABP devices ship pre-flashed keys with classic flaws: same key across thousands of devices, no frame-counter rollover protection (replay any historical uplink on 1.0.x stacks), predictable sequential DevAddr. With keys + DevAddr, inject downlinks (config changes, remote commands).

Sub-GHz proprietary:

```bash
rtl_433 -f 433.92M -A    # auto-decode known devices
hackrf_transfer -r garage.iq -f 433920000 -s 8000000 -n 80000000
# Flipper Zero: Read -> save -> replay from file
```

- Fixed-code remotes: same packet every press; capture once, replay forever.
- KeeLoq (older garage doors, some cars): 32-bit block cipher with manufacturer key, extracted publicly for major brands; decrypt rolling code -> predict next valid code (RollingPwn). Modern deployments rotated keys; legacy hardware still vulnerable.
- TPMS (315/433 MHz): unauthenticated broadcast; spoof low-pressure alerts with a crafted modulator.

Unknown protocol reconstruction: Universal Radio Hacker (URH) walks raw .iq -> modulation -> symbols -> bits -> packet structure with no docs; Inspectrum for visual analysis.

## Cross-family reporting notes

- Per device: exact frequency, modulation, baud, packet format, replay viability.
- Distinguish capture-replay vs crafted-frame attacks.
- Crypto state classification: cleartext / weak-fixed-key / standards-compliant.
- LoRaWAN: document AppKey/NwkSKey/AppSKey storage location in firmware.
- Z-Wave: map S0 vs S2 per node; flag S0 leftovers on S2-capable networks.
- BLE/BT Classic: chipset + firmware version (often visible in service records) for CVE mapping (BlueBorne, KNOB, BlueFrag).

<!-- promoted-slug: radio-families -->
