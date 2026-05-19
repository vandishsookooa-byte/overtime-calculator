const form = document.getElementById("overtime-form");
const errorMessage = document.getElementById("error-message");
const resultsSection = document.getElementById("results");

const regularHoursEl = document.getElementById("regular-hours");
const overtimeHoursEl = document.getElementById("overtime-hours");
const regularPayEl = document.getElementById("regular-pay");
const overtimePayEl = document.getElementById("overtime-pay");
const totalPayEl = document.getElementById("total-pay");

const OVERTIME_THRESHOLD = 40;
const OVERTIME_MULTIPLIER = 1.5;

function formatMoney(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);
}

function formatHours(value) {
  return Number(value).toFixed(2);
}

function getInputNumber(inputId) {
  const rawValue = document.getElementById(inputId).value;
  return Number.parseFloat(rawValue);
}

function calculatePay(hourlyRate, hoursWorked) {
  const regularHours = Math.min(hoursWorked, OVERTIME_THRESHOLD);
  const overtimeHours = Math.max(hoursWorked - OVERTIME_THRESHOLD, 0);
  const regularPay = regularHours * hourlyRate;
  const overtimePay = overtimeHours * hourlyRate * OVERTIME_MULTIPLIER;
  const totalPay = regularPay + overtimePay;

  return { regularHours, overtimeHours, regularPay, overtimePay, totalPay };
}

function clearOutput() {
  errorMessage.textContent = "";
  resultsSection.hidden = true;
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  clearOutput();

  const hourlyRate = getInputNumber("hourly-rate");
  const hoursWorked = getInputNumber("hours-worked");

  const hasInvalidValue =
    Number.isNaN(hourlyRate) ||
    Number.isNaN(hoursWorked) ||
    hourlyRate < 0 ||
    hoursWorked < 0;

  if (hasInvalidValue) {
    errorMessage.textContent =
      "Please enter valid non-negative numbers for hourly rate and hours worked.";
    return;
  }

  const pay = calculatePay(hourlyRate, hoursWorked);
  regularHoursEl.textContent = formatHours(pay.regularHours);
  overtimeHoursEl.textContent = formatHours(pay.overtimeHours);
  regularPayEl.textContent = formatMoney(pay.regularPay);
  overtimePayEl.textContent = formatMoney(pay.overtimePay);
  totalPayEl.textContent = formatMoney(pay.totalPay);
  resultsSection.hidden = false;
});
