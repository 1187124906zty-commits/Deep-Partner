"""Provenance and resume tests; no network calls or production credentials."""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import tempfile
import tarfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile


PATH = Path(__file__).resolve().parents[1] / "ops/mineru_knowledge_ingest.py"
SPEC = importlib.util.spec_from_file_location("mineru_ingest", PATH)
ingest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ingest)


def archive_bytes() -> bytes:
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w") as archive:
        archive.writestr("full.md", "Sample")
    return result.getvalue()


class ProvenanceTests(unittest.TestCase):
    def test_html_heading_locators_reference_actual_markdown_lines(self):
        headings = ingest.markdown_headings("<!-- source -->\n\n# First\nbody\n## Second\ntext\n",
                                           "purpose.S01", "https://example.test/source")
        self.assertEqual([(h["markdown_start_line"],h["markdown_end_line"]) for h in headings], [(3,4),(5,6)])
        self.assertEqual(headings[1]["source_url"], "https://example.test/source")
        self.assertEqual(headings[1]["locator"], "purpose.S01:heading:2")

    def test_inline_table_image_resolves_to_real_slice_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            raw=Path(directory)
            (raw/'images').mkdir()
            (raw/'images/logo.jpg').write_bytes(b'image')
            text=ingest.block_markdown({'type':'table','table_body':'<table><td><img src="logo.jpg"/></td></table>'},
                                      '../parts/slice/raw/',raw)
            self.assertIn('src="../parts/slice/raw/images/logo.jpg"',text)

    def test_mixed_book_mapping_and_later_slice_offset(self):
        mapping = ingest.input_mapping({"pages": [
            {"sample_pdf_page": 1, "source_id": "book.a", "source_pdf_page": 213},
            {"sample_pdf_page": 2, "source_id": "book.b", "source_pdf_page": 42},
        ]}, 2, "pilot")
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory)
            raw = job / "parts/p0002/raw"
            (raw / "images").mkdir(parents=True)
            (raw / "images/table.jpg").write_bytes(b"image")
            pages = ingest.map_content([
                {"type": "text", "text": "Do not omit 0.05.", "page_idx": 0},
                {"type": "image", "img_path": "images/table.jpg", "page_idx": 0},
            ], mapping, 1, 1, raw, job, "p0002")
            self.assertEqual(pages[0]["input_pdf_page"], 2)
            self.assertEqual(pages[0]["source_id"], "book.b")
            self.assertEqual(pages[0]["source_pdf_page"], 42)
            self.assertIn("Do not omit 0.05.", pages[0]["text"])
            self.assertTrue(pages[0]["assets"][0]["exists"])
            self.assertIn("../parts/p0002/raw/images/table.jpg", pages[0]["text"])

    def test_out_of_slice_page_cannot_become_a_source_citation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                ingest.map_content([{"type": "text", "text": "x", "page_idx": 1}],
                    {0: {"source_id": "book.a", "source_pdf_page": 213}}, 0, 1, root, root, "part")

    def test_manifest_requires_unique_complete_page_mapping(self):
        with self.assertRaises(ValueError):
            ingest.input_mapping({"pages": [
                {"sample_pdf_page": 1, "source_id": "book.a", "source_pdf_page": 2},
                {"sample_pdf_page": 1, "source_id": "book.a", "source_pdf_page": 3},
            ]}, 2, "pilot")

    def test_preproc_recovery_does_not_move_next_book_paragraph(self):
        layout = {"pdf_info": [
            {"page_idx": 0, "preproc_blocks": [{"type": "text", "lines": [
                {"spans": [{"type": "text", "content": "It requires careful"}]}]}]},
            {"page_idx": 1, "preproc_blocks": [{"type": "text", "lines": [
                {"spans": [{"type": "text", "content": "functional energy drinks (FEDs)."}]}]}]},
        ]}
        items = ingest.preproc_content(layout, 2)
        self.assertEqual([(item["page_idx"], item["text"]) for item in items],
                         [(0, "It requires careful"), (1, "functional energy drinks (FEDs).")])

    def test_probe_exposes_cross_page_citation_drift_without_passing_accuracy(self):
        text = "This paragraph physically belongs to the second source page and must retain that page locator."
        physical = [{"input_pdf_page": 2, "source_id": "book.b", "source_pdf_page": 42,
            "blocks": [{"original": {"text": text}}], "assets": [], "text": text,
            "review_status": "unreviewed"}]
        legacy = [{"input_pdf_page": 1, "text": text}, {"input_pdf_page": 2, "text": "Other text"}]
        probe = ingest.structure_probes(physical, legacy, 2)
        self.assertEqual(probe["cross_page_relocations_in_legacy"][0]["legacy_input_pdf_pages"], [1])
        self.assertEqual(physical[0]["review_status"], "unreviewed")
        self.assertIn("legacy_cross_page_text_relocation", physical[0]["risk_flags"])


class ResumeTests(unittest.TestCase):
    def test_archive_contains_actual_markdown_and_pdf_without_live_private_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'inputs').mkdir()
            (root/'inputs/book.a.pdf').write_bytes(b'original pdf')
            job=root/'jobs/book.a'
            ingest.write_json(job/'public-summary.json',{'status':'parsed_requires_content_review',
                'source_sha256':ingest.file_digest(root/'inputs/book.a.pdf'),'input_pages':1})
            ingest.write_json(job/'parts/p0001-0001/private-state.json',{'upload_url':'signed-private'})
            (job/'derived').mkdir()
            (job/'derived/page-faithful.md').write_text('actual document',encoding='utf-8')
            manifest=ingest.archive_book(SimpleNamespace(root=str(root),source_id='book.a'))
            with tarfile.open(manifest['archive_path']) as packed:
                names=packed.getnames()
            self.assertIn('inputs/book.a.pdf',names)
            self.assertIn('jobs/book.a/derived/page-faithful.md',names)
            self.assertFalse(any('private-state' in n for n in names))

    def test_known_done_batch_downloads_without_new_job_or_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            part = Path(directory)
            source = part / "sample.pdf"
            source.write_bytes(b"pdf")
            ingest.write_json(part / "private-state.json", {
                "batch_id": "existing-batch", "stage": "uploaded", "upload_completed": True})
            cloud = SimpleNamespace(
                _request_upload=Mock(), _upload_file=Mock(),
                _get_json=Mock(return_value={"data": {"extract_result": [
                    {"file_name": "sample.pdf", "state": "done", "full_zip_url": "https://example.test/result"}]}}),
                _match_entry=lambda rows, name: rows[0], _download=Mock(return_value=archive_bytes()))
            result = ingest.ensure_archive(source, part, SimpleNamespace(api_keys=["secret"]),
                cloud, None, None, timeout=1, poll_interval=0)
            cloud._request_upload.assert_not_called()
            cloud._upload_file.assert_not_called()
            self.assertEqual(result["batch_id"], "existing-batch")
            self.assertTrue((part / "original-result.zip").exists())

    def test_uncertain_post_cannot_automatically_create_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            part = Path(directory)
            ingest.write_json(part / "private-state.json", {"stage": "submit_unknown"})
            cloud = SimpleNamespace(_request_upload=Mock())
            with self.assertRaisesRegex(RuntimeError, "do not create a replacement"):
                ingest.ensure_archive(part / "sample.pdf", part,
                    SimpleNamespace(api_keys=[]), cloud, None, None, timeout=1, poll_interval=0)
            cloud._request_upload.assert_not_called()

    def test_exported_errors_remove_api_key_and_signed_url(self):
        result = ingest.safe_message("secret-key https://example.test/upload?signature=private failed",
                                     ["secret-key"])
        self.assertNotIn("secret-key", result)
        self.assertNotIn("signature", result)

    def test_batch_does_not_start_later_books_after_first_book_interruption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = root / "plan.json"
            ingest.write_json(plan, {"root": str(root), "documents": [
                {"source_id": sid, "remote_input": str(root / (sid + ".pdf")), "pages": 180}
                for sid in ["book.srw2", "book.awg3", "book.corpora2"]]})
            fake_lock = SimpleNamespace(flock=Mock(), LOCK_EX=1, LOCK_NB=2)
            run = Mock(side_effect=TimeoutError("Resume known batch after wall budget"))
            with patch.dict("sys.modules", {"fcntl": fake_lock}), patch.object(ingest, "run_cloud", run):
                result = ingest.run_batch(SimpleNamespace(plan=str(plan), wall_budget=1200,
                                                          timeout=1200, poll_interval=4))
            self.assertEqual(result, 2)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0].source_id, "book.srw2")
            self.assertEqual(ingest.read_json(root / "batch-progress.json")["completed_sources"], [])

    def test_status_does_not_export_temporary_signed_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ingest.write_json(root / "jobs/book.a/parts/p0001-0180/private-state.json", {
                "stage": "uploaded", "batch_id": "known-batch", "upload_url": "https://example.test/?signature=private"})
            text = json.dumps(ingest.public_status(root))
            self.assertIn("known-batch", text)
            self.assertNotIn("signature", text)
            self.assertNotIn("upload_url", text)


if __name__ == "__main__":
    unittest.main()
