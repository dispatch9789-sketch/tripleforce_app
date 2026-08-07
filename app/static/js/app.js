/* ═══════════════════════════════════════════════════════════════
   Triple Force Logistic LLC — Application JavaScript
   ═══════════════════════════════════════════════════════════════ */

(function () {
    "use strict";

    // ── Theme toggle ──
    const themeToggle = document.getElementById("themeToggle");
    const themeIcon = document.getElementById("themeIcon");
    const html = document.documentElement;

    // Load saved theme or use system preference
    let savedTheme = null;
    try { savedTheme = sessionStorage.getItem("tf-theme"); } catch (e) {}
    if (!savedTheme) {
        savedTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    html.setAttribute("data-theme", savedTheme);
    updateThemeIcon(savedTheme);

    if (themeToggle) {
        themeToggle.addEventListener("click", function () {
            const current = html.getAttribute("data-theme");
            const next = current === "dark" ? "light" : "dark";
            html.setAttribute("data-theme", next);
            try { sessionStorage.setItem("tf-theme", next); } catch (e) {}
            updateThemeIcon(next);
        });
    }

    function updateThemeIcon(theme) {
        if (!themeIcon) return;
        if (theme === "dark") {
            themeIcon.className = "bi bi-sun-fill";
        } else {
            themeIcon.className = "bi bi-moon-fill";
        }
    }

    // ── Sidebar toggle (mobile) ──
    const sidebarToggle = document.getElementById("sidebarToggle");
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("sidebarOverlay");

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener("click", function () {
            sidebar.classList.toggle("show");
            if (overlay) overlay.classList.toggle("show");
        });
    }

    if (overlay) {
        overlay.addEventListener("click", function () {
            sidebar.classList.remove("show");
            overlay.classList.remove("show");
        });
    }

    // Close sidebar when a link is clicked (mobile)
    if (sidebar) {
        sidebar.querySelectorAll(".sidebar-link").forEach(function (link) {
            link.addEventListener("click", function () {
                if (window.innerWidth < 992) {
                    sidebar.classList.remove("show");
                    if (overlay) overlay.classList.remove("show");
                }
            });
        });
    }

    // ── Auto-dismiss alerts after 5 seconds ──
    setTimeout(function () {
        document.querySelectorAll(".alert-dismissible").forEach(function (alert) {
            var bsAlert = bootstrap.Alert.getInstance(alert);
            if (bsAlert) bsAlert.close();
        });
    }, 5000);

    // ── Signature pad ──
    const canvas = document.getElementById("signaturePad");
    if (canvas) {
        const ctx = canvas.getContext("2d");
        let drawing = false;
        let lastX = 0, lastY = 0;

        function getPos(e) {
            const rect = canvas.getBoundingClientRect();
            const x = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
            const y = (e.touches ? e.touches[0].clientY : e.clientY) - rect.top;
            return { x: x * (canvas.width / rect.width), y: y * (canvas.height / rect.height) };
        }

        function startDraw(e) {
            e.preventDefault();
            drawing = true;
            const pos = getPos(e);
            lastX = pos.x;
            lastY = pos.y;
        }

        function draw(e) {
            if (!drawing) return;
            e.preventDefault();
            const pos = getPos(e);
            ctx.beginPath();
            ctx.moveTo(lastX, lastY);
            ctx.lineTo(pos.x, pos.y);
            ctx.strokeStyle = "#1a3a5c";
            ctx.lineWidth = 2.5;
            ctx.lineCap = "round";
            ctx.lineJoin = "round";
            ctx.stroke();
            lastX = pos.x;
            lastY = pos.y;
        }

        function stopDraw() {
            drawing = false;
            // Save to hidden field
            const hidden = document.getElementById("signature_data");
            if (hidden) hidden.value = canvas.toDataURL("image/png");
        }

        canvas.addEventListener("mousedown", startDraw);
        canvas.addEventListener("mousemove", draw);
        canvas.addEventListener("mouseup", stopDraw);
        canvas.addEventListener("mouseout", stopDraw);
        canvas.addEventListener("touchstart", startDraw, { passive: false });
        canvas.addEventListener("touchmove", draw, { passive: false });
        canvas.addEventListener("touchend", stopDraw);

        // Clear button
        const clearBtn = document.getElementById("clearSignature");
        if (clearBtn) {
            clearBtn.addEventListener("click", function () {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                const hidden = document.getElementById("signature_data");
                if (hidden) hidden.value = "";
            });
        }

        // Set canvas size
        function resizeCanvas() {
            const rect = canvas.getBoundingClientRect();
            const ratio = window.devicePixelRatio || 1;
            canvas.width = rect.width * ratio;
            canvas.height = rect.height * ratio;
            ctx.scale(ratio, ratio);
        }
        resizeCanvas();
        window.addEventListener("resize", resizeCanvas);
    }

    // ── GPS location capture for POD ──
    const gpsBtn = document.getElementById("captureGPS");
    if (gpsBtn) {
        gpsBtn.addEventListener("click", function () {
            if (!navigator.geolocation) {
                alert("Geolocation is not supported by this device.");
                return;
            }
            gpsBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Getting location...';
            navigator.geolocation.getCurrentPosition(
                function (pos) {
                    const latField = document.getElementById("gps_latitude");
                    const lngField = document.getElementById("gps_longitude");
                    if (latField) latField.value = pos.coords.latitude;
                    if (lngField) lngField.value = pos.coords.longitude;
                    gpsBtn.innerHTML = '<i class="bi bi-geo-alt-fill"></i> Location captured';
                    gpsBtn.classList.remove("btn-outline-secondary");
                    gpsBtn.classList.add("btn-success");
                },
                function () {
                    alert("Could not get GPS location. You can continue without it.");
                    gpsBtn.innerHTML = '<i class="bi bi-geo-alt"></i> GPS unavailable';
                },
                { enableHighAccuracy: true, timeout: 10000 }
            );
        });
    }

    // ── Quote calculator live preview (if on calculator page) ──
    const calcForm = document.getElementById("quoteCalculatorForm");
    if (calcForm) {
        calcForm.addEventListener("submit", function () {
            // Let the form submit normally to calculate on the server
        });
    }

    // ── Current time for delivery time field ──
    const timeField = document.getElementById("delivery_time");
    if (timeField && !timeField.value) {
        const now = new Date();
        const h = String(now.getHours()).padStart(2, "0");
        const m = String(now.getMinutes()).padStart(2, "0");
        timeField.value = h + ":" + m;
    }
})();
