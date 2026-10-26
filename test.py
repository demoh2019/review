"""Race lap leaderboard (stdlib-only; safe to import without input files)."""

import argparse
import datetime as dt
import re
import sys
from collections import OrderedDict

_ABBR = re.compile(r"^([A-Z0-9]+)_([^_]+)_([^_]+)$")
_TIME = re.compile(r"^([A-Z]+).*?(\d{2}:\d{2}:\d{2}\.\d+)$")


def create_racer_abbreviations_dict(file_name):
    """Load ABBR_Name_Team rows, rejecting ambiguous or malformed data."""
    racers = {}
    with open(file_name, encoding="utf-8") as source:
        for line_number, raw in enumerate(source, 1):
            line = raw.strip()
            if not line:
                continue
            match = _ABBR.fullmatch(line)
            if not match:
                raise ValueError(f"{file_name}:{line_number}: invalid racer row")
            abbreviation, name, team = match.groups()
            if not name.strip() or not team.strip():
                raise ValueError(f"{file_name}:{line_number}: empty name or team")
            if abbreviation in racers:
                raise ValueError(f"{file_name}:{line_number}: duplicate {abbreviation}")
            racers[abbreviation] = (name.strip(), team.strip())
    return racers


def retrieve_timings_from_log(file_name):
    """Load ABBR...HH:MM:SS.fraction rows as time-of-day datetimes."""
    timings = {}
    with open(file_name, encoding="utf-8") as source:
        for line_number, raw in enumerate(source, 1):
            line = raw.strip()
            if not line:
                continue
            match = _TIME.fullmatch(line)
            if not match:
                raise ValueError(f"{file_name}:{line_number}: invalid timing row")
            abbreviation, clock = match.groups()
            if abbreviation in timings:
                raise ValueError(f"{file_name}:{line_number}: duplicate {abbreviation}")
            try:
                timings[abbreviation] = dt.datetime.strptime(clock, "%H:%M:%S.%f")
            except ValueError as exc:
                raise ValueError(
                    f"{file_name}:{line_number}: invalid clock {clock}"
                ) from exc
    return timings


def sorted_individual_results(start_timings_, end_timings_, abbr_dict_,
                              reverse_order=False):
    """Order elapsed laps; support time-of-day laps crossing midnight once."""
    start_keys = set(start_timings_)
    end_keys = set(end_timings_)
    if start_keys != end_keys:
        raise ValueError(
            f"start/end racers differ: missing ends={sorted(start_keys - end_keys)}, "
            f"missing starts={sorted(end_keys - start_keys)}"
        )
    unknown = start_keys - set(abbr_dict_)
    if unknown:
        raise ValueError(f"unknown racer abbreviations: {sorted(unknown)}")
    laps = {}
    for racer in start_keys:
        elapsed = end_timings_[racer] - start_timings_[racer]
        if elapsed < dt.timedelta(0):
            elapsed += dt.timedelta(days=1)
        laps[racer] = elapsed
    return OrderedDict(
        sorted(laps.items(), key=lambda item: (item[1], item[0]),
               reverse=reverse_order)
    )


def format_lap(elapsed):
    """Return precise HH:MM:SS.mmm or MM:SS.mmm without string slicing."""
    milliseconds = round(elapsed.total_seconds() * 1000)
    if milliseconds < 0:
        raise ValueError("negative lap")
    total_seconds, milli = divmod(milliseconds, 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02}:{minutes:02}:{seconds:02}.{milli:03}"
    return f"{minutes:02}:{seconds:02}.{milli:03}"


def print_result_board(sorted_lap_results_, abbr_dict_, output=None):
    """Print rank, racer name, team and lap, without module-level globals."""
    stream = output if output is not None else sys.stdout
    for rank, (abbreviation, elapsed) in enumerate(sorted_lap_results_.items(), 1):
        name, team = abbr_dict_[abbreviation]
        print(f"{rank:<3} {name:<18} | {team:<30} | {format_lap(elapsed)}",
              file=stream)
        if rank == 15:
            print("-" * 70, file=stream)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Race lap leaderboard")
    parser.add_argument("--abbreviations", default="abbreviations.txt")
    parser.add_argument("--start", default="start.log")
    parser.add_argument("--end", default="end.log")
    parser.add_argument("--reverse", action="store_true",
                        help="Show slowest racer first")
    args = parser.parse_args(argv)
    try:
        abbreviations = create_racer_abbreviations_dict(args.abbreviations)
        start = retrieve_timings_from_log(args.start)
        end = retrieve_timings_from_log(args.end)
        results = sorted_individual_results(
            start, end, abbreviations, reverse_order=args.reverse
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print_result_board(results, abbreviations)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
