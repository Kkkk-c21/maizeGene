function loadGeneLiterature(geneId) {
  const endpoint = "/genes/" + encodeURIComponent(geneId) + "/literature";
  const status = document.getElementById("literatureStatus");
  const groups = document.getElementById("literatureGroups");
  const verifiedList = document.getElementById("verifiedPapers");
  const candidateList = document.getElementById("candidatePapers");
  const candidateStatus = document.getElementById("candidateStatus");
  const more = document.getElementById("literatureMore");
  const retry = document.getElementById("literatureRetry");
  const semanticButton = document.getElementById("literatureSemantic");
  const semanticList = document.getElementById("semanticPapers");
  const semanticStatus = document.getElementById("semanticStatus");
  const matchLabels = {
    gene_id: "Gene ID",
    legacy_id: "Earlier gene model ID",
    symbol_or_alias: "Gene symbol or alias"
  };
  let nextOffset = 0;

  function appendText(parent, tag, value) {
    const element = document.createElement(tag);
    element.textContent = value;
    parent.appendChild(element);
    return element;
  }

  function appendLink(parent, label, href) {
    const link = appendText(parent, "a", label);
    link.href = href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
  }

  function renderPaper(paper, verified = false) {
    const item = document.createElement("li");
    appendText(item, "h4", paper.title || "Untitled paper");
    const links = document.createElement("p");
    if (paper.doi && /^10\.[0-9]{4,9}\/\S+$/.test(paper.doi)) {
      const doiPath = paper.doi.split("/").map(encodeURIComponent).join("/");
      appendLink(links, "DOI " + paper.doi, "https://doi.org/" + doiPath);
    }
    if (paper.pmid && /^[0-9]+$/.test(paper.pmid)) {
      if (links.childNodes.length) links.append(" · ");
      appendLink(links, "PubMed " + paper.pmid, "https://pubmed.ncbi.nlm.nih.gov/" + paper.pmid + "/");
    }
    if (links.childNodes.length) item.appendChild(links);

    if (verified) {
      appendText(item, "p", "Study context — " + paper.study_context);
      appendText(item, "p", "Finding — " + paper.finding);
      appendText(item, "p", "Source location — " + paper.source_locator);
      appendText(item, "p", "Reviewed by " + paper.reviewed_by + " on " + paper.reviewed_on);
      if (/^https?:\/\//i.test(paper.identity_source)) {
        appendLink(item, "Gene identity source", paper.identity_source);
      }
    } else if (paper.match_type === "semantic") {
      appendText(item, "p", "Semantic similarity · Gene mention unconfirmed");
    } else {
      const label = matchLabels[paper.match_type];
      appendText(item, "p", label + " match · " + paper.matched_term + " · " + paper.matched_in);
    }
    if (paper.abstract) {
      const details = document.createElement("details");
      appendText(details, "summary", "Abstract");
      appendText(details, "p", paper.abstract);
      item.appendChild(details);
    }
    return item;
  }

  async function fetchLiterature(params) {
    const response = await fetch(endpoint + "?" + new URLSearchParams(params), {
      cache: "no-store"
    });
    if (!response.ok) throw new Error("Literature request failed");
    return response.json();
  }

  async function loadCandidates() {
    const firstPage = nextOffset === 0;
    more.disabled = true;
    retry.disabled = true;
    (firstPage ? status : candidateStatus).textContent = "Loading literature…";
    try {
      const data = await fetchLiterature({offset: nextOffset});
      const rows = data.candidates.map(paper => renderPaper(paper));
      if (firstPage) {
        verifiedList.replaceChildren(...data.verified_evidence.map(paper => renderPaper(paper, true)));
        verifiedList.hidden = verifiedList.childElementCount === 0;
        document.getElementById("verifiedEmpty").hidden = !verifiedList.hidden;
        groups.hidden = false;
        status.textContent = "";
        retry.hidden = true;
      }
      candidateList.append(...rows);
      candidateList.hidden = candidateList.childElementCount === 0;
      candidateStatus.textContent = data.candidate_total === 0
        ? "No candidate mentions were found in the indexed titles and abstracts."
        : "Showing " + candidateList.childElementCount + " of " + data.candidate_total + " candidates.";
      nextOffset = data.next_offset;
      more.hidden = nextOffset === null;
    } catch {
      if (firstPage) {
        status.textContent = "Literature is temporarily unavailable.";
        retry.hidden = false;
      } else {
        candidateStatus.textContent = "Could not load more candidates. Try again.";
      }
    } finally {
      more.disabled = false;
      retry.disabled = false;
    }
  }

  async function loadSemantic() {
    semanticButton.disabled = true;
    semanticStatus.textContent = "Finding semantic suggestions…";
    try {
      const data = await fetchLiterature({include_semantic: true, limit: 1});
      if (data.semantic_status !== "ok") throw new Error("Semantic search failed");
      semanticList.replaceChildren(...data.semantic_candidates.map(paper => renderPaper(paper)));
      semanticList.hidden = semanticList.childElementCount === 0;
      semanticStatus.textContent = semanticList.hidden ? "No additional suggestions were found." : "";
      semanticButton.hidden = true;
    } catch {
      semanticStatus.textContent = "Semantic suggestions are temporarily unavailable. Try again.";
    } finally {
      semanticButton.disabled = false;
    }
  }

  retry.addEventListener("click", loadCandidates);
  more.addEventListener("click", loadCandidates);
  semanticButton.addEventListener("click", loadSemantic);
  loadCandidates();
}
