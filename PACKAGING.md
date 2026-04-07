# Packaging

This project is prepared for Windows desktop distribution with PyInstaller.

## Build prerequisites

1. Activate or create the local virtual environment.
2. Install runtime dependencies from `requirements.txt`.
3. Install build tooling from `requirements-build.txt`.

Example:

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
```

## Offline ephemeris support

For fully offline Swiss Ephemeris operation, place the official ephemeris files in:

- `app/data/ephemeris`

At runtime the application resolves ephemeris files in this order:

1. `HOROSCOPE_EPHEMERIS_DIR`
2. `<distribution folder>\ephemeris`
3. bundled `app/data/ephemeris`

## Build command

```powershell
.\tools\build_windows.ps1
```

This creates an onedir build at:

- `dist/HoroscopeApp`

## What is bundled

- the PyQt desktop application entrypoint from `main.py`
- app data under `app/data`
- the default astrology config
- database migrations
- timezonefinder packaged data

## Runtime layout

In a packaged build the app writes these beside the executable:

- `database/horoscope.db`
- `logs/horoscope.log`
- `app/config/astrology_config.json`

That keeps the build offline-friendly and avoids writing into PyInstaller's temp extraction directory.
