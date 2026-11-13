
/* Pan-genome and Ortholog Data
   Uses existing relative API endpoints.
*/

async function loadGeneHomology() {
  const params = new URLSearchParams(window.location.search);
  const geneId = params.get("id");

  const panResults = document.getElementById("panGenomeResults");
  const panStatus = document.getElementById("panGenomeStatus");
  const orthoResults = document.getElementById("orthologResults");
  const orthoStatus = document.getElementById("orthologStatus");

  if (!panResults || !orthoResults) return;

  if (!geneId) {
    panStatus.textContent = "No gene ID provided.";
    orthoStatus.textContent = "No gene ID provided.";
    return;
  }

  // Helper: create safe text elements
  function addText(parent, tag, value) {
    const element = document.createElement(tag);
    element.textContent = value;
    parent.appendChild(element);
    return element;
  }


  // Example mode: uses the same rendering and pagination logic
  const demoMode = new URLSearchParams(
    window.location.search
  ).get("homology_demo") === "1";

  async function getHomologyData(url, kind) {
    if (!demoMode) {
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`API returned HTTP ${response.status}`);
      }

      return response.json();
    }

    const params = new URL(url, window.location.href).searchParams;
    const limit = Number(params.get("limit") || 20);
    const offset = Number(params.get("offset") || 0);

    if (kind === "pan") {
      const familyOffset = Number(
        params.get("family_offset") || 0
      );

      const memberCount = familyOffset === 0 ? 25 : 5;

      if (familyOffset > 1) {
        return {
          families: [],
          family_page: {has_more: false}
        };
      }

      const members = Array.from(
        {length: memberCount},
        (_, i) => ({
          member_gene_id: familyOffset === 0 && i === 0
            ? "Zm00020ab070550"
            : `DEMO_MEMBER_${familyOffset + 1}_${i + 1}`,
          material_id: familyOffset === 0 && i === 0
            ? "CML69"
            : `DEMO_MATERIAL_${i + 1}`,
          species: "Zea mays"
        })
      );

      return {
        families: [{
          pan_gene_id: familyOffset === 0
            ? "pan-zea.v4.pan00001"
            : "DEMO_FAMILY_2",
          analysis_version: "pan-zea.v4",
          member_count: memberCount,
          members: members.slice(offset, offset + limit),
          member_page: {
            has_more: offset + limit < memberCount
          }
        }],
        family_page: {
          has_more: familyOffset === 0
        }
      };
    }

    const allOrthologs = Array.from(
      {length: 23},
      (_, i) => ({
        target_gene_id: i === 0
          ? "BGIOSGA020710"
          : `DEMO_ORTHOLOG_${i + 1}`,
        species: i % 2 === 0
          ? "Oryza sativa"
          : "Sorghum bicolor",
        homology_type: "ortholog_one2many",
        target_perc_id: i === 0 ? 95.7101 : null
      })
    );

    const species = (params.get("species") || "")
      .trim().toLowerCase();

    const filtered = allOrthologs.filter(
      item => !species ||
        item.species.toLowerCase() === species
    );

    return {
      orthologs: filtered.slice(offset, offset + limit),
      page: {
        has_more: offset + limit < filtered.length
      }
    };
  }




  // Pan-genome: family and member pagination
  let panFamilyOffset = 0;
  let panMemberOffset = 0;

  const panMemberLimit = 20;
  let panRequestNumber = 0;

  // Create pagination controls
  function createPanPager(previousText, nextText) {
    const container = document.createElement("div");
    container.style.cssText =
      "display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:16px 0;";

    const previous = document.createElement("button");
    previous.type = "button";
    previous.textContent = previousText;

    const info = document.createElement("span");
    info.style.color = "#607568";

    const next = document.createElement("button");
    next.type = "button";
    next.textContent = nextText;

    previous.disabled = true;
    next.disabled = true;

    container.append(previous, info, next);

    return { container, previous, info, next };
  }

  const familyPager = createPanPager(
    "Previous Family",
    "Next Family"
  );

  const memberPager = createPanPager(
    "Previous Members",
    "Next Members"
  );

  const panFamilyContent = document.createElement("div");

  panResults.replaceChildren(
    familyPager.container,
    panFamilyContent,
    memberPager.container
  );

  async function fetchPanGenome() {
    const currentRequest = ++panRequestNumber;

    panStatus.textContent = "Loading pan-genome data...";

    familyPager.previous.disabled = true;
    familyPager.next.disabled = true;
    memberPager.previous.disabled = true;
    memberPager.next.disabled = true;

    try {
      const query = new URLSearchParams({
        limit: String(panMemberLimit),
        offset: String(panMemberOffset),
        family_limit: "1",
        family_offset: String(panFamilyOffset)
      });

      
      const data = await getHomologyData(
        `/api/v1/genes/${encodeURIComponent(geneId)}/pan?${query}`,
        "pan"
      );


      if (currentRequest !== panRequestNumber) return;

      panFamilyContent.replaceChildren();

      const families = Array.isArray(data.families)
        ? data.families
        : [];

      if (!families.length) {
        panStatus.textContent = "No pan-gene families found.";
        familyPager.info.textContent = "";
        memberPager.info.textContent = "";
        return;
      }

      const family = families[0];

      const group = document.createElement("div");
      group.className = "go-category";

      addText(
        group,
        "h3",
        family.pan_gene_id || "Pan-gene family"
      );

      addText(
        group,
        "p",
        `Analysis: ${family.analysis_version || "Unknown"} | ` +
        `Total members: ${family.member_count ?? "Unknown"}`
      );

      const memberList = document.createElement("ul");
      memberList.className = "annotation-list";

      const members = Array.isArray(family.members)
        ? family.members
        : [];

      members.forEach(member => {
        const geneName = member.member_gene_id || "Unknown gene";
        const material = member.material_id || "Unknown material";
        const species = member.species || "Unknown species";

        addText(
          memberList,
          "li",
          `${geneName} — ${material} | ${species}`
        );
      });

      if (!members.length) {
        addText(
          memberList,
          "li",
          "No members available on this page."
        );
      }

      group.appendChild(memberList);
      panFamilyContent.appendChild(group);

      // Family pagination
      familyPager.info.textContent =
        `Family ${panFamilyOffset + 1}`;

      familyPager.previous.disabled =
        panFamilyOffset === 0;

      familyPager.next.disabled =
        !data.family_page?.has_more;

      // Member pagination
      memberPager.info.textContent =
        `Members page ${Math.floor(
          panMemberOffset / panMemberLimit
        ) + 1}`;

      memberPager.previous.disabled =
        panMemberOffset === 0;

      memberPager.next.disabled =
        !family.member_page?.has_more;

      panStatus.textContent =
  (demoMode ? "EXAMPLE DATA — Test only. " : "") +
  `Showing ${members.length} members in the selected family.`;

    } catch (error) {
      if (currentRequest !== panRequestNumber) return;

      panFamilyContent.replaceChildren();
      panStatus.textContent =
        "Unable to load pan-genome data: " + error.message;
    }
  }

  // Switch families
  familyPager.previous.addEventListener("click", () => {
    if (panFamilyOffset === 0) return;

    panFamilyOffset -= 1;
    panMemberOffset = 0;

    fetchPanGenome();
  });

  familyPager.next.addEventListener("click", () => {
    panFamilyOffset += 1;
    panMemberOffset = 0;

    fetchPanGenome();
  });

  // Switch member pages
  memberPager.previous.addEventListener("click", () => {
    if (panMemberOffset === 0) return;

    panMemberOffset -= panMemberLimit;
    fetchPanGenome();
  });

  memberPager.next.addEventListener("click", () => {
    panMemberOffset += panMemberLimit;
    fetchPanGenome();
  });

  fetchPanGenome();



  // Orthologs: species filtering and pagination
  let orthologOffset = 0;
  const orthologLimit = 20;
  let selectedSpecies = "";

  // Create controls
  const controls = document.createElement("form");
  controls.style.cssText =
    "display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:16px 0;";

  const speciesLabel = document.createElement("label");
  speciesLabel.textContent = "Filter by species:";
  speciesLabel.htmlFor = "orthologSpeciesFilter";

  const speciesInput = document.createElement("input");
  speciesInput.id = "orthologSpeciesFilter";
  speciesInput.type = "text";
  speciesInput.placeholder = "e.g. Oryza sativa";
  speciesInput.style.cssText =
    "padding:9px;border:1px solid #cbd8ce;border-radius:6px;";

  const filterButton = document.createElement("button");
  filterButton.type = "submit";
  filterButton.textContent = "Apply Filter";
  filterButton.style.cssText =
    "padding:9px 16px;background:#287a48;color:white;border:0;border-radius:6px;cursor:pointer;";

  controls.append(speciesLabel, speciesInput, filterButton);

  const list = document.createElement("ul");
  list.className = "annotation-list";

  const pagination = document.createElement("div");
  pagination.style.cssText =
    "display:flex;align-items:center;gap:14px;margin-top:16px;";

  const previousButton = document.createElement("button");
  previousButton.type = "button";
  previousButton.textContent = "Previous";

  const pageInfo = document.createElement("span");

  const nextButton = document.createElement("button");
  nextButton.type = "button";
  nextButton.textContent = "Next";

  pagination.append(previousButton, pageInfo, nextButton);
  orthoResults.replaceChildren(controls, list, pagination);

  let requestNumber = 0;

  async function fetchOrthologs() {
    const currentRequest = ++requestNumber;

    orthoStatus.textContent = "Loading ortholog data...";
    list.replaceChildren();
    previousButton.disabled = true;
    nextButton.disabled = true;
    filterButton.disabled = true;

    try {
      const query = new URLSearchParams({
        limit: String(orthologLimit),
        offset: String(orthologOffset)
      });

      if (selectedSpecies) {
        query.set("species", selectedSpecies);
      }

            const data = await getHomologyData(
        `/api/v1/genes/${encodeURIComponent(geneId)}/orthologs?${query}`,
        "ortholog"
      );

      if (currentRequest !== requestNumber) return;

      const records = Array.isArray(data.orthologs)
        ? data.orthologs
        : [];

      records.forEach(gene => {
        const identityValue = Number(gene.target_perc_id);
        const identity = gene.target_perc_id == null ||
          !Number.isFinite(identityValue)
          ? "N/A"
          : identityValue.toFixed(2) + "%";

        addText(
          list,
          "li",
          `${gene.target_gene_id || "Unknown"} | ` +
          `${gene.species || "Unknown species"} | ` +
          `${gene.homology_type || "Unspecified"} | ` +
          `Identity: ${identity}`
        );
      });

      if (!records.length) {
        addText(list, "li", "No matching orthologs found.");
      }

      const pageNumber =
        Math.floor(orthologOffset / orthologLimit) + 1;

      pageInfo.textContent = `Page ${pageNumber}`;
      previousButton.disabled = orthologOffset === 0;
      nextButton.disabled = !data.page?.has_more;

      orthoStatus.textContent =
  (demoMode ? "EXAMPLE DATA — Test only. " : "") +
  `Showing ${records.length} ortholog records.` +
  (selectedSpecies ? ` Species: ${selectedSpecies}.` : "");

    } catch (error) {
      if (currentRequest !== requestNumber) return;

      pageInfo.textContent = "";
      orthoStatus.textContent =
        "Unable to load ortholog data: " + error.message;
    } finally {
      if (currentRequest === requestNumber) {
        filterButton.disabled = false;
      }
    }
  }

  controls.addEventListener("submit", event => {
    event.preventDefault();
    selectedSpecies = speciesInput.value.trim();
    orthologOffset = 0;
    fetchOrthologs();
  });

  previousButton.addEventListener("click", () => {
    if (orthologOffset < orthologLimit) return;
    orthologOffset -= orthologLimit;
    fetchOrthologs();
  });

  nextButton.addEventListener("click", () => {
    orthologOffset += orthologLimit;
    fetchOrthologs();
  });

  fetchOrthologs();

}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", loadGeneHomology);
} else {
  loadGeneHomology();
}
