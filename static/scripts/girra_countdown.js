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
const TIMETABLE_STORAGE_KEY = "girra-countdown-timetable-code";
const PERIOD_LABELS = {
    "0": "Period 0",
    RC: "Roll Call",
    R: "Recess",
    L1: "Lunch 1",
    L2: "Lunch 2",
    Bus1: "Bus 1",
    Bus2: "Bus 2"
};

let importedTimetable = null;

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

function toDateKey(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function normalizeTime(time) {
    if (!time || typeof time !== "string") {
        return "";
    }

    const [hours, minutes] = time.split(":").map(Number);
    if (Number.isNaN(hours) || Number.isNaN(minutes)) {
        return "";
    }

    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

function periodDisplayName(periodName) {
    return PERIOD_LABELS[periodName] || `Period ${periodName}`;
}

function lessonTitle(lesson) {
    if (!lesson) {
        return "";
    }

    return lesson.subject_name || lesson.lesson_class_name || lesson.type || "";
}

function lessonMeta(lesson) {
    if (!lesson) {
        return "";
    }

    const details = [];
    if (lesson.lesson_class_name && lesson.lesson_class_name !== lessonTitle(lesson)) {
        details.push(lesson.lesson_class_name);
    }
    if (lesson.room_name) {
        details.push(`Room ${lesson.room_name}`);
    }
    if (Array.isArray(lesson.teachers) && lesson.teachers.length) {
        details.push(lesson.teachers.join(", "));
    }

    return details.join(" · ");
}

function periodLessonSummary(period) {
    const lessons = Array.isArray(period.lessons) ? period.lessons : [];
    const lesson = lessons[0];
    const title = lessonTitle(lesson);
    const meta = lessonMeta(lesson);

    if (!title) {
        return {
            title: periodDisplayName(period.name),
            meta: "",
            hasLesson: false
        };
    }

    return {
        title,
        meta,
        hasLesson: true
    };
}

function normalizeTimetable(rawTimetable) {
    const containers = Array.isArray(rawTimetable) ? rawTimetable : [rawTimetable];
    const dates = {};

    containers.forEach((container) => {
        const sourceDates = container && container.dates;
        if (!sourceDates || typeof sourceDates !== "object") {
            return;
        }

        Object.values(sourceDates).forEach((day) => {
            if (!day || !day.date_name || !Array.isArray(day.period)) {
                return;
            }

            const periods = day.period
                .map((period) => ({
                    name: String(period.name || ""),
                    start: normalizeTime(period.start_time),
                    end: normalizeTime(period.end_time),
                    lessons: Array.isArray(period.lessons) ? period.lessons : []
                }))
                .filter((period) => period.name && period.start && period.end);

            if (periods.length) {
                dates[day.date_name] = {
                    dayName: day.day_name || "",
                    periods
                };
            }
        });
    });

    if (!Object.keys(dates).length) {
        throw new Error("No usable timetable dates were found.");
    }

    return { dates };
}

function loadStoredTimetable() {
    const stored = localStorage.getItem(TIMETABLE_STORAGE_KEY);
    const input = document.getElementById("timetable-code");

    if (!stored) {
        return;
    }

    if (input) {
        input.value = stored;
    }

    importedTimetable = normalizeTimetable(JSON.parse(stored));
}

function getTimetableDay(date) {
    if (!importedTimetable) {
        return null;
    }

    return importedTimetable.dates[toDateKey(date)] || null;
}

function timetableScheduleForDate(date) {
    const timetableDay = getTimetableDay(date);
    if (!timetableDay) {
        return null;
    }

    return timetableDay.periods.map((period) => {
        const summary = periodLessonSummary(period);
        return [summary.title, period.start, period.end, {
            periodName: period.name,
            periodLabel: periodDisplayName(period.name),
            meta: summary.meta,
            hasLesson: summary.hasLesson
        }];
    });
}

function getNextSchoolDay(date) {
    const next = new Date(date);
    do {
        next.setDate(next.getDate() + 1);
    } while (!timetableScheduleForDate(next) && !getScheduleForDay(next.getDay()));
    next.setHours(0, 0, 0, 0);
    return next;
}

function renderBellList(schedule, now) {
    const list = document.getElementById("bell-list");
    list.innerHTML = "";

    schedule.forEach(([name, start, end, details = {}]) => {
        const startDate = dateAtTime(now, start);
        const endDate = dateAtTime(now, end);
        const isCurrent = start !== end && now >= startDate && now < endDate;
        const isPast = now >= endDate;
        const label = details.periodLabel ? `${details.periodLabel}: ${name}` : name;

        const row = document.createElement("div");
        row.className = `bell-row${isCurrent ? " active" : ""}${isPast ? " past" : ""}`;

        const title = document.createElement("span");
        title.textContent = label;

        if (details.meta) {
            const meta = document.createElement("small");
            meta.textContent = details.meta;
            title.appendChild(meta);
        }

        const time = document.createElement("strong");
        time.textContent = start === end ? formatTime(start) : `${formatTime(start)} - ${formatTime(end)}`;

        row.append(title, time);
        list.appendChild(row);
    });
}

function renderTimetableStatus(message, isError = false) {
    const status = document.getElementById("timetable-code-status");
    if (!status) {
        return;
    }

    status.textContent = message;
    status.classList.toggle("error-text", isError);
}

function setupTimetableImport() {
    const input = document.getElementById("timetable-code");
    const addButton = document.getElementById("add-timetable-code");
    const clearButton = document.getElementById("clear-timetable-code");

    if (!input || !addButton || !clearButton) {
        return;
    }

    try {
        loadStoredTimetable();
        if (importedTimetable) {
            renderTimetableStatus("Timetable loaded on this device.");
        }
    } catch (error) {
        importedTimetable = null;
        renderTimetableStatus("Saved timetable code could not be read. Paste it again.", true);
    }

    addButton.addEventListener("click", () => {
        const code = input.value.trim();
        if (!code) {
            renderTimetableStatus("Paste timetable JSON before adding it.", true);
            return;
        }

        try {
            const parsed = JSON.parse(code);
            importedTimetable = normalizeTimetable(parsed);
            localStorage.setItem(TIMETABLE_STORAGE_KEY, code);
            renderTimetableStatus(`Timetable added with ${Object.keys(importedTimetable.dates).length} day(s).`);
            updateCountdown();
        } catch (error) {
            importedTimetable = null;
            renderTimetableStatus("That code is not valid timetable JSON.", true);
        }
    });

    clearButton.addEventListener("click", () => {
        importedTimetable = null;
        input.value = "";
        localStorage.removeItem(TIMETABLE_STORAGE_KEY);
        renderTimetableStatus("Timetable code cleared.");
        updateCountdown();
    });
}

function updateCountdown() {
    const now = new Date();
    const day = now.getDay();
    const timetableDay = getTimetableDay(now);
    const schedule = timetableScheduleForDate(now) || getScheduleForDay(day);
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

    dayElement.textContent = timetableDay && timetableDay.dayName
        ? `${DAY_NAMES[day]} · ${timetableDay.dayName}`
        : DAY_NAMES[day];
    renderBellList(schedule, now);

    if (currentBlock) {
        const [, start, end, details = {}] = currentBlock;
        const endDate = dateAtTime(now, end);
        const nextEvent = schedule.find(([, eventStart, eventEnd]) => {
            const eventDate = dateAtTime(now, eventEnd);
            return eventStart === eventEnd && eventDate > now && eventDate <= endDate;
        });

        if (nextEvent) {
            currentElement.textContent = currentBlock[0];
            rangeElement.textContent = [
                details.periodLabel || "",
                `${formatTime(start)} - ${formatTime(end)}`,
                details.meta || ""
            ].filter(Boolean).join(" · ");
            timeElement.textContent = formatDuration(dateAtTime(now, nextEvent[2]) - now);
            targetElement.textContent = `Until ${nextEvent[0]}`;
            return;
        }

        currentElement.textContent = currentBlock[0];
        rangeElement.textContent = [
            details.periodLabel || "",
            `${formatTime(start)} - ${formatTime(end)}`,
            details.meta || ""
        ].filter(Boolean).join(" · ");
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

setupTimetableImport();
updateCountdown();
setInterval(updateCountdown, 1000);
