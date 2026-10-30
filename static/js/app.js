document.addEventListener('DOMContentLoaded', () => {
    const $ = id => document.getElementById(id);
    const form = $("examForm");
    if (!form) return;

    const classes = $("className");
    const subjects = typeof DB_SUBJECTS !== 'undefined' ? DB_SUBJECTS : {};

    if ($("formNumber")) {
        $("formNumber").textContent = `SN-${new Date().getFullYear()}-${Math.floor(Math.random() * 10000)}`;
    }

    function sync() {
        if ($("metaExam") && $("examType")) {
            $("metaExam").textContent = $("examType").value;
        }
    }

    function renderSubjects(keep = []) {
        if (!$("subjects") || !classes) return;
        
        $("subjects").replaceChildren();
        if (!classes.value) {
            $("subjects").textContent = "Select a class to see subjects.";
            updateCount(); return;
        }
        
        let classSubjects = subjects[classes.value] || ["General"]; 
        
        classSubjects.forEach(s => {
            let label = document.createElement("label"); 
            label.className = "subject-option";
            let cb = document.createElement("input"); 
            cb.type = "checkbox"; 
            cb.name = "subjects"; 
            cb.value = s;
            cb.checked = keep.includes(s);
            cb.addEventListener("change", updateCount);
            let span = document.createElement("span"); 
            span.textContent = s;
            label.append(cb, span); 
            $("subjects").append(label);
        });
        updateCount();
    }

    function updateCount() {
        let selected = [...document.querySelectorAll('input[name="subjects"]:checked')].map(x => x.value);
        if ($("subjectCount")) $("subjectCount").textContent = selected.length;
    }

    function note(s) {
        if ($("notification")) {
            $("notification").textContent = s; 
            $("notification").hidden = false;
            setTimeout(() => { $("notification").hidden = true; }, 4000);
        } else {
            alert(s);
        }
    }

    function edit() {
        if (form) form.hidden = false; 
        if ($("previewPanel")) $("previewPanel").hidden = true; 
        window.scrollTo(0, 0);
    }

    function preview() {
        if (!window.FormValidation || !window.FormValidation.validate(false)) {
            note("Please correct highlighted fields."); return;
        }
        if (window.FormPreview) window.FormPreview.build();
        if (form) form.hidden = true; 
        if ($("previewPanel")) $("previewPanel").hidden = false; 
        window.scrollTo(0, 0);
    }

    function submit() {
        if (!window.FormValidation || !window.FormValidation.validate(true)) {
            edit(); 
            note("Please correct errors and acknowledge declaration."); 
            return;
        }
        
        if (confirm("Are you sure you want to submit this exam form?")) {
            // requestSubmit triggers HTML5 validation as well
            if (form.requestSubmit) {
                form.requestSubmit();
            } else {
                form.submit();
            }
        }
    }

    if (classes) {
        classes.addEventListener("change", () => { sync(); renderSubjects(); });
    }
    
    if ($("examType")) {
        $("examType").addEventListener("change", sync);
    }

    if ($("previewForm")) $("previewForm").addEventListener('click', preview);
    if ($("editForm")) $("editForm").addEventListener('click', edit);
    if ($("submitForm")) $("submitForm").addEventListener('click', submit);
    if ($("previewSubmit")) $("previewSubmit").addEventListener('click', submit);
    
    if ($("printForm")) $("printForm").addEventListener('click', () => window.print());
    if ($("previewPrint")) $("previewPrint").addEventListener('click', () => window.print());

    sync(); 
    renderSubjects(); 
});