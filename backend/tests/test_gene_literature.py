import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import gene_literature as literature, main


GENE_ID = "Zm00001eb287000"
OTHER_ID = "Zm00001eb081920"
ARGOS_DOI = "10.1111/pbi.12603"


def paper(key, title, doi="", pmid=""):
    return {"source_record_key": key, "title": title, "doi": doi, "pmid": pmid}


class TestGeneLiterature(unittest.TestCase):
    def setUp(self):
        self.url = f"/genes/{GENE_ID}/literature"
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        literature.find_mentions.cache_clear()
        self.addCleanup(literature.find_mentions.cache_clear)
        self.papers = [
            paper("alias", "ARGOS8 variants in maize", ARGOS_DOI, "27442592"),
            paper("duplicate", "ZmARGOS8 variants", "HTTPS://DOI.ORG/" + ARGOS_DOI.upper()),
            paper("exact", GENE_ID + " editing"),
            paper("legacy", "Older maize genome"),
            paper("alias_abstract", "Experiment with an alias"),
            paper("longer_word", "ZmARGOS80 and preARGOS8 in maize"),
            paper("background", "A CRISPR/Cas9 platform for maize"),
        ]
        self.abstracts = {"legacy": "Results for Zm00001d038075", "alias_abstract": "It targets alt8."}
        self.curated = {
            GENE_ID: literature.CuratedGene(
                aliases=["ARGOS8", "ZmARGOS8"], legacy_ids=["Zm00001d038075"],
            ),
        }
        for mock in (
            patch.object(main, "read_neo4j", side_effect=self.read_neo4j),
            patch.object(literature, "load_paper_metadata", return_value=(self.papers, self.abstracts)),
            patch.object(literature, "load_curated", return_value=self.curated),
        ):
            mock.start()
            self.addCleanup(mock.stop)

    def read_neo4j(self, request, operation, gene_id):
        self.assertIs(operation, main.fetch_gene_identity)
        if gene_id == GENE_ID:
            return {"gene_id": gene_id, "aliases": "alt8; unknown"}
        if gene_id == OTHER_ID:
            return {"gene_id": gene_id, "symbol": "unknown"}
        return None

    def test_mentions_pagination_and_duplicate_doi(self):
        with patch.object(literature, "find_similar_papers") as semantic:
            response = self.client.get(self.url, params={"limit": 2})
            page = response.json()
            second = self.client.get(self.url, params={"offset": page["next_offset"]}).json()
            semantic.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(page["candidate_total"], 4)
        self.assertEqual(page["verified_evidence"], [])
        self.assertEqual(page["semantic_status"], "not_requested")
        self.assertEqual(page["next_offset"], 2)
        self.assertEqual([p["match_type"] for p in page["candidates"]], ["gene_id", "legacy_id"])
        self.assertEqual(second["next_offset"], None)
        argos, alias = second["candidates"]
        self.assertEqual(argos["doi"], ARGOS_DOI)
        self.assertEqual(argos["matched_term"], "ARGOS8")
        self.assertEqual(argos["matched_in"], "title")
        self.assertEqual(alias["matched_term"], "alt8")
        self.assertEqual(alias["matched_in"], "abstract")

    def test_verified_doi_is_scoped_to_gene_and_removed_from_candidates(self):
        self.curated[GENE_ID].verified_evidence.append(literature.VerifiedEvidence(
            title="ARGOS8 study", doi=ARGOS_DOI, pmid="27442592",
            study_context="Test experimental context", finding="Test finding",
            source_locator="Results", identity_source="https://example.org/gene",
            reviewed_by="Test reviewer", reviewed_on="2026-11-05",
        ))
        payload = self.client.get(self.url).json()
        self.assertEqual(payload["verified_evidence"][0]["doi"], ARGOS_DOI)
        self.assertEqual(payload["verified_evidence"][0]["reviewed_by"], "Test reviewer")
        self.assertEqual(payload["candidate_total"], 3)
        self.assertNotIn(ARGOS_DOI, {p["doi"] for p in payload["candidates"]})
        other = self.client.get(f"/genes/{OTHER_ID}/literature").json()
        self.assertEqual(other["verified_evidence"], [])

    def test_semantic_is_opt_in_and_separate_from_mentions(self):
        retrieved = [
            {**self.papers[0], "abstract": ""},
            {**self.papers[-1], "abstract": "A study of unrelated targets."},
        ]
        with patch.object(literature, "find_similar_papers", return_value=retrieved) as similar:
            payload = self.client.get(self.url, params={"include_semantic": True}).json()
            self.assertIn("ARGOS8", similar.call_args.args[0])
        self.assertEqual(payload["candidate_total"], 4)
        self.assertEqual(payload["verified_evidence"], [])
        self.assertEqual(payload["semantic_status"], "ok")
        self.assertEqual([p["source_record_key"] for p in payload["semantic_candidates"]], ["background"])
        self.assertEqual(payload["semantic_candidates"][0]["match_type"], "semantic")

    def test_semantic_outage_preserves_candidates(self):
        with patch.object(literature, "find_similar_papers", side_effect=HTTPException(503)):
            response = self.client.get(self.url, params={"include_semantic": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["semantic_status"], "unavailable")
        self.assertEqual(response.json()["candidate_total"], 4)

    def test_empty_known_gene_and_bad_inputs(self):
        response = self.client.get(f"/genes/{OTHER_ID}/literature")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["candidates"], [])
        self.assertEqual(response.json()["candidate_total"], 0)
        self.assertEqual(self.client.get("/genes/missing/literature").status_code, 404)
        self.assertEqual(self.client.get("/genes/bad%20id/literature").status_code, 422)
        self.assertEqual(self.client.get(self.url, params={"limit": 26}).status_code, 422)
        self.assertEqual(self.client.get(self.url, params={"offset": -1}).status_code, 422)

    def test_metadata_and_curated_configuration_errors_are_503(self):
        for method in ("load_paper_metadata", "load_curated"):
            with self.subTest(method=method), patch.object(
                literature, method, side_effect=ValueError("private path or config")
            ):
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("private", response.text)

    def test_database_failure_is_503(self):
        with patch.object(main, "read_neo4j", side_effect=HTTPException(503)):
            self.assertEqual(self.client.get(self.url).status_code, 503)


if __name__ == "__main__":
    unittest.main()
