window.FormPreview = (() => {
    const $ = id => document.getElementById(id);
    const v = id => { let el = $(id); return el ? (el.value || "").trim() || "—" : "—"; };
    const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
    const row = (a, b) => `<tr><th>${esc(a)}</th><td>${esc(b)}</td></tr>`;

    function build() {
        let subs = [...document.querySelectorAll('input[name="subjects"]:checked')].map(x => x.value);
        let formNoEl = $("formNumber");
        let formNo = formNoEl ? formNoEl.textContent : "N/A";

        if (!$("previewContent")) return;

        $("#previewContent").innerHTML = `
        <header class="school-header">
            <img class="school-logo" src="/static/assets/school-logo-left.svg" alt="Logo">
            <div class="school-heading">
                <h1>RES. SHANTI NIKETAN SHISHU VIDYA MANDIR</h1>
                <p>NAVINAGAR (JAMUI)</p>
                <p>${esc(v("examType").toUpperCase())} EXAMINATION 2026–2027</p>
                <h2>ONLINE EXAMINATION FORM</h2>
            </div>
            <img class="school-logo" src="/static/assets/school-logo-right.svg" alt="Logo">
        </header>
        <table class="preview-table">
            <tbody>
                ${row("Session", "2026–2027")}
                ${row("Examination", v("examType"))}
                ${row("Form Number", formNo)}
            </tbody>
        </table>
        <h3>STUDENT DETAILS</h3>
        <table class="preview-table">
            <tbody>
                ${row("Student's Full Name", v("studentName"))}
                ${row("Father's Name", v("fatherName"))}
                ${row("Mother's Name", v("motherName"))}
                ${row("Date of Birth", v("dob"))}
                ${row("Gender", v("gender"))}
                ${row("Class", v("className"))}
                ${row("Section", v("section"))}
                ${row("Roll Number", v("rollNumber"))}
                ${row("Admission Number", v("admissionNumber"))}
                ${row("Student Mobile", v("studentMobile"))}
                ${row("Parent/Guardian Mobile", v("parentMobile"))}
                ${row("Address", v("address"))}
            </tbody>
        </table>
        <h3>EXAMINATION DETAILS</h3>
        <table class="preview-table">
            <tbody>
                ${row("Class", v("className"))}
                ${row("Section", v("section"))}
            </tbody>
        </table>
        <p><b>Selected Subjects (${subs.length})</b></p>
        <div class="preview-subjects">
            ${subs.map(s => `<span>${esc(s)}</span>`).join("") || "None selected"}
        </div>
        <div class="preview-declaration">
            <b>Parent / Guardian Declaration</b>
            <p>${$("declaration") && $("declaration").checked ? "Declaration acknowledged." : "Declaration not acknowledged."} I confirm the information is correct to the best of my knowledge.</p>
        </div>
        <div class="signature-lines">
            <div>Student / Parent Signature</div>
            <div>School Office Use</div>
        </div>`;
    }
    return { build };
})();