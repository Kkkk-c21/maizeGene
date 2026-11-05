import unittest
from unittest.mock import patch

from fastapi import HTTPException
from backend import main


class TestUnifiedSearch(unittest.TestCase):

    def setUp(self):
        self.request = main.UnifiedSearchRequest(
            query="maize salt tolerance",
            top_k_genes=3,
            top_k_papers=3,
        )
        self.genes = {
            "results": [{"gene_id": "Zm00001eb298460", "similarity": 0.5}],
            "total_genes": 44303,
        }
        self.papers = {
            "papers": [{"source_record_key": "MED:31522293", "title": "Test"}]
        }

    def test_both_available(self):
        with patch.object(main, "search_genes", return_value=self.genes), \
             patch.object(main, "search_literature", return_value=self.papers):
            result = main.unified_search(self.request)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["returned_genes"], 1)
        self.assertEqual(result["returned_papers"], 1)
        self.assertEqual(
            result["genes"][0]["detail_url"],
            "/genes/Zm00001eb298460",
        )

    def test_gene_service_unavailable(self):
        with patch.object(
            main, "search_genes",
            side_effect=HTTPException(status_code=503)
        ), patch.object(main, "search_literature", return_value=self.papers):
            result = main.unified_search(self.request)

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["returned_genes"], 0)
        self.assertEqual(result["returned_papers"], 1)

    def test_literature_service_unavailable(self):
        with patch.object(main, "search_genes", return_value=self.genes), \
             patch.object(
                 main, "search_literature",
                 side_effect=HTTPException(status_code=503)
             ):
            result = main.unified_search(self.request)

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["returned_genes"], 1)
        self.assertEqual(result["returned_papers"], 0)

    def test_both_unavailable(self):
        with patch.object(
            main, "search_genes",
            side_effect=HTTPException(status_code=503)
        ), patch.object(
            main, "search_literature",
            side_effect=HTTPException(status_code=503)
        ):
            with self.assertRaises(HTTPException) as error:
                main.unified_search(self.request)

        self.assertEqual(error.exception.status_code, 503)

    def test_exact_gene_id_without_embedding(self):
        request = main.UnifiedSearchRequest(query="Zm00001eb298460")

        with patch.object(main, "gene_ids", ["Zm00001eb298460"]), \
             patch.object(main, "search_genes") as gene_search, \
             patch.object(main, "search_literature") as paper_search:
            result = main.unified_search(request)

        self.assertEqual(result["genes"][0]["match_type"], "exact_id")
        self.assertEqual(result["returned_papers"], 0)
        gene_search.assert_not_called()
        paper_search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
