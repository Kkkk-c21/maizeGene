
/* BLAST Graphic Summary
   Front-end visualization demo only.
   All alignment records below are simulated.
*/

document.addEventListener("DOMContentLoaded", () => {
  const graphic = document.getElementById("blastGraphic");
  if (!graphic) return;

  // Simulated BLAST results (NOT scientific evidence)
  const blastData = {
    queryId: "DEMO_QUERY",
    queryLength: 2013,
    moleculeType: "Nucleotide",
    database: "Demo maize sequences",
    program: "blastn",
    hits: [
      {
        name: "Demo hit A",
        segments: [[15, 1850]]
      },
      {
        name: "Demo hit B",
        segments: [[280, 810], [1120, 1700]]
      },
      {
        name: "Demo hit C",
        segments: [[600, 720]]
      }
    ]
  };

  // Update summary values
  const summary = {
    blastQueryId: blastData.queryId,
    blastDatabase: blastData.database,
    blastMoleculeType: blastData.moleculeType,
    blastProgram: blastData.program,
    blastQueryLength: blastData.queryLength + " nt"
  };

  Object.entries(summary).forEach(([id, value]) => {
    const element = document.getElementById(id);
    if (element) element.textContent = value;
  });

  graphic.replaceChildren();

  const demoNotice = document.createElement("p");
  demoNotice.textContent =
    "DEMO DATA — Simulated alignments for layout testing only.";
  demoNotice.style.cssText =
    "color:#a35c2b;font-weight:600;font-size:13px;";
  graphic.appendChild(demoNotice);

  // Create responsive SVG alignment chart
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");

  const width = 900;
  const left = 150;
  const right = 30;
  const plotWidth = width - left - right;
  const chartHeight = 90 + blastData.hits.length * 70;

  svg.setAttribute("viewBox", `0 0 ${width} ${chartHeight}`);
  svg.setAttribute("width", "100%");
  svg.setAttribute("role", "img");
  svg.setAttribute(
    "aria-label",
    "Demonstration BLAST alignment graphic with simulated hits"
  );

  function addElement(tag, attributes, parent = svg) {
    const element = document.createElementNS(ns, tag);

    Object.entries(attributes).forEach(([key, value]) => {
      element.setAttribute(key, String(value));
    });

    parent.appendChild(element);
    return element;
  }

  function addText(value, x, y, anchor = "start") {
    const element = addElement("text", {
      x, y,
      "text-anchor": anchor,
      "font-size": 13,
      fill: "#405449"
    });

    element.textContent = value;
    return element;
  }

  function position(bp) {
    return left + bp / blastData.queryLength * plotWidth;
  }

  // Draw axis and reference lines
  const ticks = [0, 500, 1000, 1500, 2000];

  ticks.forEach(bp => {
    const x = position(bp);

    addElement("line", {
      x1: x, y1: 43,
      x2: x, y2: chartHeight - 20,
      stroke: "#cbd8ce",
      "stroke-dasharray": "4 5"
    });

    addText(bp + " bp", x, 28, "middle");
  });

  addElement("line", {
    x1: left,
    y1: 43,
    x2: position(blastData.queryLength),
    y2: 43,
    stroke: "#5c7562",
    "stroke-width": 1.5
  });

  // Draw individual alignment hits
  blastData.hits.forEach((hit, index) => {
    const y = 75 + index * 70;

    addText(hit.name, 12, y + 6);

    hit.segments.forEach(([start, end]) => {
      const x1 = position(start);
      const x2 = position(end);

      const bar = addElement("rect", {
        x: x1,
        y: y - 10,
        width: x2 - x1,
        height: 20,
        rx: 3,
        fill: ["#287a48", "#74ae89", "#b1d4bc"][index % 3],
stroke: "#377955",
        "stroke-width": 1.5
      });

      const tooltip = addElement("title", {}, bar);
      tooltip.textContent =
        `${hit.name}: ${start}–${end} bp (simulated)`;
    });
  });

  graphic.appendChild(svg);

  const status = document.getElementById("blastStatus");
  if (status) {
    status.textContent =
      "Demo visualization only. Real BLAST results have not yet been integrated.";
  }
});
