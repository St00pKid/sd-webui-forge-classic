(function () {
    "use strict";

    var listenerAttached = false;

    function attachListener() {
        if (listenerAttached) return;
        listenerAttached = true;

        document.addEventListener("click", function (e) {
            // Copy triggers button
            var copyBtn = e.target.closest("#lm_copy_triggers_btn");
            if (copyBtn) {
                var ta = gradioApp().querySelector("#lm-triggers-input textarea");
                if (ta && ta.value) {
                    navigator.clipboard.writeText(ta.value);
                    var orig = copyBtn.textContent;
                    copyBtn.textContent = "Copied!";
                    setTimeout(function () { copyBtn.textContent = orig; }, 1500);
                }
                return;
            }

            // Card click
            var card = e.target.closest(".lm-card[data-lora-name]");
            if (!card) return;

            var name = card.getAttribute("data-lora-name");
            var hiddenBox = gradioApp().querySelector("#lm_selected_name textarea");
            if (!hiddenBox) return;

            hiddenBox.value = name;
            hiddenBox.dispatchEvent(new Event("input", { bubbles: true }));

            setTimeout(function () {
                var bridgeBtn = gradioApp().querySelector("#lm_js_bridge_btn");
                if (bridgeBtn) bridgeBtn.click();
            }, 50);
        });
    }

    onUiUpdate(function () {
        attachListener();
    });
})();
