(function(){
  const qs = id=>document.getElementById(id);
  function uuid(){ return crypto?.randomUUID ? crypto.randomUUID().slice(0,8) : Math.random().toString(36).slice(2,10) }

  const State = { sessions: [], idx: 0 };
  function newSession(){ return {
    title:"", description:"", color:"", image_url:"", thumbnail_url:"", footer:"", footer_icon:"",
    fields:[], buttons:[], plain_message:""
  } }

  function current(){ return State.sessions[State.idx] }

  function renderSessionInfo(){
    const info = qs("session-info");
    if(info) info.textContent = `Embed ${State.idx+1} / ${State.sessions.length}`;
    const s = current();
    if(qs("title")) qs("title").value = s.title;
    if(qs("description")) qs("description").value = s.description;
    if(qs("color")) qs("color").value = s.color;
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

  function updatePreview(){
    const preview = qs("preview-area"); if(!preview) return;
    preview.innerHTML = "";
    const s = current();

    const card = document.createElement("div"); card.className="preview-card";
    // color stripe
    const stripe = document.createElement("div"); stripe.style.width="8px"; stripe.style.height="100%";
    stripe.style.background = s.color ? `#${String(s.color).padStart(6,'0')}` : "#2f3136";
    stripe.style.borderRadius = "6px 0 0 6px"; stripe.style.float="left"; stripe.style.marginRight = "12px";
    card.append(stripe);

    const inner = document.createElement("div"); inner.style.paddingLeft = "12px";
    const header = document.createElement("div"); header.style.display="flex"; header.style.alignItems="center"; header.style.justifyContent="space-between";
    const left = document.createElement("div");
    const title = document.createElement("div"); title.style.color="#d0b47b"; title.style.fontWeight="700"; title.textContent = s.title || "(no title)";
    const desc = document.createElement("div"); desc.textContent = s.description || "";
    left.append(title, desc);
    const right = document.createElement("div");
    if(s.footer_icon){ const ficon = document.createElement("img"); ficon.src = s.footer_icon; ficon.style.width="40px"; ficon.style.height="40px"; ficon.style.borderRadius="6px"; ficon.style.objectFit="cover"; right.append(ficon) }
    header.append(left, right);

    inner.append(header);

    if(s.thumbnail_url){
      const th = document.createElement("img"); th.src = s.thumbnail_url; th.style.width="80px"; th.style.float="right"; th.style.marginLeft="10px"; inner.append(th);
    }
    if(s.image_url){
      const img = document.createElement("img"); img.src = s.image_url; img.style.maxWidth="100%"; img.style.marginTop="8px"; inner.append(img);
    }

    // fields in grid
    if(s.fields && s.fields.length){
      const grid = document.createElement("div"); grid.style.display="grid"; grid.style.gridTemplateColumns = "repeat(auto-fit,minmax(180px,1fr))"; grid.style.gap = "8px"; grid.style.marginTop = "8px";
      s.fields.forEach(f=>{
        const fb = document.createElement("div"); fb.style.padding = "8px"; fb.style.background = "rgba(255,255,255,0.02)"; fb.style.borderRadius = "6px";
        const fn = document.createElement("div"); fn.style.fontWeight = "600"; fn.textContent = f.name || "(no name)";
        const fv = document.createElement("div"); fv.style.marginTop="6px"; fv.textContent = f.value || "";
        fb.append(fn, fv);
        grid.append(fb);
      });
      inner.append(grid);
    }

    // buttons with optional icons
    if(s.buttons && s.buttons.length){
      const row = document.createElement("div"); row.style.marginTop="12px";
      s.buttons.forEach(b=>{
        const btn = document.createElement("button"); btn.className="btn"; btn.style.display="inline-flex"; btn.style.alignItems="center"; btn.style.gap="8px";
        if(b.icon){ const bi = document.createElement("img"); bi.src = b.icon; bi.style.width="18px"; bi.style.height="18px"; bi.style.objectFit="cover"; bi.style.borderRadius="4px"; btn.append(bi) }
        const span = document.createElement("span"); span.textContent = b.label || "button"; btn.append(span);
        if(b.type==="link" && b.url) btn.onclick = ()=>window.open(b.url, "_blank");
        row.append(btn);
      });
      inner.append(row);
    }

    if(s.plain_message){
      const pm = document.createElement("div"); pm.style.marginTop="12px"; pm.style.padding="8px"; pm.style.background="rgba(255,255,255,0.02)"; pm.style.borderRadius="6px"; pm.textContent = s.plain_message;
      inner.append(pm);
    }

    if(s.footer){
      const footer = document.createElement("div"); footer.style.marginTop="12px"; footer.style.fontSize="12px"; footer.style.color="#9aa3ad"; footer.textContent = s.footer;
      inner.append(footer);
    }

    card.append(inner);
    preview.append(card);
  }

  // wire UI
  function init(){
    State.sessions = [ newSession() ];
    bind();
    renderSessionInfo();
  }

  function bind(){
    const el = id => { const e = qs(id); return e || null; };

    const addBtn = el("add-embed"); if(addBtn) addBtn.onclick = ()=>{ State.sessions.push(newSession()); State.idx = State.sessions.length-1; renderSessionInfo() }
    const prevBtn = el("prev-embed"); if(prevBtn) prevBtn.onclick = ()=>{ if(State.idx>0) State.idx--; renderSessionInfo() }
    const nextBtn = el("next-embed"); if(nextBtn) nextBtn.onclick = ()=>{ if(State.idx < State.sessions.length-1) State.idx++; renderSessionInfo() }

    const title = el("title"); if(title) title.oninput = ()=>{ current().title = title.value; updatePreview() }
    const desc = el("description"); if(desc) desc.oninput = ()=>{ current().description = desc.value; updatePreview() }
    const color = el("color"); if(color) color.oninput = ()=>{ current().color = color.value.replace("#",""); updatePreview() }
    const image = el("image_url"); if(image) image.onchange = ()=>{ current().image_url = image.value; updatePreview() }
    const thumb = el("thumbnail_url"); if(thumb) thumb.onchange = ()=>{ current().thumbnail_url = thumb.value; updatePreview() }
    const footer = el("footer"); if(footer) footer.onchange = ()=>{ current().footer = footer.value; updatePreview() }
    const footer_icon = el("footer_icon"); if(footer_icon) footer_icon.onchange = ()=>{ current().footer_icon = footer_icon.value; updatePreview() }
    const plain = el("plain_message"); if(plain) plain.oninput = ()=>{ current().plain_message = plain.value; updatePreview() }

    const addField = el("add-field"); if(addField) addField.onclick = ()=>{ current().fields.push({name:"",value:"",inline:false}); renderFields(); updatePreview() }
    const addLink = el("add-link"); if(addLink) addLink.onclick = ()=>{ current().buttons.push({type:"link",label:"",url:"",icon:"",target:"",ephemeral:false}); renderButtons(); updatePreview() }

    const exportBtn = el("export-json"); if(exportBtn) exportBtn.onclick = ()=>{ const payload = { embeds: State.sessions, plain_message: current().plain_message, exported_at: new Date().toISOString() }; const s = JSON.stringify(payload, null, 2); const blob = new Blob([s], {type:"application/json"}); const a=document.createElement("a"); a.href=URL.createObjectURL(blob); a.download="embed_export.json"; a.click(); }
    const copyBtn = el("copy-json"); if(copyBtn) copyBtn.onclick = ()=>{ const payload = { embeds: State.sessions, plain_message: current().plain_message }; navigator.clipboard.writeText(JSON.stringify(payload)).then(()=>alert("Copied JSON to clipboard")) }
    const genBtn = el("generate-key"); if(genBtn) genBtn.onclick = ()=>{ const key = uuid(); const lk = qs("last-key"); if(lk){ lk.textContent = `Key: ${key}`; lk.dataset.key = key } }
    const saveBtn = el("save-local"); if(saveBtn) saveBtn.onclick = ()=>{ const key = (qs("last-key") && qs("last-key").dataset.key) || uuid(); const payload = { key, embeds: State.sessions, plain_message: current().plain_message }; localStorage.setItem(`embed_${key}`, JSON.stringify(payload)); const lk = qs("last-key"); if(lk) lk.textContent = `Saved key: ${key}` }

    // keyboard left/right to navigate carousel
    document.addEventListener("keydown", (ev)=>{
      if(ev.key === "ArrowLeft"){ if(State.idx>0){ State.idx--; renderSessionInfo(); } }
      if(ev.key === "ArrowRight"){ if(State.idx < State.sessions.length-1){ State.idx++; renderSessionInfo(); } }
    });
  }

  init();
})();