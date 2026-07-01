// Wait for the page to fully load before running any logic
document.addEventListener("DOMContentLoaded", initializeTimer);

// Track when the question loaded so we can calculate time spent
const questionStartTime = Date.now();

function initializeTimer() {
    const form = document.getElementById("answerForm");
    if (!form) return;

    // QUIZ_MODE is set inline in question.html by Flask
    // Only run the countdown timer in Quick Quiz mode — SAT has no time limit
    if (typeof QUIZ_MODE !== "undefined" && QUIZ_MODE === "quick") {
        const timerDisplay = document.getElementById("timer");
        if (!timerDisplay) return;

        const startingTime = parseInt(timerDisplay.textContent, 10);
        startTimer(startingTime, timerDisplay, form);
    }
}

function startTimer(timeLeft, timerDisplay, form) {
    const totalTime = timeLeft;
    const ringFill = document.getElementById("ringFill");
    const circumference = 213.6; // 2 * pi * 34

    updateDisplay(timerDisplay, timeLeft, ringFill, circumference, totalTime);

    const timerId = setInterval(function () {
        timeLeft--;
        updateDisplay(timerDisplay, timeLeft, ringFill, circumference, totalTime);

        // Turn the ring darker orange in the last 3 seconds
        if (timeLeft <= 3 && ringFill) {
            ringFill.classList.add("urgent");
        }

        if (timeLeft <= 0) {
            stopTimer(timerId);

            // Mark as timed out so Flask won't count it as correct
            const hidden = document.createElement("input");
            hidden.type  = "hidden";
            hidden.name  = "timed_out";
            hidden.value = "1";
            form.appendChild(hidden);

            // Inject time spent before submitting
            injectTimeSpent(form);

            const answerInput = document.getElementById("answerInput");
            if (answerInput) answerInput.removeAttribute("required");

            form.submit();
        }
    }, 1000);
}

// Updates the timer number and drains the SVG ring proportionally
function updateDisplay(timerDisplay, timeLeft, ringFill, circumference, totalTime) {
    timerDisplay.textContent = timeLeft;

    if (ringFill) {
        const progress = timeLeft / totalTime;
        const offset   = circumference * (1 - progress);
        ringFill.style.strokeDashoffset = offset;
    }
}

// Injects a hidden time_spent field into the form before submission
// time_spent is the number of seconds since the question loaded
function injectTimeSpent(form) {
    const timeSpent = ((Date.now() - questionStartTime) / 1000).toFixed(1);
    const field = document.createElement("input");
    field.type  = "hidden";
    field.name  = "time_spent";
    field.value = timeSpent;
    form.appendChild(field);
}

// Called when the user clicks a multiple choice button (A, B, C, or D)
function selectChoice(letter, btn) {
    const answerInput = document.getElementById("answerInput");
    if (answerInput) answerInput.value = letter;

    // Highlight the selected button
    document.querySelectorAll(".sat-choice-btn, .choice-btn").forEach(b => b.classList.remove("selected"));
    btn.classList.add("selected");

    // Inject time spent then submit after brief delay so highlight is visible
    setTimeout(function () {
        const form = document.getElementById("answerForm");
        injectTimeSpent(form);
        form.submit();
    }, 200);
}

// Called when the user clicks Skip
function skipQuestion() {
    const form = document.getElementById("answerForm");

    // Mark as skipped
    let skippedField = form.querySelector('input[name="skipped"]');
    if (!skippedField) {
        skippedField       = document.createElement("input");
        skippedField.type  = "hidden";
        skippedField.name  = "skipped";
        form.appendChild(skippedField);
    }
    skippedField.value = "1";

    const answerInput = document.getElementById("answerInput");
    if (answerInput) answerInput.removeAttribute("required");

    form.submit();
}

function stopTimer(timerId) {
    clearInterval(timerId);
}