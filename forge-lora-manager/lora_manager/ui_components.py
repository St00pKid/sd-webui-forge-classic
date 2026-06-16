import html
import re
import gradio as gr
from lora_manager import lora_data


def _preview_url(path: str) -> str:
    return f"/file={path}"


def _sanitize_html(text: str) -> str:
    text = re.sub(r'<(script|iframe|style|object|embed|form|meta|link)[\s>].*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'\s+on\w+\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]*)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'(href\s*=\s*["\']?\s*)javascript:', r'\1#', text, flags=re.IGNORECASE)
    return text


def _make_card_grid_html(loras: list[dict], selected_name: str = "") -> str:
    if not loras:
        return "<p style='padding:1em;color:var(--body-text-color-subdued)'>No LoRAs found. Check your models/Lora directory.</p>"

    cards = []
    for lora in loras:
        label = lora.get("display_name") or lora["name"]
        name_attr = html.escape(lora["name"], quote=True)
        label_escaped = html.escape(label)
        selected_class = " selected" if lora["name"] == selected_name else ""

        if lora["preview_path"]:
            img_html = f'<img class="lm-card-preview" src="{_preview_url(lora["preview_path"])}" alt="" loading="lazy">'
        else:
            img_html = '<div class="lm-card-no-preview">No preview</div>'

        cards.append(
            f'<div class="lm-card{selected_class}" data-lora-name="{name_attr}">'
            f'{img_html}'
            f'<div class="lm-card-label" title="{label_escaped}">{label_escaped}</div>'
            f'</div>'
        )

    return f'<div id="lm-card-grid-inner">{"".join(cards)}</div>'


def _filter_loras(loras: list[dict], query: str) -> list[dict]:
    query = query.strip().lower()
    if not query:
        return loras
    terms = query.split()
    def matches(lora):
        haystack = (
            f"{lora['name']} {lora.get('display_name', '')} "
            f"{lora['trigger_words']} {lora['description']}"
        ).lower()
        return all(t in haystack for t in terms)
    return [l for l in loras if matches(l)]


def _sort_loras(loras: list[dict], sort_by: str) -> list[dict]:
    if sort_by == "Name A-Z":
        return sorted(loras, key=lambda x: (x.get("display_name") or x["name"]).lower())
    elif sort_by == "Name Z-A":
        return sorted(loras, key=lambda x: (x.get("display_name") or x["name"]).lower(), reverse=True)
    elif sort_by == "Date Modified":
        return sorted(loras, key=lambda x: x["mtime"], reverse=True)
    elif sort_by == "Has Preview First":
        return sorted(loras, key=lambda x: (0 if x["preview_path"] else 1, (x.get("display_name") or x["name"]).lower()))
    return loras


def _u(value, interactive=True):
    """Shorthand for gr.update with an optional interactive flag."""
    return gr.update(value=value, interactive=interactive)


def _empty_detail_returns():
    """Returns for all 9 detail outputs when nothing is selected."""
    return (
        _u("", interactive=False),  # detail_filename (read-only)
        _u("", interactive=True),   # detail_display_name
        None,                        # detail_preview (gr.Image: None = blank)
        _u("", interactive=True),   # detail_desc
        _u("", interactive=True),   # detail_triggers
        _u("", interactive=True),   # detail_weight
        _u("", interactive=True),   # detail_notes
        _u("", interactive=False),  # detail_sd_ver (read-only)
        "",                          # save_status
    )


def _html_to_text(raw: str) -> str:
    """Convert HTML description to readable plain text with proper line breaks."""
    # Block-level closers → double newline
    text = re.sub(r'</p>', '\n\n', raw, flags=re.IGNORECASE)
    text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</li>', '\n', text, flags=re.IGNORECASE)
    # Explicit line breaks
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode common HTML entities
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>') \
               .replace('&nbsp;', ' ').replace('&quot;', '"').replace('&#39;', "'")
    # Collapse more than two consecutive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _lora_detail_returns(lora: dict):
    """Returns for all 9 detail outputs when a LoRA is selected."""
    raw_desc = lora["description"]
    desc_plain = _html_to_text(raw_desc) if raw_desc else ""

    return (
        _u(lora["name"], interactive=False),                     # detail_filename
        _u(lora.get("display_name") or "", interactive=True),   # detail_display_name
        lora["preview_path"] or None,                            # detail_preview
        _u(desc_plain, interactive=True),                        # detail_desc
        _u(lora["trigger_words"], interactive=True),             # detail_triggers
        _u(lora["preferred_weight"], interactive=True),          # detail_weight
        _u(lora["notes"], interactive=True),                     # detail_notes
        _u(lora["sd_version"] or "Unknown", interactive=False),  # detail_sd_ver
        "",                                                       # save_status
    )


def build_lora_manager_tab() -> gr.Blocks:
    with gr.Blocks(analytics_enabled=False) as tab:
        all_loras_state     = gr.State([])
        selected_name_state = gr.State("")
        selected_file_state = gr.State("")

        # ── Top bar ──────────────────────────────────────────────────────────
        with gr.Row(elem_id="lm-top-bar"):
            search_box = gr.Textbox(
                placeholder="Search by name, trigger words…",
                show_label=False, scale=3, container=False,
            )
            sort_dropdown = gr.Dropdown(
                choices=["Name A-Z", "Name Z-A", "Date Modified", "Has Preview First"],
                value="Name A-Z", label="Sort", min_width=160, scale=0,
            )
            refresh_btn = gr.Button("Refresh", scale=0, min_width=90)

        # ── Main area ─────────────────────────────────────────────────────────
        with gr.Row(elem_id="lm-main-row"):
            with gr.Column(scale=3, elem_id="lm-grid-col"):
                grid_html = gr.HTML(
                    elem_id="lm_card_grid",
                    value="<p style='padding:1em'>Loading…</p>",
                )

            with gr.Column(scale=2, elem_id="lm-detail-col"):
                detail_filename     = gr.Textbox(label="Filename", interactive=False)
                detail_display_name = gr.Textbox(label="Display Name", interactive=True, placeholder="Leave blank to use filename")
                detail_preview      = gr.Image(show_label=False, interactive=False, height=320, elem_id="lm-detail-preview")
                detail_desc         = gr.Textbox(label="Description", interactive=True, lines=7)
                with gr.Row():
                    detail_triggers = gr.Textbox(label="Trigger Words", interactive=True, lines=2, scale=1, elem_id="lm-triggers-input")
                    copy_triggers_btn = gr.Button("Copy", scale=0, min_width=70, elem_id="lm_copy_triggers_btn")
                detail_weight   = gr.Textbox(label="Preferred Weight", interactive=True, placeholder="e.g. 0.8")
                detail_notes    = gr.Textbox(label="Notes", interactive=True, lines=3)
                detail_sd_ver   = gr.Textbox(label="SD Version", interactive=False)

                with gr.Row():
                    save_btn    = gr.Button("Save", variant="primary", scale=1)
                    save_status = gr.HTML(elem_id="lm-save-status")

                gr.HTML("<hr style='margin:8px 0;border-color:var(--block-border-color)'>")
                with gr.Row():
                    civitai_fetch_btn     = gr.Button("Fetch from Civitai", scale=1)
                    overwrite_preview_chk = gr.Checkbox(label="Overwrite preview", value=False, scale=0, min_width=150)

        # ── Hidden JS bridge ──────────────────────────────────────────────────
        selected_name_box = gr.Textbox(visible=False, elem_id="lm_selected_name")
        js_bridge_btn     = gr.Button(visible=False, elem_id="lm_js_bridge_btn")

        # ── Shared output list (order must match _empty_detail_returns / _lora_detail_returns) ──
        _detail_outputs = [
            detail_filename, detail_display_name, detail_preview,
            detail_desc, detail_triggers, detail_weight,
            detail_notes, detail_sd_ver, save_status,
        ]

        # ── Event handlers ────────────────────────────────────────────────────
        def on_load(sort_by):
            loras = _sort_loras(lora_data.list_loras(), sort_by)
            return _make_card_grid_html(loras), loras

        def on_refresh(sort_by, query):
            lora_data.refresh_network_list()
            all_loras = lora_data.list_loras()
            visible = _sort_loras(_filter_loras(all_loras, query), sort_by)
            return (
                _make_card_grid_html(visible),  # grid_html
                all_loras,                       # all_loras_state
                "",                              # selected_name_state
                "",                              # selected_file_state
                *_empty_detail_returns(),        # 9 detail outputs
            )

        def on_search_or_sort(query, sort_by, all_loras, selected_name):
            visible = _sort_loras(_filter_loras(all_loras, query), sort_by)
            return _make_card_grid_html(visible, selected_name)

        def on_card_selected(raw_name, all_loras, query):
            name = raw_name.strip()
            if not name:
                return ("", "", *_empty_detail_returns(), _make_card_grid_html(all_loras))
            lora = lora_data.get_lora_detail(name)
            if lora is None:
                return ("", "", *_empty_detail_returns(), _make_card_grid_html(all_loras))
            visible = _sort_loras(_filter_loras(all_loras, query), "Name A-Z") if query else all_loras
            grid = _make_card_grid_html(visible, selected_name=name)
            return (name, lora["filename"], *_lora_detail_returns(lora), grid)

        def on_save(filename, display_name, desc, triggers, weight, notes,
                    all_loras, selected_name, query, sort_by):
            if not filename:
                return (
                    "<span style='color:var(--error-border-color)'>No LoRA selected.</span>",
                    _make_card_grid_html(all_loras, selected_name),
                )
            try:
                lora_data.save_user_metadata(filename, {
                    "display_name": display_name.strip() or None,
                    "description":  desc,
                    "activation text": triggers,
                    "preferred weight": weight.strip() or None,
                    "notes": notes,
                })
                lora_data.refresh_network_list()
                all_loras_new = lora_data.list_loras()
                visible = _sort_loras(_filter_loras(all_loras_new, query), sort_by)
                return (
                    "<span style='color:var(--color-accent)'>Saved.</span>",
                    _make_card_grid_html(visible, selected_name),
                )
            except Exception as e:
                return (
                    f"<span style='color:var(--error-border-color)'>Error: {html.escape(str(e))}</span>",
                    _make_card_grid_html(all_loras, selected_name),
                )

        # ── Event wiring ──────────────────────────────────────────────────────
        tab.load(
            fn=on_load,
            inputs=[sort_dropdown],
            outputs=[grid_html, all_loras_state],
        )

        # on_refresh returns: grid_html, all_loras_state, selected_name_state,
        #                     selected_file_state, + 9 detail outputs = 13 total
        refresh_btn.click(
            fn=on_refresh,
            inputs=[sort_dropdown, search_box],
            outputs=[grid_html, all_loras_state, selected_name_state, selected_file_state,
                     *_detail_outputs],
        )

        search_box.change(
            fn=on_search_or_sort,
            inputs=[search_box, sort_dropdown, all_loras_state, selected_name_state],
            outputs=[grid_html],
        )

        sort_dropdown.change(
            fn=on_search_or_sort,
            inputs=[search_box, sort_dropdown, all_loras_state, selected_name_state],
            outputs=[grid_html],
        )

        # on_card_selected returns: selected_name_state, selected_file_state,
        #                           + 9 detail outputs, + grid_html = 12 total
        js_bridge_btn.click(
            fn=on_card_selected,
            inputs=[selected_name_box, all_loras_state, search_box],
            outputs=[selected_name_state, selected_file_state, *_detail_outputs, grid_html],
        )

        save_btn.click(
            fn=on_save,
            inputs=[selected_file_state, detail_display_name, detail_desc,
                    detail_triggers, detail_weight, detail_notes,
                    all_loras_state, selected_name_state, search_box, sort_dropdown],
            outputs=[save_status, grid_html],
        )

        def on_civitai_fetch(filename, overwrite):
            import os
            if not filename:
                return "<span style='color:var(--error-border-color)'>Select a LoRA first.</span>", "", "", None
            name = os.path.splitext(os.path.basename(filename))[0]
            from lora_manager import civitai_client
            try:
                success, msg, data = civitai_client.fetch_and_populate(filename, name, overwrite)
            except Exception as e:
                return f"<span style='color:var(--error-border-color)'>Error: {html.escape(str(e))}</span>", "", "", None

            colour = "var(--color-accent)" if success else "var(--error-border-color)"
            status_html = f"<span style='color:{colour}'>{html.escape(msg)}</span>"

            if not success:
                return status_html, "", "", None

            desc_plain = _html_to_text(data["description"]) if data.get("description") else ""
            return (
                status_html,
                desc_plain,
                data.get("trigger_words", ""),
                data.get("preview_path") or None,
            )

        # outputs: save_status (reused for fetch status), detail_desc, detail_triggers, detail_preview
        civitai_fetch_btn.click(
            fn=on_civitai_fetch,
            inputs=[selected_file_state, overwrite_preview_chk],
            outputs=[save_status, detail_desc, detail_triggers, detail_preview],
        )

    return tab
