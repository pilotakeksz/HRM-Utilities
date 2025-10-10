// Minimal embed builder logic with JSON import and JSON display overlay.
(function(){
  const qs = id=>document.getElementById(id);
  function uuid(){ return crypto?.randomUUID ? crypto.randomUUID().slice(0,8) : Math.random().toString(36).slice(2,10) }

  const State = { sessions: [], idx: 0 };
  function newSession(){ return { title:"", description:"", color:"", image_url:"", thumbnail_url:"", footer:"", footer_icon:"", fields:[], buttons:[], selects:[], plain_message:"" } }
  function current(){ return State.sessions[State.idx] }

  function renderSessionInfo(){
    const info = qs("session-info");
    if(info) info.textContent = `Embed ${State.idx+1} / ${State.sessions.length}`;
    const s = current();
    if(qs("title")) qs("title").value = s.title;
    if(qs("description")) qs("description").value = s.description;
    if(qs("color")) qs("color").value = s.color;
    // sync color picker input (expects hex, store without #)
    const cp = qs("color-picker");
    try {
      const hex = (() => {
        if(!s.color) return "#2f3136";
        const c = String(s.color).replace("#","").slice(0,6);
        return `#${c.padStart(6,"0")}`;
      })();
      if(cp) cp.value = hex;
    } catch(e){ if(cp) cp.value = "#2f3136" }
    if(qs("image_url")) qs("image_url").value = s.image_url;
    if(qs("thumbnail_url")) qs("thumbnail_url").value = s.thumbnail_url;
    if(qs("footer")) qs("footer").value = s.footer;
    if(qs("footer_icon")) qs("footer_icon").value = s.footer_icon;
    if(qs("plain_message")) qs("plain_message").value = s.plain_message;
    renderFields(); renderButtons(); updatePreview(); renderCarousel();
  }

  function renderCarousel(){
    const c = qs("embed-carousel");
    if(!c) return;
    c.innerHTML = "";
    State.sessions.forEach((s, i)=>{
      const dot = document.createElement("div");
      dot.className = "dot" + (i === State.idx ? " active" : "");
      dot.title = `Embed ${i+1}`;
      dot.onclick = ()=>{ State.idx = i; renderSessionInfo(); };
      c.append(dot);
    });
  }

  function renderFields(){
    const list = qs("fields-list"); if(!list) return;
    list.innerHTML = "";
    current().fields.forEach((f,i)=>{
      const row = document.createElement("div"); row.className="field-entry";
      const n = document.createElement("input"); n.placeholder="Name"; n.value=f.name;
      const v = document.createElement("input"); v.placeholder="Value"; v.value=f.value;
      const inl = document.createElement("input"); inl.placeholder="inline?"; inl.value = f.inline ? "true":"false"; inl.className="small";
      const trash = document.createElement("button"); trash.className="trash-btn"; trash.innerHTML="🗑"; trash.title="Delete field";
      n.onchange = ()=>{ current().fields[i].name=n.value; updatePreview() }
      v.onchange = ()=>{ current().fields[i].value=v.value; updatePreview() }
      inl.onchange = ()=>{ current().fields[i].inline = inl.value.toLowerCase()==="true"; updatePreview() }
      trash.onclick = ()=>{ current().fields.splice(i,1); renderFields(); updatePreview() }
      row.append(n,v,inl,trash); list.append(row);
    })
  }

  function renderButtons(){
    const list = qs("link-buttons"); if(!list) return;
    list.innerHTML = "";
    current().buttons.forEach((b,i)=>{
      const row = document.createElement("div"); row.className="link-entry";
      const type = document.createElement("select"); type.innerHTML = `<option value="link">Link</option><option value="send_embed">SendEmbed</option>`; type.value = b.type||"link";
      const label = document.createElement("input"); label.placeholder="Label"; label.value=b.label;
      const url = document.createElement("input"); url.placeholder="URL (for Link)"; url.value=b.url;
      const icon = document.createElement("input"); icon.placeholder="Icon URL (optional)"; icon.value=b.icon; icon.className="small";
      const target = document.createElement("input"); target.placeholder="Target key (for SendEmbed)"; target.value=b.target||"";
      const ephBoxLabel = document.createElement("label"); ephBoxLabel.className="checkbox";
      const eph = document.createElement("input"); eph.type="checkbox"; eph.checked = !!b.ephemeral; ephBoxLabel.append(eph, document.createTextNode("Ephemeral"));
      const trash = document.createElement("button"); trash.className="trash-btn"; trash.innerHTML="🗑"; trash.title="Delete button";

      type.onchange = ()=>{ current().buttons[i].type = type.value; renderButtons(); updatePreview() }
      label.onchange = ()=>{ current().buttons[i].label = label.value; updatePreview() }
      url.onchange = ()=>{ current().buttons[i].url = url.value; updatePreview() }
      icon.onchange = ()=>{ current().buttons[i].icon = icon.value; updatePreview() }
      target.onchange = ()=>{ current().buttons[i].target = target.value; updatePreview() }
      eph.onchange = ()=>{ current().buttons[i].ephemeral = eph.checked; updatePreview() }
      trash.onclick = ()=>{ current().buttons.splice(i,1); renderButtons(); updatePreview() }

      // hide fields depending on type
      if (type.value === "link") {
        row.append(type,label,url,icon,trash);
      } else {
        row.append(type,label,target,ephBoxLabel,icon,trash);
      }
      list.append(row);
    })
  }

  function renderSelects(){
    const list = qs("select-menus"); if(!list) return;
    list.innerHTML = "";
    const storedKeys = typeof getStoredKeys === "function" ? getStoredKeys() : [];

    current().selects.forEach((s, si)=>{
      const container = document.createElement("div");
      container.className = "select-builder";

      // header row: placeholder + name + icon + helpers (with visible labels)
      const header = document.createElement("div"); header.className = "select-builder-header";

      const phField = document.createElement("div"); phField.className="field";
      const phLabel = document.createElement("label"); phLabel.className="field-label"; phLabel.textContent = "Placeholder";
      const ph = document.createElement("input"); ph.className="input"; ph.placeholder="Choose an action"; ph.value = s.placeholder||"";
      phField.append(phLabel, ph);

      const nameField = document.createElement("div"); nameField.className="field";
      const nameLabel = document.createElement("label"); nameLabel.className="field-label"; nameLabel.textContent = "Name (internal id)";
      const nameInput = document.createElement("input"); nameInput.className="input"; nameInput.placeholder="select_name"; nameInput.value = s.name||"";
      nameField.append(nameLabel, nameInput);

      const iconField = document.createElement("div"); iconField.className="field";
      const iconLabel = document.createElement("label"); iconLabel.className="field-label"; iconLabel.textContent = "Icon (emoji or URL)";
      const iconInput = document.createElement("input"); iconInput.className="input"; iconInput.placeholder="🛠 or https://..."; iconInput.value = s.icon||"";
      iconField.append(iconLabel, iconInput);

      const storedSel = document.createElement("select"); storedSel.className="input stored-select";
      const opt0 = document.createElement("option"); opt0.value=""; opt0.textContent="Insert stored key…"; storedSel.appendChild(opt0);
      storedKeys.forEach(k=>{ const o=document.createElement("option"); o.value = k.replace(/^embed_/,""); o.textContent = o.value; storedSel.appendChild(o) });
      const insertStoredBtn = document.createElement("button"); insertStoredBtn.className="btn"; insertStoredBtn.textContent="Insert stored";
      const importButtonsBtn = document.createElement("button"); importButtonsBtn.className="btn"; importButtonsBtn.textContent="Use buttons";
      const addJsonBtn = document.createElement("button"); addJsonBtn.className="btn"; addJsonBtn.textContent="Add JSON option";

      header.append(phField, nameField, iconField, storedSel, insertStoredBtn, importButtonsBtn, addJsonBtn);
      container.appendChild(header);

      // options list (structured rows)
      const optsWrap = document.createElement("div"); optsWrap.className = "select-options-wrap";
      (s.options || []).forEach((opt, oi)=> {
        optsWrap.appendChild(makeOptionRow(si, oi, opt.label||"", opt.value||"", opt.description||"", opt.icon||""));
      });
      container.appendChild(optsWrap);

      // controls: add new option + delete select
      const ctrls = document.createElement("div"); ctrls.className = "select-builder-controls";
      const addOptBtn = document.createElement("button"); addOptBtn.className="btn"; addOptBtn.textContent = "Add option";
      const delSelBtn = document.createElement("button"); delSelBtn.className="trash-btn"; delSelBtn.textContent="🗑 Delete select";
      ctrls.append(addOptBtn, delSelBtn);
      container.appendChild(ctrls);

      // wire header interactions
      ph.onchange = ()=>{ current().selects[si].placeholder = ph.value; updatePreview(); }
      nameInput.onchange = ()=>{ current().selects[si].name = nameInput.value; updatePreview(); }
      iconInput.onchange = ()=>{ current().selects[si].icon = iconInput.value; updatePreview(); }

      addOptBtn.onclick = ()=>{
        const idx = (current().selects[si].options||[]).length;
        const row = makeOptionRow(si, idx, "Label","value","", "");
        optsWrap.appendChild(row);
        syncOptionsFromDOM(si, optsWrap);
        updatePreview();
      };
      delSelBtn.onclick = ()=>{
        if(!confirm("Delete this select?")) return;
        current().selects.splice(si,1);
        renderSelects();
        updatePreview();
      };

      insertStoredBtn.onclick = ()=>{
        const key = storedSel.value;
        if(!key) return alert("Choose a stored key");
        const line = { label: key, value: `send:${key}`, description: `Send stored ${key}` };
        (current().selects[si].options = current().selects[si].options||[]).push(line);
        optsWrap.appendChild(makeOptionRow(si, current().selects[si].options.length-1, line.label, line.value, line.description, ""));
        updatePreview();
      };

      importButtonsBtn.onclick = ()=>{
        const btns = current().buttons || [];
        if(!btns.length) return alert("No buttons to import");
        btns.forEach(b=>{
          if(b.type === "link" && b.url){
            (current().selects[si].options = current().selects[si].options||[]).push({ label: b.label||b.url, value:`link:${b.url}`, description:"Link", icon: b.icon||"" });
          } else if(b.type === "send_embed"){
            (current().selects[si].options = current().selects[si].options||[]).push({ label: b.label||b.target, value:`send:${b.target||""}${b.ephemeral?":e":""}`, description:"Send saved embed", icon: b.icon||"" });
          }
        });
        optsWrap.innerHTML = "";
        (current().selects[si].options||[]).forEach((opt, oi)=> optsWrap.appendChild(makeOptionRow(si, oi, opt.label, opt.value, opt.description, opt.icon)));
        updatePreview();
      };

      addJsonBtn.onclick = ()=>{
        openJsonOptionModal((jsonText)=>{
          const b64 = btoa(unescape(encodeURIComponent(jsonText)));
          const label = "Custom JSON";
          const value = `send_json:${b64}`;
          (current().selects[si].options = current().selects[si].options||[]).push({ label, value, description:"Send custom JSON", icon: "" });
          optsWrap.appendChild(makeOptionRow(si, (current().selects[si].options.length-1), label, value, "Send custom JSON", ""));
          updatePreview();
        });
      };

      list.appendChild(container);
    });

    // small helpers -------------------------------------------------------
    function makeOptionRow(selectIndex, optIndex, labelV="", valueV="", descV="", iconV=""){
      const row = document.createElement("div"); row.className="select-option-row";

      const labelField = document.createElement("div"); labelField.className="field small";
      const labLabel = document.createElement("label"); labLabel.className="field-label"; labLabel.textContent = "Option label";
      const l = document.createElement("input"); l.className="input opt-label"; l.placeholder="Visible label"; l.value = labelV;
      labelField.append(labLabel, l);

      const valueField = document.createElement("div"); valueField.className="field wide";
      const valLabel = document.createElement("label"); valLabel.className="field-label"; valLabel.textContent = "Value (send:key or link:url)";
      const v = document.createElement("input"); v.className="input opt-value"; v.placeholder="Value (e.g. send:key or link:https://)"; v.value = valueV;
      valueField.append(valLabel, v);

      const descField = document.createElement("div"); descField.className="field medium";
      const descLabel = document.createElement("label"); descLabel.className="field-label"; descLabel.textContent = "Description (optional)";
      const d = document.createElement("input"); d.className="input opt-desc"; d.placeholder="Short description"; d.value = descV;
      descField.append(descLabel, d);

      const iconField = document.createElement("div"); iconField.className="field tiny";
      const iconLabel = document.createElement("label"); iconLabel.className="field-label"; iconLabel.textContent = "Icon";
      const ic = document.createElement("input"); ic.className="input opt-icon"; ic.placeholder="Emoji or URL"; ic.value = iconV;
      iconField.append(iconLabel, ic);

      const up = document.createElement("button"); up.className="icon-btn"; up.textContent="↑";
      const down = document.createElement("button"); down.className="icon-btn"; down.textContent="↓";
      const del = document.createElement("button"); del.className="trash-btn"; del.textContent="🗑";

      row.append(labelField, valueField, descField, iconField, up, down, del);

      function syncAll(){
        syncOptionsFromDOM(selectIndex, row.parentElement);
        updatePreview();
      }
      l.onchange = syncAll; v.onchange = syncAll; d.onchange = syncAll; ic.onchange = syncAll;

      up.onclick = ()=>{
        const parent = row.parentElement;
        const prev = row.previousElementSibling;
        if(prev) parent.insertBefore(row, prev);
        syncAll();
      };
      down.onclick = ()=>{
        const parent = row.parentElement;
        const next = row.nextElementSibling;
        if(next) parent.insertBefore(next, row);
        syncAll();
      };
      del.onclick = ()=>{
        row.remove();
        syncAll();
      };
      return row;
    }

    function syncOptionsFromDOM(selectIndex, optsContainer){
      const rows = Array.from(optsContainer.querySelectorAll(".select-option-row"));
      const arr = rows.map(r=>{
        return {
          label: r.querySelector(".opt-label").value || "",
          value: r.querySelector(".opt-value").value || "",
          description: r.querySelector(".opt-desc").value || "",
          icon: r.querySelector(".opt-icon").value || ""
        };
      });
      current().selects[selectIndex].options = arr;
    }
  }

  function updatePreview(){
    const preview = qs("preview-area"); if(!preview) return;
    preview.innerHTML = "";
    const s = current();

    const card = document.createElement("div");
    card.className = "preview-card";

    const stripe = document.createElement("div");
    stripe.className = "stripe";
    if (s.color) stripe.style.background = `#${String(s.color).replace("#","").padStart(6,"0")}`;
    else stripe.style.background = "#2f3136";
    card.appendChild(stripe);

    const content = document.createElement("div");
    content.className = "preview-content";

    // header
    const header = document.createElement("div");
    header.className = "preview-header";
    const headerLeft = document.createElement("div");
    headerLeft.className = "preview-header-left";
    const title = document.createElement("div");
    title.className = "preview-title";
    title.textContent = s.title || "(no title)";
    const desc = document.createElement("div");
    desc.className = "preview-desc";
    desc.textContent = s.description || "";
    headerLeft.appendChild(title);
    headerLeft.appendChild(desc);
    header.appendChild(headerLeft);

    // thumbnail (absolute top-right inside header)
    if (s.thumbnail_url) {
      const th = document.createElement("img");
      th.className = "preview-thumbnail";
      th.src = s.thumbnail_url;
      header.appendChild(th);
    }

    // footer/icon on header right (if present)
    if (s.footer_icon && !s.thumbnail_url) {
      const ficon = document.createElement("img");
      ficon.className = "preview-footer-icon";
      ficon.src = s.footer_icon;
      header.appendChild(ficon);
    }

    content.appendChild(header);

    // main image
    if (s.image_url) {
      const img = document.createElement("img");
      img.className = "preview-image";
      img.src = s.image_url;
      content.appendChild(img);
    }

    // fields: support array form [name,value,inline] or object {name,value,inline}
    if (s.fields && s.fields.length) {
      const fieldsWrap = document.createElement("div");
      fieldsWrap.className = "preview-fields-wrap";

      s.fields.forEach(f=>{
        let name = "", value = "", inline = false;
        if (Array.isArray(f)) {
          name = f[0] || "";
          value = f[1] || "";
          inline = !!f[2];
        } else if (f && typeof f === "object") {
          name = f.name || "";
          value = f.value || f.val || f.inline === undefined ? (f.value || "") : (f.value || "");
          inline = !!f.inline;
        } else {
          // fallback: try to stringify
          name = "field";
          value = String(f);
        }

        const fb = document.createElement("div");
        fb.className = "preview-field" + (inline ? " inline" : "");
        const fn = document.createElement("div"); fn.className = "preview-field-name"; fn.textContent = name || "(no name)";
        const fv = document.createElement("div"); fv.className = "preview-field-value"; fv.textContent = value || "";
        fb.appendChild(fn);
        fb.appendChild(fv);
        fieldsWrap.appendChild(fb);
      });

      content.appendChild(fieldsWrap);
    }

    // buttons row
    if (s.buttons && s.buttons.length) {
      const row = document.createElement("div");
      row.className = "preview-buttons-row";
      s.buttons.forEach(b=>{
        const btn = document.createElement("button");
        btn.className = "preview-button";
        if (b.icon) {
          const bi = document.createElement("img");
          bi.className = "preview-button-icon";
          bi.src = b.icon;
          btn.appendChild(bi);
        }
        const span = document.createElement("span"); span.textContent = b.label || "button";
        btn.appendChild(span);
        // small external indicator for links
        if (b.type === "link" && b.url) {
          const ext = document.createElement("span");
          ext.className = "preview-button-ext";
          ext.textContent = "↗";
          btn.appendChild(ext);
          btn.onclick = ()=>window.open(b.url, "_blank");
        }
        row.appendChild(btn);
      });
      content.appendChild(row);
    }

    // select preview
    if (s.selects && s.selects.length){
      s.selects.forEach(sel=>{
        const wrap = document.createElement("div"); wrap.className="preview-select-wrap";
        const selEl = document.createElement("select"); selEl.className="preview-select";
        const phOpt = document.createElement("option"); phOpt.textContent = sel.placeholder || "Choose…"; phOpt.disabled = true; phOpt.selected = true;
        selEl.appendChild(phOpt);
        (sel.options||[]).forEach(o=>{
          const opt = document.createElement("option"); opt.value = o.value || ""; opt.textContent = o.label || o.value || "";
          selEl.appendChild(opt);
        });
        wrap.appendChild(selEl);
        // no functional onChange in preview
        preview.appendChild(wrap);
      })
    }

    // plain message
    if (s.plain_message) {
      const pm = document.createElement("div");
      pm.className = "preview-plain-message";
      pm.textContent = s.plain_message;
      content.appendChild(pm);
    }

    // footer row (icon + text)
    if (s.footer) {
      const footerRow = document.createElement("div");
      footerRow.className = "preview-footer-row";
      if (s.footer_icon) {
        const fi = document.createElement("img");
        fi.className = "preview-footer-icon-left";
        fi.src = s.footer_icon;
        footerRow.appendChild(fi);
      }
      const ft = document.createElement("div");
      ft.className = "preview-footer-text";
      ft.textContent = s.footer;
      footerRow.appendChild(ft);
      content.appendChild(footerRow);
    }

    card.appendChild(content);
    preview.appendChild(card);
  }

  // JSON payload builder
  function buildPayload(){
    return { embeds: State.sessions, plain_message: current().plain_message || "" };
  }

  // Import logic
  function openImportModal(){ const m = qs("import-modal"); if(m){ m.classList.remove("hidden"); m.setAttribute("aria-hidden","false"); } }
  function closeImportModal(){ const m = qs("import-modal"); if(m){ m.classList.add("hidden"); m.setAttribute("aria-hidden","true"); qs("import-text").value = ""; qs("import-status").textContent = ""; } }

  function importFromObject(obj){
    // Expect {embeds: [...] } or array
    let embeds = [];
    if(Array.isArray(obj)) embeds = obj;
    else if(obj && obj.embeds && Array.isArray(obj.embeds)) embeds = obj.embeds;
    else {
      alert("Invalid structure: expected an array of embeds or { embeds: [...] }");
      return;
    }
    // replace sessions
    State.sessions = embeds.map(e=>{
      // Normalize shape to fields/buttons arrays if necessary
      return {
        title: e.title || "",
        description: e.description || "",
        color: (typeof e.color === "number") ? e.color.toString(16).padStart(6,"0") : (e.color||""),
        image_url: e.image_url || e.image || "",
        thumbnail_url: e.thumbnail_url || e.thumbnail || "",
        footer: e.footer || "",
        footer_icon: e.footer_icon || "",
        fields: (e.fields || []).map(f=>{
          // support either [name,value,inline] or {name,value,inline}
          if(Array.isArray(f)) return { name: f[0]||"", value: f[1]||"", inline: !!f[2] };
          return { name: f.name||"", value: f.value||"", inline: !!f.inline };
        }),
        buttons: (e.buttons || []),
        selects: (e.selects || []),
        plain_message: e.plain_message || ""
      }
    });
    State.idx = 0;
    renderSessionInfo();
  }

  // wire UI
  function init(){
    State.sessions = [ newSession() ];
    bind();
    renderSessionInfo();
    renderStoredList();
    setupSaveLocalHook();
  }

  function bind(){
    const el = id => { const e = qs(id); return e || null; };

    const addBtn = el("add-embed"); if(addBtn) addBtn.onclick = ()=>{ State.sessions.push(newSession()); State.idx = State.sessions.length-1; renderSessionInfo() }
    const prevBtn = el("prev-embed"); if(prevBtn) prevBtn.onclick = ()=>{ if(State.idx>0) State.idx--; renderSessionInfo() }
    const nextBtn = el("next-embed"); if(nextBtn) nextBtn.onclick = ()=>{ if(State.idx < State.sessions.length-1) State.idx++; renderSessionInfo() }

    const title = el("title"); if(title) title.oninput = ()=>{ current().title = title.value; updatePreview() }
    const desc = el("description"); if(desc) desc.oninput = ()=>{ current().description = desc.value; updatePreview() }
    const color = el("color"); if(color) color.oninput = ()=>{ current().color = color.value.replace("#",""); updatePreview() }
    const colorPicker = el("color-picker");
    if(colorPicker) colorPicker.oninput = ()=>{
      const v = colorPicker.value.replace("#","");
      const txt = qs("color");
      if(txt) txt.value = v;
      current().color = v;
      updatePreview();
    }
    const image = el("image_url"); if(image) image.onchange = ()=>{ current().image_url = image.value; updatePreview() }
    const thumb = el("thumbnail_url"); if(thumb) thumb.onchange = ()=>{ current().thumbnail_url = thumb.value; updatePreview() }
    const footer = el("footer"); if(footer) footer.onchange = ()=>{ current().footer = footer.value; updatePreview() }
    const footer_icon = el("footer_icon"); if(footer_icon) footer_icon.onchange = ()=>{ current().footer_icon = footer_icon.value; updatePreview() }
    const plain = el("plain_message"); if(plain) plain.oninput = ()=>{ current().plain_message = plain.value; updatePreview() }

    const addField = el("add-embed"); if(addField) addField.onclick = ()=>{ current().fields.push({name:"",value:"",inline:false}); renderFields(); updatePreview() }
    const addLink = el("add-link"); if(addLink) addLink.onclick = ()=>{ current().buttons.push({type:"link",label:"",url:"",icon:"",target:"",ephemeral:false}); renderButtons(); updatePreview() }
    const addSelect = el("add-select"); if(addSelect) addSelect.onclick = ()=>{ current().selects.push({ placeholder:"", options:[] }); renderSelects(); updatePreview() }

    const exportBtn = el("export-json"); if(exportBtn) exportBtn.onclick = ()=>{ const payload = buildPayload(); const s = JSON.stringify(payload, null, 2); const blob = new Blob([s], {type:"application/json"}); const a=document.createElement("a"); a.href=URL.createObjectURL(blob); a.download="embed_export.json"; a.click(); }
    const copyBtn = el("copy-json"); if(copyBtn) copyBtn.onclick = ()=>{ openJsonDisplay(JSON.stringify(buildPayload(), null, 2)) }

    const importBtn = el("import-json"); if(importBtn) importBtn.onclick = ()=>{ openImportModal() }
    const uploadInput = el("upload-json-file"); if(uploadInput) uploadInput.onchange = async (ev)=>{
      const f = ev.target.files && ev.target.files[0];
      if(!f) return;
      try{
        const txt = await f.text();
        const obj = JSON.parse(txt);
        importFromObject(obj);
        closeImportModal();
        alert("Imported JSON file.");
      }catch(e){
        qs("import-status").textContent = "Failed to parse uploaded file: "+e;
      } finally {
        uploadInput.value = "";
      }
    }

    const importCancel = el("import-cancel"); if(importCancel) importCancel.onclick = ()=>closeImportModal();
    const importUploadBtn = el("import-upload-btn"); if(importUploadBtn) importUploadBtn.onclick = ()=>{ const up = qs("upload-json-file"); if(up) up.click(); }
    const importPasteBtn = el("import-paste-btn"); if(importPasteBtn) importPasteBtn.onclick = ()=>{
      const txt = qs("import-text").value.trim();
      if(!txt){ qs("import-status").textContent = "Paste JSON into the box first."; return; }
      try{
        const obj = JSON.parse(txt);
        importFromObject(obj);
        closeImportModal();
        alert("Imported JSON from paste.");
      }catch(e){
        qs("import-status").textContent = "Failed to parse JSON: "+e;
      }
    }

    const genBtn = el("generate-key"); if(genBtn) genBtn.onclick = ()=>{ const key = uuid(); const lk = qs("last-key"); if(lk){ lk.textContent = `Key: ${key}`; lk.dataset.key = key } }
    const saveBtn = el("save-local"); if(saveBtn) saveBtn.onclick = ()=>{ const key = (qs("last-key") && qs("last-key").dataset.key) || uuid(); const payload = { key, embeds: State.sessions, plain_message: current().plain_message }; localStorage.setItem(`embed_${key}`, JSON.stringify(payload)); const lk = qs("last-key"); if(lk) lk.textContent = `Saved key: ${key}` }

    // JSON display modal handlers
    const jsonClose = el("json-close"); if(jsonClose) jsonClose.onclick = ()=>{ closeJsonDisplay() }
    const jsonCopy = el("json-copy-btn"); if(jsonCopy) jsonCopy.onclick = ()=>{ const text = qs("json-code").textContent; navigator.clipboard.writeText(text).then(()=>{ alert("Copied to clipboard"); }) }
    const jsonDownload = el("json-download-btn"); if(jsonDownload) jsonDownload.onclick = ()=>{ const text = qs("json-code").textContent; const blob = new Blob([text], {type:"application/json"}); const a=document.createElement("a"); a.href=URL.createObjectURL(blob); a.download="embed_export.json"; a.click(); }

    // keyboard left/right to navigate carousel
    document.addEventListener("keydown", (ev)=>{
      if(ev.key === "ArrowLeft"){ if(State.idx>0){ State.idx--; renderSessionInfo(); } }
      if(ev.key === "ArrowRight"){ if(State.idx < State.sessions.length-1){ State.idx++; renderSessionInfo(); } }
    });
  }

  // --- stored list helpers ---
  function getStoredKeys(){
    return Object.keys(localStorage).filter(k=>k.startsWith("embed_")).sort();
  }

  function renderStoredList(){
    const container = qs("stored-list");
    if(!container) return;
    container.innerHTML = "";
    const keys = getStoredKeys();
    if(keys.length === 0){
      container.innerHTML = '<div class="stored-empty muted">No stored embeds</div>';
      return;
    }
    keys.forEach(key=>{
      try{
        const raw = localStorage.getItem(key);
        const obj = raw ? JSON.parse(raw) : null;
        const label = (obj && obj.key) ? obj.key : key.replace(/^embed_/,"");
        const item = document.createElement("div");
        item.className = "stored-item";
        item.innerHTML = `
          <div class="stored-left">
            <div class="stored-key">${label}</div>
            <div class="stored-meta muted">saved</div>
          </div>
          <div class="stored-actions">
            <button class="icon-btn copy-key" title="Copy key">📋</button>
            <button class="icon-btn view-json" title="View JSON">🗎</button>
            <button class="icon-btn download-json" title="Download JSON">⬇</button>
            <button class="icon-btn delete-json" title="Delete">🗑</button>
          </div>
        `;
        // wire buttons
        const copyKeyBtn = item.querySelector(".copy-key");
        const viewJsonBtn = item.querySelector(".view-json");
        const downloadBtn = item.querySelector(".download-json");
        const deleteBtn = item.querySelector(".delete-json");

        copyKeyBtn.onclick = ()=>{
          const k = (obj && obj.key) ? obj.key : label;
          navigator.clipboard.writeText(k).then(()=>{ alert("Copied key: "+k) });
        };
        viewJsonBtn.onclick = ()=>{
          // open JSON modal with pretty printed payload (if stored object contains embeds/ payload)
          const payload = obj && (obj.embeds || obj.payload || obj) ? (obj.payload || obj) : obj;
          openJsonDisplay(JSON.stringify(payload, null, 2));
        };
        downloadBtn.onclick = ()=>{
          const payload = obj && (obj.embeds || obj.payload || obj) ? (obj.payload || obj) : obj;
          const text = JSON.stringify(payload, null, 2);
          const blob = new Blob([text], {type:"application/json"});
          const a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = `${label || key}.json`;
          a.click();
        };
        deleteBtn.onclick = ()=>{
          if(!confirm("Delete stored embed '"+label+"'?")) return;
          localStorage.removeItem(key);
          renderStoredList();
        };

        container.appendChild(item);
      }catch(e){
        // skip broken entry
      }
    });
  }

  // override save-local to refresh stored list (hook existing save behavior)
  function setupSaveLocalHook(){
    const saveBtn = qs("save-local");
    if(!saveBtn) return;
    saveBtn.addEventListener("click", ()=>{
      // small delay to allow existing handler to set localStorage
      setTimeout(()=>{ renderStoredList() }, 150);
    });
  }

  // JSON display open/close (existing)
  function openJsonDisplay(jsonText){
    const m = qs("json-display"); if(!m) return;
    qs("json-code").textContent = jsonText;
    m.classList.remove("hidden"); m.setAttribute("aria-hidden","false");
  }
  function closeJsonDisplay(){ const m = qs("json-display"); if(!m) return; m.classList.add("hidden"); m.setAttribute("aria-hidden","true"); qs("json-code").textContent = ""; }

  // ensure stored list refresh after init
  function init(){
    State.sessions = [ newSession() ];
    bind();
    renderSessionInfo();
    renderStoredList();
    setupSaveLocalHook();
  }

  // ensure json modal close button hooked
  document.addEventListener("DOMContentLoaded", ()=>{
    const jsonClose = qs("json-close");
    if(jsonClose) jsonClose.onclick = ()=>{ closeJsonDisplay() };
  });

  init();
})();