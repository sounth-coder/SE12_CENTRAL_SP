
    // NESA HSC OFFICIAL DAY 
    const hscDate = new Date("2026-10-13T09:00:00+11:00");

    const monthsEl = document.getElementById("months");
    const weeksEl = document.getElementById("weeks");
    const daysEl = document.getElementById("days");
    const hoursEl = document.getElementById("hours");
    const minutesEl = document.getElementById("minutes");
    const secondsEl = document.getElementById("seconds");

    function pad(value) {
      return String(value).padStart(2, "0");
    }

    function updateCountdown() {
      const now = new Date();
      let difference = hscDate - now;

      if (difference <= 0) {
        monthsEl.textContent = "00";
        weeksEl.textContent = "00";
        daysEl.textContent = "00";
        hoursEl.textContent = "00";
        minutesEl.textContent = "00";
        secondsEl.textContent = "00";
        return;
      }

      const second = 1000;
      const minute = second * 60;
      const hour = minute * 60;
      const day = hour * 24;
      const week = day * 7;
      const month = day * 30.4375;

      const months = Math.floor(difference / month);
      difference %= month;

      const weeks = Math.floor(difference / week);
      difference %= week;

      const days = Math.floor(difference / day);
      difference %= day;

      const hours = Math.floor(difference / hour);
      difference %= hour;

      const minutes = Math.floor(difference / minute);
      difference %= minute;

      const seconds = Math.floor(difference / second);

      monthsEl.textContent = pad(months);
      weeksEl.textContent = pad(weeks);
      daysEl.textContent = pad(days);
      hoursEl.textContent = pad(hours);
      minutesEl.textContent = pad(minutes);
      secondsEl.textContent = pad(seconds);
    }

    updateCountdown();
    setInterval(updateCountdown, 1000);