from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from llm_identify.corpus import TrustedCorpusLoader, TrustedCorpusSource, default_trusted_corpus_sources


class TrustedCorpusTests(unittest.TestCase):
    def test_embedded_corpus_loads_with_version_metadata(self) -> None:
        sources = default_trusted_corpus_sources()
        self.assertTrue(sources)
        with tempfile.TemporaryDirectory() as tmp:
            result = TrustedCorpusLoader(sources[0], tmp).load(provider_id="openai", claimed_model="gpt-4o")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.source_type, "trusted_reference_corpus")
        self.assertEqual(result.metadata["schema_version"], "1.0.0")
        self.assertTrue(result.models)
        self.assertIsNotNone(result.method)

    def test_default_sources_include_initialized_community_submodule(self) -> None:
        source_ids = {source.source_id for source in default_trusted_corpus_sources()}
        self.assertIn("embedded_trusted_reference", source_ids)
        self.assertIn("community_trusted_references", source_ids)

    def test_accepted_directory_loads_reviewed_candidate_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            accepted = Path(tmp) / "accepted" / "openai" / "gpt-4o"
            accepted.mkdir(parents=True)
            (accepted / "sample.json").write_text(
                json.dumps(
                    {
                        "schema_version": "trusted-reference-candidate/v1",
                        "sample_type": "trusted_reference_candidate",
                        "verification_status": "maintainer_review_required",
                        "task_ref": "task_hash_value",
                        "endpoint": {"provider": "openai", "official_host": "api.openai.com", "matched_path": "/v1"},
                        "model": {"claimed_by_official_endpoint": "gpt-4o"},
                        "versions": {"probe_pack": "pack-v1", "sanitizer": "1.0.0"},
                        "capability_scores": {},
                        "fingerprint_vector": {},
                    }
                ),
                encoding="utf-8",
            )
            source = TrustedCorpusSource(source_id="community", path=str(Path(tmp) / "accepted"))
            result = TrustedCorpusLoader(source, tmp).load(provider_id="openai", claimed_model="gpt-4o")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.metadata["release"], "git-submodule")
        self.assertEqual(result.models[0]["id"], "gpt-4o")
        self.assertEqual(result.models[0]["trust_tier"], "T2")
        self.assertIsNotNone(result.method)

    def test_remote_corpus_falls_back_to_cached_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            source = TrustedCorpusSource(source_id="remote", url="https://example.invalid/corpus.json")
            cache_path = TrustedCorpusLoader(source, cache_dir)._cache_path()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "corpus_version": "cached-v1",
                        "model_profiles": [
                            {
                                "id": "google.gemini_family",
                                "provider_family_id": "google_like",
                                "aliases": ["gemini"],
                                "trust_tier": "T1",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = TrustedCorpusLoader(source, cache_dir).load(provider_id="google", claimed_model="gemini-test")
        self.assertEqual(result.status, "cached")
        self.assertEqual(result.metadata["corpus_version"], "cached-v1")
        self.assertEqual(result.models[0]["family"], "google_like")
        self.assertIsNotNone(result.degraded_reason)


if __name__ == "__main__":
    unittest.main()
