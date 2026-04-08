# ISS Tracker

A simple Python application to track the International Space Station (ISS) position using the Open Notify API.

## Requirements

- Python 3.6+
- No external dependencies required
- GUI mode uses the default web browser and does not require tkinter

## Installation

1. Clone or download the repository.
2. Run the script with Python:
   ```
   python iss_tracker.py
   ```

## Usage

Run the script:
```
python iss_tracker.py
```

By default, the application fetches the ISS position every 5 seconds and prints it to the console.

### Options

- `--interval SECONDS`
  - Set the polling interval in seconds.
  - Example: `python iss_tracker.py --interval 10`
- `--count N`
  - Collect `N` samples and exit.
  - Example: `python iss_tracker.py --count 12`
- `--output FILE`
  - Save results to a CSV file.
  - Example: `python iss_tracker.py --output iss_log.csv`
- `--gui`
  - Launch a simple graphical interface with a live map showing the ISS position.
  - Example: `python iss_tracker.py --gui`

### Examples

Run once every 10 seconds:
```
python iss_tracker.py --interval 10
```

Launch the GUI:
```
python iss_tracker.py --gui
```

Log ISS positions to CSV:
```
python iss_tracker.py --output iss_log.csv
```

Collect 20 samples and exit:
```
python iss_tracker.py --count 20
```

## API

Uses http://api.open-notify.org/iss-now.json which returns the current ISS position in JSON format.

## Troubleshooting

- Ensure internet connection is available.
- The API may have rate limits; if errors occur, wait and try again.
