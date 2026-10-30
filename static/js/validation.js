window.FormValidation = (() => {
    const $ = id => document.getElementById(id);
    const mobile = /^[6-9]\d{9}$/;

    function error(id, msg) {
        const e = $(id + "Error");
        if (e) e.textContent = msg || "";
        const f = $(id);
        if (f && msg) f.setAttribute("aria-invalid", "true");
        else if (f) f.removeAttribute("aria-invalid");
    }

    function validate(forSubmit = false) {
        let ok = true;
        const req = [
            ["studentName", "Enter the student's full name."],
            ["fatherName", "Enter the father's name."],
            ["dob", "Enter date of birth."],
            ["gender", "Select gender."],
            ["className", "Select a class."],
            ["section", "Enter section."],
            ["parentMobile", "Enter parent/guardian mobile number."],
            ["address", "Enter full address."]
        ];

        req.forEach(([id, msg]) => {
            let el = $(id);
            if (!el) return;
            let v = el.value.trim(), e = v ? "" : msg;
            if (id === "dob" && v) {
                let d = new Date(v + "T00:00:00"), t = new Date();
                t.setHours(0, 0, 0, 0);
                if (Number.isNaN(d.getTime()) || d > t) e = "Date of birth must be a valid past date.";
            }
            if (id === "parentMobile" && v && !mobile.test(v)) e = "Enter a valid 10-digit mobile starting 6–9.";
            error(id, e);
            if (e) ok = false;
        });

        let smEl = $("studentMobile");
        if (smEl) {
            let sm = smEl.value.trim(), se = sm && !mobile.test(sm) ? "Enter a valid 10-digit mobile starting 6–9." : "";
            error("studentMobile", se);
            if (se) ok = false;
        }

        const chosen = document.querySelectorAll('input[name="subjects"]:checked');
        const subErr = $("subjectsError");
        if (subErr) subErr.textContent = chosen.length ? "" : "Select at least one subject.";
        if (!chosen.length) ok = false;

        const decEl = $("declaration");
        if (decEl) {
            const de = forSubmit && !decEl.checked ? "Please confirm the declaration." : "";
            const decErr = $("declarationError");
            if (decErr) decErr.textContent = de;
            if (de) ok = false;
        }

        return ok;
    }

    function clearErrors() {
        document.querySelectorAll(".error").forEach(e => e.textContent = "");
        document.querySelectorAll('[aria-invalid="true"]').forEach(e => e.removeAttribute("aria-invalid"));
    }

    return { validate, clearErrors };
})();