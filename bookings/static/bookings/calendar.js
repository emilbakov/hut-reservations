
document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("availability-calendar");

    if (!root) return;

    const title = document.getElementById("cal-title");
    const prevButton = document.getElementById("cal-prev");
    const nextButton = document.getElementById("cal-next");

    const arrival = document.querySelector(
        '#find-stay input[name="check_in"]'
    );

    const departure = document.querySelector(
        '#find-stay input[name="check_out"]'
    );

    const hutSlug = root.dataset.hutSlug || "";
    const endpoint = root.dataset.endpoint;

    const today = new Date();
    const firstMonth = new Date(
        today.getFullYear(),
        today.getMonth(),
        1
    );

    let cursor = new Date(firstMonth);

    const weekdays = [
        "Mon", "Tue", "Wed", "Thu",
        "Fri", "Sat", "Sun"
    ];

    function iso(y, m, d) {
        return (
            `${y}-` +
            `${String(m + 1).padStart(2, "0")}-` +
            `${String(d).padStart(2, "0")}`
        );
    }

    function makeElement(tag, className, text) {
        const element = document.createElement(tag);

        if (className) {
            element.className = className;
        }

        if (text !== undefined) {
            element.textContent = text;
        }

        return element;
    }

    async function render() {
        const year = cursor.getFullYear();
        const month = cursor.getMonth();

        if (title) {
            title.textContent = cursor.toLocaleDateString(
                undefined,
                {
                    month: "long",
                    year: "numeric"
                }
            );
        }

        root.replaceChildren();

        weekdays.forEach((day) => {
            root.append(
                makeElement("span", "cal-weekday", day)
            );
        });

        const offset = (
            new Date(year, month, 1).getDay() + 6
        ) % 7;

        for (let i = 0; i < offset; i++) {
            root.append(document.createElement("span"));
        }

        const params = new URLSearchParams({
            year: String(year),
            month: String(month + 1)
        });

        if (hutSlug) {
            params.set("hut", hutSlug);
        }

        try {
            const response = await fetch(
                `${endpoint}?${params.toString()}`,
                {
                    credentials: "same-origin"
                }
            );

            if (!response.ok) {
                throw new Error(
                    "Calendar unavailable for this month"
                );
            }

            const data = await response.json();

            const byDate = new Map(
                data.days.map((day) => [
                    day.date,
                    day
                ])
            );

            const numberOfDays = new Date(
                year,
                month + 1,
                0
            ).getDate();

            for (
                let day = 1;
                day <= numberOfDays;
                day++
            ) {
                const key = iso(year, month, day);
                const info = byDate.get(key);

                const button = document.createElement(
                    "button"
                );

                button.type = "button";

                button.className =
                    "cal-day " +
                    (
                        !info
                            ? "cal-disabled"
                            : info.free_beds > 0
                                ? "cal-free"
                                : "cal-full"
                    );

                button.disabled =
                    !info || info.free_beds <= 0;

                button.textContent = String(day);

                button.title = info
                    ? `${info.free_beds} beds free`
                    : "Not available";

                button.setAttribute(
                    "aria-label",
                    info
                        ? `${key}: ${info.free_beds} beds free`
                        : `${key}: not bookable`
                );

                if (!button.disabled) {
                    button.addEventListener(
                        "click",
                        () => {
                            if (arrival) {
                                arrival.value = key;
                            }

                            if (
                                departure &&
                                (
                                    !departure.value ||
                                    departure.value <= key
                                )
                            ) {
                                const next = new Date(
                                    year,
                                    month,
                                    day + 1
                                );

                                departure.value = iso(
                                    next.getFullYear(),
                                    next.getMonth(),
                                    next.getDate()
                                );
                            }

                            arrival?.focus();
                        }
                    );
                }

                root.append(button);
            }

        } catch (error) {
            root.append(
                makeElement(
                    "p",
                    "muted",
                    "Calendar unavailable for this month."
                )
            );
        }

        if (prevButton) {
            prevButton.disabled =
                cursor.getFullYear() === firstMonth.getFullYear() &&
                cursor.getMonth() === firstMonth.getMonth();
        }
    }

    if (prevButton) {
        prevButton.addEventListener("click", () => {
            const previous = new Date(
                cursor.getFullYear(),
                cursor.getMonth() - 1,
                1
            );

            if (previous >= firstMonth) {
                cursor = previous;
                render();
            }
        });
    }

    if (nextButton) {
        nextButton.addEventListener("click", () => {
            cursor = new Date(
                cursor.getFullYear(),
                cursor.getMonth() + 1,
                1
            );

            render();
        });
    }

    render();
});
