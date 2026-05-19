# overtime-calculator

A simple browser-based overtime pay calculator.

## How it works

- Regular pay is calculated for up to **40 hours**.
- Overtime pay is calculated for hours above 40 at **1.5x** the hourly rate.
- Total pay = regular pay + overtime pay.

## Run locally

1. Open `/home/runner/work/overtime-calculator/overtime-calculator/index.html` in your browser.
2. Enter your hourly rate and hours worked.
3. Click **Calculate**.

## Formula

- `regularHours = min(hoursWorked, 40)`
- `overtimeHours = max(hoursWorked - 40, 0)`
- `regularPay = regularHours * hourlyRate`
- `overtimePay = overtimeHours * hourlyRate * 1.5`
- `totalPay = regularPay + overtimePay`
