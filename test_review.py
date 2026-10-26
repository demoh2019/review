"""Regression tests with synthetic input; no racing data or network needed."""

import contextlib
import datetime as dt
import io
import pathlib
import tempfile
import unittest

import test as board


class LeaderboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)

    def write(self, filename, contents):
        path = self.root / filename
        path.write_text(contents, encoding="utf-8")
        return str(path)

    def test_racer_parser_preserves_names_and_teams(self):
        file = self.write("abbreviations.txt",
                          "SVM_Sebastian Vettel_FERRARI\n"
                          "DRR_Daniel Ricciardo_RED BULL RACING\n\n")
        self.assertEqual(
            board.create_racer_abbreviations_dict(file),
            {"SVM": ("Sebastian Vettel", "FERRARI"),
             "DRR": ("Daniel Ricciardo", "RED BULL RACING")}
        )

    def test_reject_bad_abbreviations(self):
        for contents in ("invalid\n", "SVM_Name_Team\nSVM_Other_Team\n",
                         "SVM__Team\n"):
            with self.subTest(contents=contents):
                with self.assertRaises(ValueError):
                    board.create_racer_abbreviations_dict(
                        self.write("abbr", contents)
                    )

    def test_parse_timings(self):
        file = self.write("start.log",
                          "SVM2018-05-24_12:01:02.123\n"
                          "DRR2018-05-24_12:00:00.000\n")
        result = board.retrieve_timings_from_log(file)
        self.assertEqual(result["SVM"].time(), dt.time(12, 1, 2, 123000))
        self.assertEqual(result["DRR"].time(), dt.time(12, 0))

    def test_reject_malformed_or_duplicate_timing(self):
        for contents in ("SVMbad\n", "SVM2018-05-24_25:00:00.000\n",
                         "SVM2018-05-24_12:00:00.000\n"
                         "SVM2018-05-24_12:01:00.000\n"):
            with self.subTest(contents=contents):
                with self.assertRaises(ValueError):
                    board.retrieve_timings_from_log(
                        self.write("timing.log", contents)
                    )

    def test_order_and_midnight_wrap(self):
        starts = {"SVM": dt.datetime(1900, 1, 1, 23, 59, 59),
                  "DRR": dt.datetime(1900, 1, 1, 12, 0, 0)}
        ends = {"SVM": dt.datetime(1900, 1, 1, 0, 0, 1),
                "DRR": dt.datetime(1900, 1, 1, 12, 0, 5)}
        racers = {"SVM": ("Sebastian", "Ferrari"),
                  "DRR": ("Daniel", "Red Bull")}
        self.assertEqual(
            list(board.sorted_individual_results(starts, ends, racers)),
            ["SVM", "DRR"]
        )
        self.assertEqual(
            list(board.sorted_individual_results(starts, ends, racers, True)),
            ["DRR", "SVM"]
        )

    def test_reject_missing_and_unregistered_racers(self):
        t = dt.datetime(1900, 1, 1, 12)
        with self.assertRaisesRegex(ValueError, "missing ends"):
            board.sorted_individual_results({"SVM": t}, {}, {})
        with self.assertRaisesRegex(ValueError, "unknown racer"):
            board.sorted_individual_results({"SVM": t}, {"SVM": t}, {})

    def test_format_without_loss_of_precision(self):
        self.assertEqual(board.format_lap(dt.timedelta(seconds=1.234)),
                         "00:01.234")
        self.assertEqual(board.format_lap(dt.timedelta(hours=1, seconds=5)),
                         "01:00:05.000")
        with self.assertRaises(ValueError):
            board.format_lap(dt.timedelta(seconds=-1))

    def test_print_uses_supplied_metadata_not_globals(self):
        ordered = {"SVM": dt.timedelta(seconds=1.5)}
        stream = io.StringIO()
        board.print_result_board(ordered, {"SVM": ("Sebastian", "Ferrari")},
                                 output=stream)
        self.assertIn("Sebastian", stream.getvalue())
        self.assertIn("Ferrari", stream.getvalue())
        self.assertIn("00:01.500", stream.getvalue())

    def test_cli_integration(self):
        abbr = self.write("abbr", "SVM_Sebastian Vettel_FERRARI\n")
        start = self.write("start", "SVM2018-05-24_12:00:00.000\n")
        end = self.write("end", "SVM2018-05-24_12:00:03.250\n")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            rc = board.main(["--abbreviations", abbr, "--start", start,
                             "--end", end])
        self.assertEqual(rc, 0)
        self.assertIn("00:03.250", stdout.getvalue())

    def test_cli_missing_file_is_clear_error(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                board.main(["--abbreviations", str(self.root / "missing")])
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
