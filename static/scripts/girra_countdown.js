const BELL_SCHEDULES = {
    1: [
        ["Assembly/Meeting", "08:45", "09:00"],
        ["Period 1", "09:00", "10:00"],
        ["Period 2", "10:00", "11:00"],
        ["Recess", "11:00", "11:20"],
        ["Period 3", "11:20", "12:20"],
        ["Period 4 / L1", "12:20", "13:25"],
        ["Lunch 1", "13:25", "13:45"],
        ["Lunch 2 / P4", "13:45", "14:05"],
        ["Period 5", "14:05", "15:10"]
    ],
    2: [
        ["Period 1", "08:45", "09:50"],
        ["Period 2", "09:50", "10:55"],
        ["Recess", "10:55", "11:15"],
        ["Period 3", "11:15", "12:20"],
        ["Period 4 / L1", "12:20", "13:25"],
        ["Lunch 1", "13:25", "13:45"],
        ["Lunch 2 / P4", "13:45", "14:05"],
        ["Period 5", "14:05", "15:10"]
    ],
    3: [
        ["Period 1", "08:45", "09:45"],
        ["Period 2", "09:45", "10:45"],
        ["Recess", "10:45", "11:05"],
        ["Period 3", "11:05", "12:10"],
        ["Period 4 / L1", "12:10", "12:35"],
        ["Lunch 1", "12:35", "13:00"],
        ["Lunch 2 / P4", "13:00", "14:05"],
        ["Period 5", "14:05", "15:10"],
        ["Sport Bell", "14:45", "14:45"]
    ],
    4: [
        ["Period 1", "08:45", "09:50"],
        ["Period 2", "09:50", "10:55"],
        ["Recess", "10:55", "11:15"],
        ["Period 3", "11:15", "12:20"],
        ["Period 4 / L1", "12:20", "13:25"],
        ["Lunch 1", "13:25", "13:45"],
        ["Lunch 2 / P4", "13:45", "14:05"],
        ["Period 5", "14:05", "15:10"]
    ],
    5: [
        ["Period 1", "08:45", "09:50"],
        ["Period 2", "09:50", "10:55"],
        ["Recess", "10:55", "11:15"],
        ["Period 3", "11:15", "12:20"],
        ["Period 4 / L1", "12:20", "13:25"],
        ["Lunch 1", "13:25", "13:45"],
        ["Lunch 2 / P4", "13:45", "14:05"],
        ["Period 5", "14:05", "15:10"]
    ]
};

const DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
function getScheduleForDay(day) {
    return BELL_SCHEDULES[day] || null;
}

function dateAtTime(baseDate, time) {
    const [hours, minutes] = time.split(":").map(Number);
    const date = new Date(baseDate);
    date.setHours(hours, minutes, 0, 0);
    return date;
}

function formatTime(time) {
    const [hours, minutes] = time.split(":").map(Number);
    const suffix = hours >= 12 ? "pm" : "am";
    const displayHours = hours % 12 || 12;
    return `${displayHours}:${String(minutes).padStart(2, "0")}${suffix}`;
}

function formatDuration(milliseconds) {
    const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    return [hours, minutes, seconds]
        .map((value) => String(value).padStart(2, "0"))
        .join(":");
}

function getNextSchoolDay(date) {
    const next = new Date(date);
    do {
        next.setDate(next.getDate() + 1);
    } while (!getScheduleForDay(next.getDay()));
    next.setHours(0, 0, 0, 0);
    return next;
}

function renderBellList(schedule, now) {
    const list = document.getElementById("bell-list");
    list.innerHTML = "";

    schedule.forEach(([name, start, end]) => {
        const startDate = dateAtTime(now, start);
        const endDate = dateAtTime(now, end);
        const isCurrent = start !== end && now >= startDate && now < endDate;
        const isPast = now >= endDate;

        const row = document.createElement("div");
        row.className = `bell-row${isCurrent ? " active" : ""}${isPast ? " past" : ""}`;
        row.innerHTML = `
            <span>${name}</span>
            <strong>${start === end ? formatTime(start) : `${formatTime(start)} - ${formatTime(end)}`}</strong>
        `;
        list.appendChild(row);
    });
}

function updateCountdown() {
    const now = new Date();
    const day = now.getDay();
    const schedule = getScheduleForDay(day);
    const dayElement = document.getElementById("countdown-day");
    const currentElement = document.getElementById("countdown-current");
    const rangeElement = document.getElementById("countdown-range");
    const timeElement = document.getElementById("countdown-time");
    const targetElement = document.getElementById("countdown-target");

    if (!schedule) {
        const nextSchoolDay = getNextSchoolDay(now);
        dayElement.textContent = `${DAY_NAMES[day]} - no regular bells`;
        currentElement.textContent = "Weekend";
        rangeElement.textContent = `Next school day is ${DAY_NAMES[nextSchoolDay.getDay()]}.`;
        timeElement.textContent = formatDuration(nextSchoolDay - now);
        targetElement.textContent = "Until next school day";
        document.getElementById("bell-list").innerHTML = "<p class=\"muted-text\">No regular bell schedule today.</p>";
        return;
    }

    const currentBlock = schedule.find(([, start, end]) => start !== end && now >= dateAtTime(now, start) && now < dateAtTime(now, end));
    const upcomingBell = schedule.find(([, , end]) => now < dateAtTime(now, end));
    const firstBell = dateAtTime(now, schedule[0][1]);

    dayElement.textContent = DAY_NAMES[day];
    renderBellList(schedule, now);

    if (currentBlock) {
        const [, start, end] = currentBlock;
        const endDate = dateAtTime(now, end);
        const nextEvent = schedule.find(([, eventStart, eventEnd]) => {
            const eventDate = dateAtTime(now, eventEnd);
            return eventStart === eventEnd && eventDate > now && eventDate <= endDate;
        });

        if (nextEvent) {
            currentElement.textContent = currentBlock[0];
            rangeElement.textContent = `${formatTime(start)} - ${formatTime(end)}`;
            timeElement.textContent = formatDuration(dateAtTime(now, nextEvent[2]) - now);
            targetElement.textContent = `Until ${nextEvent[0]}`;
            return;
        }

        currentElement.textContent = currentBlock[0];
        rangeElement.textContent = `${formatTime(start)} - ${formatTime(end)}`;
        timeElement.textContent = formatDuration(endDate - now);
        targetElement.textContent = `Until ${currentBlock[0]} ends`;
        return;
    }

    if (now < firstBell) {
        currentElement.textContent = "Before school";
        rangeElement.textContent = `First bell at ${formatTime(schedule[0][1])}`;
        timeElement.textContent = formatDuration(firstBell - now);
        targetElement.textContent = "Until first bell";
        return;
    }

    if (upcomingBell) {
        currentElement.textContent = "Passing time";
        rangeElement.textContent = `Next bell at ${formatTime(upcomingBell[2])}`;
        timeElement.textContent = formatDuration(dateAtTime(now, upcomingBell[2]) - now);
        targetElement.textContent = "Until next bell";
        return;
    }

    const nextSchoolDay = getNextSchoolDay(now);
    currentElement.textContent = "School day finished";
    rangeElement.textContent = `Next school day is ${DAY_NAMES[nextSchoolDay.getDay()]}.`;
    timeElement.textContent = formatDuration(nextSchoolDay - now);
    targetElement.textContent = "Until next school day";
}

updateCountdown();
setInterval(updateCountdown, 1000);
