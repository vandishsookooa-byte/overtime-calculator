# Overtime Calculator

A **professional Python desktop application** for tracking daily work hours and calculating overtime, built with `tkinter` + `SQLite` — no third-party packages required.

---

## Features

| Feature | Details |
|---|---|
| **Daily time entry** | Input start time, end time, and break duration per day |
| **Payroll calendar** | 19th of each month → 18th of the following month |
| **Overtime breakdown** | Regular hours, OT minutes, OT hours, OT pay — per day |
| **Auto-save** | All data saved automatically to a local `overtime_data.db` SQLite file |
| **Period summary** | Totals for any of the last 6 payroll periods |
| **Settings** | Hourly rate, regular hours/day, OT multiplier, currency symbol, employee name |
| **Dark UI** | Professional dark-themed interface |

---

## Requirements

- Python **3.10+**
- `tkinter` (ships with the Python installer on Windows and macOS)

### Linux (if tkinter is missing)

```bash
# Ubuntu / Debian
sudo apt-get install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch Linux
sudo pacman -S tk
```

---

## Running the App

```bash
python3 overtime_calculator.py
```

or on Windows:

```cmd
python overtime_calculator.py
```

The database file `overtime_data.db` is created automatically in the same folder as the script.

---

## How to Use

1. **Enter Times** tab — Select a date, type your start / end time (24-hour `HH:MM`), set break minutes, then click **Save Entry**.
2. The **Day Breakdown** section instantly shows total hours, OT minutes/hours, and costs.
3. **Payroll Period** tab — Choose any payroll period from the dropdown to see the full summary and per-day breakdown.
4. **Settings** — Set your hourly rate, regular hours per day (default 8), and OT multiplier (default 1.5×).

---

## Data Storage

All entries are stored in `overtime_data.db` (SQLite) in the application directory. You can back this file up at any time.

---

## Overtime Calculation

```
Total worked = (End − Start) − Break minutes
Overtime     = max(Total worked − Regular hours, 0)
OT Pay       = OT Hours × Hourly Rate × OT Multiplier
Regular Pay  = min(Total worked, Regular hours) × Hourly Rate
```
