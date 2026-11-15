
/* BLAST Graphic Summary
   Supports demo data and imported BLAST tabular results.
*/

function initBlast() {
  const graphic = document.getElementById("blastGraphic");
  const fileInput = document.getElementById("blastFile");
  const status = document.getElementById("blastStatus");

  if (!graphic || !fileInput || !status) return;

  const colors = ["#287a48", "#74ae89", "#b1d4bc"];

  // Update BLAST summary
  function updateSummary(data) {
    Object.entries(data).forEach(([id, value]) => {
      const element = document.getElementById(id);
      if (element) element.textContent = value;
    });
  }

  let currentResult;
  const filters = document.createElement("div");
  filters.className = "blast-filters";
  filters.hidden = true;
  filters.innerHTML = '<label>Minimum identity (%) <input type="number" min="0" max="100" step="any" value="0"></label> <label>Maximum E-value <input type="number" min="0" step="any" placeholder="No limit"></label> <button type="button">Apply filters</button> <span role="status"></span>';
  graphic.before(filters);
  const [identityFilter, evalueFilter] = filters.querySelectorAll("input");
  filters.querySelector("button").onclick = () => {
    if (!currentResult) return;
    if (!identityFilter.checkValidity() || !evalueFilter.checkValidity()) {
      filters.querySelector("span").textContent = "Enter valid filter values.";
      return;
    }
    const min = Number(identityFilter.value || 0);
    const max = evalueFilter.value === "" ? Infinity : Number(evalueFilter.value);
    const hits = currentResult.hits.map(hit => ({...hit, segments: hit.segments.filter(s =>
      Number.isFinite(Number(s.identity)) && Number(s.identity) >= min &&
      Number.isFinite(Number(s.evalue)) && Number(s.evalue) <= max
    )})).filter(hit => hit.segments.length);
    drawGraphic(hits, currentResult.axisMax, currentResult.notice, currentResult.unit);
    filters.querySelector("span").textContent = `${hits.length} of ${currentResult.hits.length} subjects shown`;
  };
  function renderGraphic(hits, axisMax, notice, unit = "bp") {
    currentResult = {hits, axisMax, notice, unit};
    identityFilter.value = "0";
    evalueFilter.value = "";
    filters.hidden = false;
    filters.querySelector("span").textContent = "";
    drawGraphic(hits, axisMax, notice, unit);
  }
  // Display only existing HSP fields; no synthetic sequence alignments.
  function showHit(hit, segment, detail) {
    detail.replaceChildren();
    const heading = document.createElement("h4");
    heading.textContent = hit.name;
    detail.appendChild(heading);
    (segment ? [segment] : hit.segments).forEach(s => {
      const p = document.createElement("p");
      p.textContent = `Query: ${s.start}-${s.end} | Identity: ${s.identity}% | E-value: ${s.evalue} | Bit score: ${s.bitscore}`;
      detail.appendChild(p);
    });
    detail.hidden = false;
    detail.focus();
    detail.scrollIntoView({block: "nearest"});
  }
  function activate(element, handler) {
    element.setAttribute("tabindex", "0");
    element.setAttribute("role", "button");
    element.style.cursor = "pointer";
    element.addEventListener("click", handler);
    element.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); handler(); }
    });
  }
  // Draw the alignment graphic
  function drawGraphic(hits, axisMax, notice, unit = "bp") {
    graphic.replaceChildren();

    const message = document.createElement("p");
    message.textContent = notice;
    message.style.cssText =
      "font-size:13px;font-weight:600;color:#287a48;margin:10px 0 20px;";
    graphic.appendChild(message);
    const detail = document.createElement("div");
    detail.tabIndex = -1;
    detail.hidden = true;
    detail.setAttribute("aria-label", "Alignment details");

    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");

    const width = 1000;
    const left = 230;
    const right = 35;
    const plotWidth = width - left - right;
    const top = 55;
    const rowGap = 65;
    const height = top + hits.length * rowGap + 30;

    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("width", "100%");
    svg.setAttribute("role", "img");
    svg.setAttribute(
      "aria-label",
      "BLAST sequence alignment graphic"
    );
    svg.style.display = "block";

    function add(tag, attrs, parent = svg) {
      const el = document.createElementNS(ns, tag);

      Object.entries(attrs).forEach(([key, value]) => {
        el.setAttribute(key, String(value));
      });

      parent.appendChild(el);
      return el;
    }

    function addText(value, x, y, anchor = "middle") {
      const el = add("text", {
        x,
        y,
        "text-anchor": anchor,
        "font-size": 14,
        fill: "#405449"
      });

      el.textContent = value;
      return el;
    }

    function position(bp) {
      return left + (bp / axisMax) * plotWidth;
    }

    // Coordinate axis
    for (let i = 0; i <= 4; i++) {
      const bp = axisMax * i / 4;
      const x = position(bp);

      add("line", {
        x1: x,
        y1: 35,
        x2: x,
        y2: height - 15,
        stroke: "#cbd8ce",
        "stroke-dasharray": "4 5"
      });

      addText(
        Math.round(bp) + " " + unit,
        x,
        20
      );
    }

    add("line", {
      x1: left,
      y1: 35,
      x2: position(axisMax),
      y2: 35,
      stroke: "#5c7562",
      "stroke-width": 1.5
    });

    // Draw each subject sequence and its HSP segments
    hits.forEach((hit, index) => {
      const y = top + index * rowGap + 15;

      const label = hit.name.length > 27
        ? hit.name.slice(0, 24) + "..."
        : hit.name;

      const labelElement = addText(label, left - 15, y + 5, "end");
      activate(labelElement, () => showHit(hit, null, detail));

      const labelTitle = add("title", {}, labelElement);
      labelTitle.textContent = hit.name;

      hit.segments.forEach(segment => {
        const x1 = position(segment.start);
        const x2 = position(segment.end);

        const rect = add("rect", {
          x: x1,
          y: y - 12,
          width: Math.max(2, x2 - x1),
          height: 24,
          rx: 4,
          fill: colors[index % colors.length],
          stroke: "#377955",
          "stroke-width": 1.5
        });

        const tooltip = add("title", {}, rect);
        activate(rect, () => showHit(hit, segment, detail));
        rect.setAttribute("aria-label", `${hit.name}, query ${segment.start}-${segment.end}`);

        tooltip.textContent =
          `${hit.name}\n` +
          `Query: ${segment.start}-${segment.end} ${unit}\n` +
          `Identity: ${segment.identity}%\n` +
          `E-value: ${segment.evalue}\n` +
          `Bit score: ${segment.bitscore}`;
      });
    });

    graphic.appendChild(svg);
    graphic.appendChild(detail);
  }

  // Explicit test mode only; normal pages keep the empty state from gene.html.
  const demoMode = new URLSearchParams(location.search).get("blast_demo") === "1";
  if (demoMode) {
    // Initial demonstration data
    const demoHits = [
      {
        name: "Demo hit A",
        segments: [{start: 15, end: 1850, identity: 98.5, evalue: "1e-50", bitscore: 900}]
      },
      {
        name: "Demo hit B",
        segments: [
          {start: 280, end: 810, identity: 95, evalue: "1e-30", bitscore: 500},
          {start: 1120, end: 1700, identity: 93, evalue: "1e-25", bitscore: 450}
        ]
      },
      {
        name: "Demo hit C",
        segments: [{start: 600, end: 720, identity: 90, evalue: "1e-10", bitscore: 150}]
      }
    ];

    updateSummary({
      blastQueryId: "DEMO_QUERY",
      blastDatabase: "Demo maize sequences",
      blastMoleculeType: "Nucleotide",
      blastProgram: "blastn",
      blastQueryLength: "2013 nt"
    });

    renderGraphic(
      demoHits,
      2013,
      "DEMO DATA — Simulated alignments for layout testing only."
    );

    status.textContent =
      "DEMO DATA — Run NCBI BLAST or import results to view actual alignments.";

  }

  const controls = document.createElement("div");
  controls.className = "blast-controls";
  controls.innerHTML = '<p>Paste a maize sequence from a verified source. Running BLAST sends the sequence to NCBI to search Zea mays sequences, not just B73 v5.</p><textarea aria-label="Sequence" rows="5"></textarea><select aria-label="Program"><option>blastn</option><option>blastp</option></select><button type="button">Load gene sequence</button><button type="button">Run NCBI BLAST</button>';
  graphic.before(controls);
  const sequence = controls.querySelector("textarea");
  const program = controls.querySelector("select");
  const [load, run] = controls.querySelectorAll("button");
  async function remote(path, options) {
    const response = await fetch("/blast" + path, options);
    const data = await response.json();
    if (!response.ok) {
      const messages = {
        422: "Invalid sequence or request. Check the sequence and selected program.",
        429: "Requests are too frequent. Please wait before trying again.",
        501: "Gene sequences are not available yet. Paste a sequence from a verified source.",
        502: "NCBI is temporarily unavailable. Please try again later."
      };
      const detail = typeof data.detail === "string" && !/[\u3400-\u9fff]/.test(data.detail) ? data.detail : "The BLAST request failed. Please try again.";
      throw new Error(messages[response.status] || detail);
    }
    return data;
  }
  load.onclick = async () => {
    try {
      const id = new URLSearchParams(location.search).get("id");
      if (!id) throw new Error("No Gene ID was provided.");
      const data = await remote("/sequence/" + encodeURIComponent(id));
      sequence.value = data.sequence;
      program.value = data.molecule === "protein" ? "blastp" : "blastn";
    } catch (error) { status.textContent = error.message; }
  };
  run.onclick = async () => {
    run.disabled = true; fileInput.disabled = true;
    graphic.replaceChildren();
    currentResult = undefined;
    filters.hidden = true;
    status.textContent = "Submitting to NCBI…";
    try {
      const task = await remote("/jobs", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({sequence:sequence.value, program:program.value})});
      updateSummary({blastQueryId:task.rid, blastProgram:program.value, blastDatabase:"NCBI Zea mays", blastQueryLength:"Pending", blastMoleculeType:program.value === "blastp" ? "Protein" : "Nucleotide"});
      const poll = async () => {
        try {
          const data = await remote("/jobs/" + encodeURIComponent(task.rid));
          if (data.status === "WAITING") { setTimeout(poll,60000); return; }
          if (data.status !== "READY") throw new Error("NCBI status: " + data.status);
          const unit = data.program === "blastp" ? "aa" : "bp";
          updateSummary({blastQueryId:data.query_id, blastProgram:data.program, blastDatabase:data.database, blastQueryLength:data.query_length + " " + unit});
          renderGraphic(data.hits,data.query_length,data.hits.length ? "NCBI BLAST results" : "No hits found",unit);
          status.textContent = "Completed | RID: " + task.rid + " | " + data.hits.length + " subjects";
        } catch(error) { status.textContent = error.message; }
        run.disabled = false; fileInput.disabled = false;
      };
      status.textContent = "NCBI BLAST is running | RID: " + task.rid + " | Checking every 60 seconds.";
      setTimeout(poll,60000);
    } catch(error) { status.textContent = error.message; run.disabled = false; fileInput.disabled = false; }
  };
  // Import BLAST tabular results (standard outfmt 6)
  fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    if (!file) return;

    try {
      status.textContent = "Reading BLAST results...";

      const content = await file.text();

      const lines = content.split(/\r?\n/)
        .filter(line => line.trim() && !line.startsWith("#"));

      if (!lines.length) {
        throw new Error("The selected file contains no alignment records.");
      }

      const records = lines.map((line, index) => {
        const columns = line.split("\t");

        if (columns.length < 12) {
          throw new Error(
            `Invalid BLAST format at data row ${index + 1}.`
          );
        }

        const identity = Number(columns[2]);
        const qstart = Number(columns[6]);
        const qend = Number(columns[7]);
        const evalue = Number(columns[10]);
        const bitscore = Number(columns[11]);

        if (
          !Number.isFinite(identity) ||
          !Number.isFinite(qstart) ||
          !Number.isFinite(qend) ||
          !Number.isFinite(evalue) ||
          !Number.isFinite(bitscore) ||
          qstart <= 0 ||
          qend <= 0
        ) {
          throw new Error(
            `Invalid numerical data at row ${index + 1}.`
          );
        }

        return {
          queryId: columns[0],
          subjectId: columns[1],
          identity,
          start: Math.min(qstart, qend),
          end: Math.max(qstart, qend),
          evalue: columns[10],
          bitscore
        };
      });

      // Group HSPs belonging to the same subject sequence
      const hitMap = new Map();

      records.forEach(record => {
        if (!hitMap.has(record.subjectId)) {
          hitMap.set(record.subjectId, {
            name: record.subjectId,
            bestBitscore: record.bitscore,
            segments: []
          });
        }

        const hit = hitMap.get(record.subjectId);

        hit.bestBitscore = Math.max(
          hit.bestBitscore,
          record.bitscore
        );

        hit.segments.push({
          start: record.start,
          end: record.end,
          identity: record.identity,
          evalue: record.evalue,
          bitscore: record.bitscore
        });
      });

      const hits = Array.from(hitMap.values())
        .sort((a, b) => b.bestBitscore - a.bestBitscore);

      const maxPosition = Math.max(
        ...records.map(record => record.end)
      );

      const axisMax = Math.ceil(maxPosition / 100) * 100 || 100;

      updateSummary({
        blastQueryId: records[0].queryId,
        blastDatabase: "Imported BLAST results",
        blastMoleculeType: "Not specified",
        blastProgram: "Not specified",
        blastQueryLength: "Not included in standard outfmt 6"
      });

      const isDemo = file.name.toLowerCase().includes("demo");

      const notice = isDemo
        ? "DEMO DATA — Imported test records, not scientific evidence."
        : "IMPORTED BLAST RESULTS — Check the source and parameters.";

      renderGraphic(hits, axisMax, notice);

      status.textContent =
        `File loaded: ${file.name} | ` +
        `${records.length} alignment records | ` +
        `${hits.length} subject sequences.`;

    } catch (error) {
      status.textContent = "Import failed: " + error.message;
    }
  });
}

// Initialize after the page is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initBlast);
} else {
  initBlast();
}
