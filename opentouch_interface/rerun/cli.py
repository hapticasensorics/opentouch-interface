import argparse
import os
import sys

import rerun as rr

from opentouch_interface.rerun.archetype_mapper import log_event
from opentouch_interface.rerun.decoder_stream import iter_events


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert OpenTouch .touch files to Rerun .rrd recordings."
    )
    parser.add_argument("input", help="Path to input .touch file")
    parser.add_argument("output", help="Path to output .rrd file")
    parser.add_argument(
        "--downsample",
        type=int,
        default=1,
        help="Downsample camera frames by this stride (default: 1)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])

    if args.downsample < 1:
        raise ValueError("--downsample must be >= 1")

    if not os.path.isfile(args.input):
        raise FileNotFoundError(f"Input file not found: {args.input}")

    output_dir = os.path.dirname(os.path.abspath(args.output))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    rr.init("opentouch_to_rrd", spawn=False)
    rr.save(args.output)

    for sensor_name, stream_name, delta, data in iter_events(args.input):
        log_event(
            sensor_name=sensor_name,
            stream_name=stream_name,
            delta=delta,
            data=data,
            image_downsample=args.downsample,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
