Place Swiss Ephemeris data files (`*.se1`, `*.se2`, `*.seas`, and related files)
in this folder before building a distribution if you want fully offline ephemeris
lookups from bundled data.

The packaged application will look for ephemeris files in:
1. `HOROSCOPE_EPHEMERIS_DIR`
2. `<app folder>\ephemeris`
3. bundled `app/data/ephemeris`

If this folder is empty, pyswisseph may still fall back to its default calculation
mode, but shipping official ephemeris files is recommended for production use.
