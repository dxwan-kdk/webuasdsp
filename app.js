const $ = (sel) => document.querySelector(sel);

const fileEl = $("#file");
const opEl = $("#operation");

const statusEl = $("#status");
const metaEl = $("#meta");

const inWrap = $("#inWrap");
const outWrap = $("#outWrap");

const btnProcess = $("#btnProcess");
const btnReset = $("#btnReset");

function setStatus(msg, isError=false){
  statusEl.hidden = false;
  statusEl.textContent = msg;
  statusEl.style.opacity = "1";
  statusEl.dataset.error = isError ? "1" : "0";
}

function clearStatus(){
  statusEl.hidden = true;
  statusEl.textContent = "";
}

function showWrapImage(wrap, url){
  wrap.classList.remove("placeholder");
  wrap.innerHTML = `<img class="previewImg" src="${url}" alt="preview" />`;
}

function showPlaceholder(wrap, text){
  wrap.classList.add("placeholder");
  wrap.innerHTML = `<div class="ph">${text}</div>`;
}

function updateVisibleFields(){
  const op = opEl.value;
  document.querySelectorAll("[data-show]").forEach(el => {
    const allowed = el.getAttribute("data-show").split(" ").includes(op);
    el.style.display = allowed ? "" : "none";
  });
}

opEl.addEventListener("change", updateVisibleFields);
updateVisibleFields();

btnReset.addEventListener("click", () => {
  fileEl.value = "";
  showPlaceholder(inWrap, "Belum ada gambar");
  showPlaceholder(outWrap, "Belum diproses");
  metaEl.hidden = true;
  metaEl.textContent = "";
  clearStatus();
});

btnProcess.addEventListener("click", async () => {
  clearStatus();
  metaEl.hidden = true;
  metaEl.textContent = "";

  const f = fileEl.files?.[0];
  if(!f){
    setStatus("Pilih gambar dulu.", true);
    return;
  }

  btnProcess.disabled = true;
  btnProcess.textContent = "Memproses...";

  try{
    const fd = new FormData();
    fd.append("image", f);
    fd.append("operation", opEl.value);

    // params
    fd.append("factor", $("#factor")?.value ?? "");
    fd.append("antialias", $("#antialias")?.value ?? "");
    fd.append("scale", $("#scale")?.value ?? "");
    fd.append("method", $("#method")?.value ?? "");
    fd.append("amount", $("#amount")?.value ?? "");
    fd.append("radius", $("#radius")?.value ?? "");
    fd.append("alpha", $("#alpha")?.value ?? "");
    fd.append("beta", $("#beta")?.value ?? "");

    const res = await fetch("/api/process", { method: "POST", body: fd });
    const data = await res.json();

    if(!data.ok){
      setStatus(data.error || "Gagal memproses.", true);
      return;
    }

    showWrapImage(inWrap, data.input_url);
    showWrapImage(outWrap, data.output_url);

    metaEl.hidden = false;
    metaEl.textContent = JSON.stringify(data.meta, null, 2);

    setStatus("Selesai ✔");
  }catch(e){
    setStatus("Error: " + (e?.message || e), true);
  }finally{
    btnProcess.disabled = false;
    btnProcess.textContent = "Proses";
  }
});
