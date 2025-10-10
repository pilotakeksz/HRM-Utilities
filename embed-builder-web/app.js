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
    qs("session-info").textContent = `Embed ${State.idx+1} / ${State.sessions.length}`;
    const s = current();
    qs("title").value = s.title; qs("description").value = s.description;
    qs("color").value = s.color; qs("image_url").value = s.image_url; qs("thumbnail_url").value = s.thumbnail_url;
    qs("footer").value = s.footer; qs("footer_icon").value = s.footer_icon; qs("plain_message").value = s.plain_message;
    renderFields(); renderButtons(); updatePreview();
  }

  function renderFields(){
    const list = qs("fields-list"); list.innerHTML = "";
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
    const list = qs("link-buttons"); list.innerHTML = "";
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
    const preview = qs("preview-area"); preview.innerHTML = "";
    const s = current();
    const card = document.createElement("div"); card.className="preview-card";
    const title = document.createElement("div"); title.style.color="#d0b47b"; title.textContent = s.title || "(no title)";
    const desc = document.createElement("div"); desc.textContent = s.description || "";
    card.append(title,desc);
    if(s.thumbnail_url){ const th = document.createElement("img"); th.src = s.thumbnail_url; th.style.width="64px"; th.style.float="right"; card.append(th) }
    if(s.image_url){ const img=document.createElement("img"); img.src=s.image_url; img.style.maxWidth="100%"; card.append(img) }
    if(s.fields.length){ s.fields.forEach(f=>{ const el=document.createElement("div"); el.innerHTML=`<b>${f.name}</b>: ${f.value}`; card.append(el) }) }
    if(s.buttons.length){
      const row=document.createElement("div"); row.style.marginTop="8px";
      s.buttons.forEach(b=>{
        const btn = document.createElement("button"); btn.className="btn"; btn.textContent = b.label || "button";
        if(b.type==="link" && b.url) btn.onclick = ()=>window.open(b.url,"_blank");
        row.append(btn);
      });
      card.append(row)
    }
    if(s.plain_message){ const m=document.createElement("div"); m.style.marginTop="8px"; m.textContent = s.plain_message; card.append(m) }
    preview.append(card);
  }

  // wire UI
  function init(){
    State.sessions = [ newSession() ];
    bind();
    renderSessionInfo();
  }

  function bind(){
    qs("add-embed").onclick = ()=>{ State.sessions.push(newSession()); State.idx = State.sessions.length-1; renderSessionInfo() }
    qs("remove-embed").onclick = ()=>{ if(State.sessions.length>1){ State.sessions.splice(State.idx,1); State.idx = Math.max(0, State.idx-1); renderSessionInfo() } }
    qs("prev-embed").onclick = ()=>{ if(State.idx>0) State.idx--; renderSessionInfo() }
    qs("next-embed").onclick = ()=>{ if(State.idx < State.sessions.length-1) State.idx++; renderSessionInfo() }

    qs("title").oninput = ()=>{ current().title = qs("title").value; updatePreview() }
    qs("description").oninput = ()=>{ current().description = qs("description").value; updatePreview() }
    qs("color").oninput = ()=>{ current().color = qs("color").value.replace("#",""); updatePreview() }
    qs("image_url").onchange = ()=>{ current().image_url = qs("image_url").value; updatePreview() }
    qs("thumbnail_url").onchange = ()=>{ current().thumbnail_url = qs("thumbnail_url").value; updatePreview() }
    qs("footer").onchange = ()=>{ current().footer = qs("footer").value; updatePreview() }
    qs("footer_icon").onchange = ()=>{ current().footer_icon = qs("footer_icon").value; updatePreview() }
    qs("plain_message").oninput = ()=>{ current().plain_message = qs("plain_message").value; updatePreview() }

    qs("add-field").onclick = ()=>{ current().fields.push({name:"",value:"",inline:false}); renderFields(); updatePreview() }
    qs("add-link").onclick = ()=>{ current().buttons.push({type:"link",label:"",url:"",icon:"",target:"",ephemeral:false}); renderButtons(); updatePreview() }

    qs("export-json").onclick = ()=>{ const payload = { embeds: State.sessions, plain_message: current().plain_message, exported_at: new Date().toISOString() }; const s = JSON.stringify(payload, null, 2); const blob = new Blob([s], {type:"application/json"}); const a=document.createElement("a"); a.href=URL.createObjectURL(blob); a.download="embed_export.json"; a.click(); }
    qs("copy-json").onclick = ()=>{ const payload = { embeds: State.sessions, plain_message: current().plain_message }; navigator.clipboard.writeText(JSON.stringify(payload)).then(()=>alert("Copied JSON to clipboard")) }
    qs("generate-key").onclick = ()=>{ const key = uuid(); qs("last-key").textContent = `Key: ${key}`; qs("last-key").dataset.key = key }
    qs("save-local").onclick = ()=>{ const key = qs("last-key").dataset.key || uuid(); const payload = { key, embeds: State.sessions, plain_message: current().plain_message }; localStorage.setItem(`embed_${key}`, JSON.stringify(payload)); qs("last-key").textContent = `Saved key: ${key}` }
  }

  init();
})();